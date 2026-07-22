# -*- coding: utf-8 -*-
"""
Servicio Wikipedia→MD para PDFexport (Etapa 44).
Extrae artículos de Wikipedia usando la API REST y los convierte a Markdown.
Fallback: GET directo + BeautifulSoup si la API REST falla.
"""

import re
import logging
from urllib.parse import urlparse, quote

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

import config
from utils import job_manager

logger = logging.getLogger(__name__)

_HEADERS = {
    'User-Agent': 'PDFexport/1.0 (https://github.com/ERF/PDFexport; contacto@pdfexport.local) Python/requests',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
}

_LANGS_VALIDOS = {'es', 'en', 'fr', 'de', 'pt', 'it', 'nl', 'pl', 'ru', 'ja', 'zh', 'ar'}


def _parsear_entrada(entrada: str, lang_hint: str) -> tuple[str, str, str]:
    """
    Retorna (lang, title_url_encoded, url_articulo).
    Soporta URL completa de Wikipedia o nombre de artículo.
    """
    if 'wikipedia.org' in entrada:
        parsed = urlparse(entrada)
        host = parsed.hostname or ''
        partes_host = host.split('.')
        lang = partes_host[0] if len(partes_host) >= 3 else lang_hint
        if lang not in _LANGS_VALIDOS:
            lang = lang_hint
        path = parsed.path
        if '/wiki/' not in path:
            raise ValueError("URL de Wikipedia inválida — debe contener /wiki/Título")
        title = path.split('/wiki/', 1)[1].split('#')[0]
    else:
        lang = lang_hint
        title = quote(entrada.strip().replace(' ', '_'), safe='():/-_.,')

    url_articulo = f'https://{lang}.wikipedia.org/wiki/{title}'
    return lang, title, url_articulo


def _obtener_via_api_rest(lang: str, title: str) -> tuple[str, str]:
    """
    GET https://{lang}.wikipedia.org/api/rest_v1/page/html/{title}
    Retorna (html, titulo_real).
    """
    url = f'https://{lang}.wikipedia.org/api/rest_v1/page/html/{title}'
    r = requests.get(url, headers=_HEADERS, timeout=20)
    if r.status_code == 404:
        raise ValueError(f"Artículo '{title}' no encontrado en {lang}.wikipedia.org")
    r.raise_for_status()

    soup = BeautifulSoup(r.text, 'lxml')
    h1 = soup.find('h1')
    titulo_real = h1.get_text(strip=True) if h1 else title.replace('_', ' ')
    return r.text, titulo_real


def _obtener_via_fallback(url_articulo: str) -> tuple[str, str]:
    """GET directo a la URL y BeautifulSoup sobre #mw-content-text."""
    r = requests.get(url_articulo, headers=_HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'lxml')

    titulo_tag = soup.find('h1', id='firstHeading') or soup.find('h1')
    titulo_real = titulo_tag.get_text(strip=True) if titulo_tag else ''

    contenido = soup.find(id='mw-content-text')
    if not contenido:
        raise ValueError("No se encontró el contenido del artículo")
    return str(contenido), titulo_real


def _limpiar_html(html: str) -> str:
    """Elimina elementos de navegación, notas al pie y decoradores de Wikipedia."""
    soup = BeautifulSoup(html, 'lxml')

    selectores_eliminar = [
        # Notas y referencias
        '.mw-ref', '.reference', '.mw-references-wrap', '.reflist', '.references', 'sup',
        # Navegación y cabeceras informativas
        '.hatnote', '.navbox', '.navbox-styles', '.mw-jump-link', '.toc',
        # Categorías y elementos de edición
        '.catlinks', '.mw-editsection', '.printfooter',
        # Miniaturas y pie de imágenes (evitar ruido en MD)
        '.thumbcaption', '.mw-ext-cite-error',
    ]
    for sel in selectores_eliminar:
        for el in soup.select(sel):
            el.decompose()

    # Secciones semánticas de la API REST
    secciones = soup.find_all('section')
    if secciones:
        return '\n'.join(str(s) for s in secciones if s.get_text(strip=True))

    return str(soup)


def _html_a_markdown(html: str) -> str:
    """Convierte el HTML limpio a Markdown."""
    md = markdownify(
        html,
        heading_style='ATX',
        bullets='-',
        strip=['script', 'style', 'img', 'figure', 'figcaption'],
    )
    # Eliminar referencias vacías [1], [2], []
    md = re.sub(r'\[\s*\d*\s*\]', '', md)
    # Colapsar más de 2 líneas en blanco consecutivas
    md = re.sub(r'\n{3,}', '\n\n', md)
    return md.strip()


def procesar_wikipedia_to_md(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """Procesador principal registrado como 'wikipedia-to-md'."""
    entrada  = parametros.get('entrada', '').strip()
    lang_in  = parametros.get('lang', 'es').strip()

    if not entrada:
        raise ValueError("No se recibió URL ni nombre de artículo")

    if lang_in not in _LANGS_VALIDOS:
        lang_in = 'es'

    job_manager.actualizar_progreso(trabajo_id, 5, "Analizando entrada")

    try:
        lang, title, url_articulo = _parsear_entrada(entrada, lang_in)
    except ValueError as e:
        raise ValueError(str(e)) from e

    job_manager.actualizar_progreso(trabajo_id, 20, f"Obteniendo artículo de {lang}.wikipedia.org")

    titulo_real = title.replace('_', ' ')
    try:
        html_crudo, titulo_real = _obtener_via_api_rest(lang, title)
        job_manager.actualizar_progreso(trabajo_id, 55, "Procesando contenido")
        html_limpio = _limpiar_html(html_crudo)
    except Exception as e_api:
        logger.warning(f"API REST Wikipedia falló ({e_api}), usando fallback directo")
        job_manager.actualizar_progreso(trabajo_id, 40, "Usando método alternativo")
        html_limpio, titulo_fb = _obtener_via_fallback(url_articulo)
        if titulo_fb:
            titulo_real = titulo_fb

    job_manager.actualizar_progreso(trabajo_id, 75, "Convirtiendo a Markdown")

    contenido_cuerpo = _html_a_markdown(html_limpio)
    if not contenido_cuerpo.strip():
        raise ValueError("El artículo no tiene contenido extraíble")

    encabezado = '\n'.join([
        f'# {titulo_real}',
        '',
        f'**Fuente:** Wikipedia ({lang.upper()})  **URL:** {url_articulo}',
        '',
        '---',
        '',
    ])
    contenido_md = encabezado + contenido_cuerpo + '\n'

    job_manager.actualizar_progreso(trabajo_id, 90, "Guardando archivo")

    nombre_base = re.sub(r'[^\w\s-]', '', titulo_real)[:60].strip()
    nombre_base = re.sub(r'\s+', '_', nombre_base) or title[:40]

    ruta_md = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_base}.md"
    with open(ruta_md, 'w', encoding='utf-8') as f:
        f.write(contenido_md)

    return {
        'ruta_resultado': str(ruta_md),
        'mensaje': f'Markdown generado: "{titulo_real}" · {len(contenido_md):,} caracteres'
    }


job_manager.registrar_procesador('wikipedia-to-md', procesar_wikipedia_to_md)
