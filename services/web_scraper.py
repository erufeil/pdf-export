# -*- coding: utf-8 -*-
"""
Servicio de Web Scraping de contenido para PDFexport.
Extrae contenido estructurado de una URL: metadatos, cuerpo principal
(en texto plano o Markdown), informacion del footer y links.
Optimizado para procesamiento posterior con IA o insercion en DOCX.
"""

import logging
import re
import zipfile
import io
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse, urljoin, unquote

import requests
import config
from utils import job_manager

logger = logging.getLogger(__name__)

# User-Agent para simular navegador comun
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)

# Timeout para descarga de la pagina
TIMEOUT_PAGINA = 30  # segundos

# Importar librerias de scraping de forma condicional
try:
    from bs4 import BeautifulSoup
    import trafilatura
    from markdownify import markdownify as md
    SCRAPER_DISPONIBLE = True
    logger.info("Librerias de scraping cargadas correctamente")
except ImportError as e:
    SCRAPER_DISPONIBLE = False
    logger.warning(f"Librerias de scraping no disponibles: {e}. Instalar: beautifulsoup4, trafilatura, markdownify, lxml")


def _verificar_dependencias():
    """Verifica que las librerias de scraping esten disponibles."""
    if not SCRAPER_DISPONIBLE:
        raise ValueError(
            "Librerias de scraping no disponibles. "
            "Instalar: beautifulsoup4, trafilatura, markdownify, lxml"
        )


def _descargar_pagina(url: str) -> tuple:
    """
    Descarga el HTML de la URL.

    Returns:
        Tupla (html_texto, url_final_tras_redirects)
    """
    headers = {'User-Agent': USER_AGENT}
    respuesta = requests.get(
        url,
        timeout=TIMEOUT_PAGINA,
        headers=headers,
        verify=False  # Algunos sitios tienen certificados problematicos
    )
    respuesta.raise_for_status()
    return respuesta.text, respuesta.url


def _extraer_metadatos(soup: 'BeautifulSoup', url: str) -> Dict:
    """
    Extrae metadatos del <head>: titulo, URL canonica, fecha, autor, descripcion.
    Prioriza Open Graph y meta article: que usan los portales de noticias.
    """
    metadatos = {
        'titulo': '',
        'url': url,
        'sitio': urlparse(url).netloc,
        'fecha': '',
        'autor': '',
        'descripcion': '',
    }

    # Titulo: og:title > title tag
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        metadatos['titulo'] = og_title['content'].strip()
    elif soup.title:
        metadatos['titulo'] = soup.title.get_text(strip=True)

    # URL canonica (decodificar percent-encoding para legibilidad humana)
    canonical = soup.find('link', rel='canonical')
    og_url = soup.find('meta', property='og:url')
    if canonical and canonical.get('href'):
        metadatos['url'] = unquote(canonical['href'])
    elif og_url and og_url.get('content'):
        metadatos['url'] = unquote(og_url['content'])
    else:
        metadatos['url'] = unquote(url)

    # Fecha de publicacion: varios patrones en orden de prioridad
    fecha_busquedas = [
        ('meta', {'property': 'article:published_time'}),
        ('meta', {'property': 'article:modified_time'}),
        ('meta', {'name': 'date'}),
        ('meta', {'name': 'DC.date'}),
        ('meta', {'itemprop': 'datePublished'}),
        ('time', {'itemprop': 'datePublished'}),
        ('time', {}),
    ]
    for tag, attrs in fecha_busquedas:
        el = soup.find(tag, attrs)
        if el:
            fecha = el.get('content') or el.get('datetime') or el.get_text(strip=True)
            if fecha and len(fecha) >= 6:
                # Recortar a solo fecha si tiene hora (ISO 8601: 2024-01-15T10:30:00)
                metadatos['fecha'] = fecha[:10] if 'T' in fecha else fecha
                break

    # Autor: varios patrones en orden de prioridad
    autor_busquedas = [
        ('meta', {'property': 'article:author'}),
        ('meta', {'name': 'author'}),
        ('meta', {'name': 'DC.creator'}),
        ('span', {'itemprop': 'author'}),
        ('a', {'rel': 'author'}),
        ('span', {'class': re.compile(r'author|autor', re.I)}),
    ]
    for tag, attrs in autor_busquedas:
        el = soup.find(tag, attrs)
        if el:
            autor = el.get('content') or el.get_text(strip=True)
            if autor and len(autor) > 2:
                metadatos['autor'] = autor[:100]
                break

    # Descripcion: og:description > meta description
    og_desc = soup.find('meta', property='og:description')
    meta_desc = soup.find('meta', {'name': 'description'})
    if og_desc and og_desc.get('content'):
        metadatos['descripcion'] = og_desc['content'].strip()
    elif meta_desc and meta_desc.get('content'):
        metadatos['descripcion'] = meta_desc['content'].strip()

    return metadatos


def _extraer_contenido_body(html: str, url: str, formato: str) -> str:
    """
    Extrae el contenido principal del body usando trafilatura.
    trafilatura es el estado del arte en "boilerplate removal":
    elimina nav, ads, sidebar y se queda con el articulo/texto principal.

    Si trafilatura no encuentra nada usa BeautifulSoup como fallback.

    Args:
        html: HTML crudo de la pagina
        url: URL de la pagina (ayuda a trafilatura a mejorar extraccion)
        formato: 'texto' | 'markdown'

    Returns:
        Texto limpio del contenido principal
    """
    if formato == 'markdown':
        # trafilatura puede devolver Markdown directamente
        contenido = trafilatura.extract(
            html,
            url=url,
            include_links=True,
            include_formatting=True,
            output_format='markdown',
            no_fallback=False,
        )
    else:
        contenido = trafilatura.extract(
            html,
            url=url,
            include_links=True,
            include_formatting=False,
            no_fallback=False,
        )

    # DEBUG TEMPORAL: ver output crudo de trafilatura antes del post-procesado
    if contenido:
        logger.info(f"[trafilatura RAW] primeros 800 chars:\n{contenido[:800]!r}")
    else:
        logger.warning(f"[trafilatura RAW] retorno vacio para {url[:60]}")

    if not contenido:
        # Fallback: BeautifulSoup remueve nav/header/footer y extrae el body
        logger.warning(f"trafilatura no extrajo contenido de {url[:60]}, usando fallback BeautifulSoup")
        soup = BeautifulSoup(html, 'lxml')
        body = soup.find('body') or soup

        # Remover elementos que no son contenido principal
        for tag in body.find_all(['nav', 'header', 'footer', 'script', 'style', 'aside', 'form']):
            tag.decompose()

        if formato == 'markdown':
            contenido = md(str(body), heading_style='ATX', strip=['img', 'a'])
        else:
            contenido = body.get_text(separator='\n', strip=True)

        # Limpiar lineas vacias multiples (mas de 2 seguidas)
        contenido = re.sub(r'\n{3,}', '\n\n', contenido)

    if contenido and formato == 'markdown':
        # Caracter guardian: STX (0x02), nunca aparece en texto web normal.
        # Se inserta antes de viñetas para excluirlas del Paso 3 y se elimina al final.
        _G = '\x02'

        # --- Paso 0: Proteger viñetas y titulos de lista del Paso 3 ---
        # El Paso 3 une "\n\n[link]" cuando el char previo no es puntuacion segura.
        # Insertar _G justo antes del \n\n de una vineta hace que Paso 3 lo ignore.
        #
        # Caso A: viñeta con marcador (* o -):
        #   "texto\n\n* item" → "texto\x02\n\n* item"
        # Nota: el reemplazo usa lambda porque \x02 no es valido en strings de reemplazo de re.sub
        contenido = re.sub(
            r'([^.!?:\n#\x02])\n\n([*\-] )',
            lambda m: m.group(1) + _G + '\n\n' + m.group(2),
            contenido
        )
        # Caso B: titulo-lista SIN marcador "[Link](url): descripcion"
        #   La presencia de ":" justo despues de la URL indica que es un titulo,
        #   no un link inline. Comparar:
        #     "[Adenina](url): desc"  → titulo de lista → proteger
        #     "[virus](url) en el"    → link inline     → NO proteger (se une en Paso 3)
        contenido = re.sub(
            r'([^.!?:\n#\x02])\n\n(\[[^\]]+\]\([^)]+\)\s*:)',
            lambda m: m.group(1) + _G + '\n\n' + m.group(2),
            contenido
        )

        # --- Paso 1: Decodificar URLs percent-encoded en links Markdown ---
        # ej: [Ácido](%C3%81cido) → URL legible con acentos
        contenido = re.sub(
            r'\[([^\]]*)\]\(([^)]+)\)',
            lambda m: f'[{m.group(1)}]({unquote(m.group(2))})',
            contenido
        )

        # --- Paso 2: Eliminar referencias de notas al pie de Wikipedia ---
        # Forma link:  [[2]](url)  → eliminar completamente
        # Forma suelta: [1] (solo numero, sin URL) → eliminar
        contenido = re.sub(r'\[\[\d+\]\]\([^)]+\)', '', contenido)
        contenido = re.sub(r' ?\[\d+\] ?', ' ', contenido)

        # --- Paso 3: Unir doble salto (\n\n) antes de "[" o "*" inline en medio de oracion ---
        # Cuando la linea anterior NO termina en puntuacion de fin de oracion
        # (.  !  ?  :  #  \x02) el \n\n es falso inicio de parrafo (artefacto de trafilatura).
        # \x02 tambien excluido: protege viñetas insertadas en Paso 0.
        # ej: "→\n\n*A*"           → "→ *A*"       (inline, se une)
        # ej: "algunos\n\n[virus]" → "algunos [virus]" (inline, se une)
        # ej: "texto\x02\n\n* item"→ sin cambio    (viñeta protegida, NO se une)
        contenido = re.sub(r'([^.!?:\n#\x02])\n\n(\[|\*(?!\s|\*))', r'\1 \2', contenido)

        # --- Paso 4: Unir salto SIMPLE (\n) antes de "[" o "*" inline ---
        # Un salto simple dentro de un bloque es continuacion, no parrafo nuevo.
        # ej: "la molécula de\n[ADN]" → "la molécula de [ADN]"
        # ej: "puede ser\n*A*"        → "puede ser *A*"
        # Excluye listas "* item" (espacio) y negrita "**bold**" (asterisco)
        contenido = re.sub(r'([^\n])\n(\[|\*(?!\s|\*))', r'\1 \2', contenido)

        # --- Paso 5: Agregar espacio faltante entre ")" y siguiente "[" o texto ---
        # trafilatura a veces pega )[texto] o )texto sin espacio
        # ej: "[ADN](url)[molécula]" → "[ADN](url) [molécula]"
        # ej: "[virus](url)texto"    → "[virus](url) texto"
        contenido = re.sub(r'\)(\[)', r') \1', contenido)
        contenido = re.sub(r'\)([^\s\)\]\.,;:!?\n\(])', r') \1', contenido)

        # --- Paso 5b: Agregar espacio cuando "*" de cierre queda pegado al siguiente texto ---
        # ej: "*C*o [guanina]" → "*C* o [guanina]"
        # Solo aplica cuando hay letra ANTES del "*" (es cierre) y letra DESPUES (inicio de palabra)
        # NO aplica a apertura: "**ácido" → antes del 2do "*" hay otro "*", no letra → sin cambio
        contenido = re.sub(r'([a-zA-Z\u00C0-\u017E])\*([a-zA-Z\u00C0-\u017E])', r'\1* \2', contenido)

        # --- Paso 6: Limpiar espacios multiples generados por los pasos anteriores ---
        contenido = re.sub(r'  +', ' ', contenido)

        # --- Paso 7: Eliminar el caracter guardian (ya cumplio su funcion) ---
        contenido = contenido.replace(_G, '')

    return contenido or '(No se pudo extraer contenido principal)'


def _extraer_links(soup: 'BeautifulSoup', url_base: str) -> List[Dict]:
    """
    Extrae links del body con su texto descriptivo.
    Filtra links sin texto, anclas (#) y javascript:.
    Convierte URLs relativas a absolutas.
    Limita a 100 links para no saturar el output.
    """
    links = []
    seen = set()

    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        texto = a.get_text(strip=True)

        # Ignorar links sin texto util, anclas, javascript, mailto
        if not texto or not href:
            continue
        if href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
            continue

        # Convertir URLs relativas a absolutas
        if not href.startswith('http'):
            href = urljoin(url_base, href)

        # Decodificar percent-encoding para legibilidad humana
        # ej: /wiki/%C3%81cido → /wiki/Ácido
        href = unquote(href)

        # Deduplicar por URL
        if href in seen:
            continue
        seen.add(href)

        links.append({'texto': texto[:150], 'url': href})

        if len(links) >= 100:
            break

    return links


def _eliminar_enlaces_markdown(contenido: str) -> str:
    """
    Elimina todas las URLs del Markdown para lectura fluida de corrido.

    Reglas:
    - [[N]](url)   → nada  (referencias footnote numeradas tipo Wikipedia)
    - [N](url)     → nada  (referencias numéricas sueltas)
    - [texto](url) → texto (links normales: conserva el texto, borra la URL)
    """
    # 1. Referencias footnote dobles: [[3]](url) → nada
    contenido = re.sub(r'\[\[\d+\]\]\([^)]*\)', '', contenido)
    # 2. Referencias numéricas simples: [3](url) → nada
    contenido = re.sub(r'\[\d+\]\([^)]*\)', '', contenido)
    # 3. Links con texto descriptivo: [virus](url) → virus
    contenido = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', contenido)
    # 4. Limpiar espacios múltiples
    contenido = re.sub(r'  +', ' ', contenido)
    # 5. Eliminar espacios/tabs que quedaron al final de línea
    #    ej: "texto [1](url)\n" → "texto \n" → "texto\n"
    contenido = re.sub(r'[ \t]+\n', '\n', contenido)
    # 6. Colapsar 3+ saltos de línea en máximo 2
    #    ej: referencia en su propia línea "texto.\n\n[1](url)\n\ntexto" → "texto.\n\n\n\ntexto" → "texto.\n\ntexto"
    contenido = re.sub(r'\n{3,}', '\n\n', contenido)
    return contenido


def _extraer_footer(soup: 'BeautifulSoup') -> Dict:
    """
    Extrae informacion del footer: emails, telefonos, texto de contacto.
    Busca en etiquetas footer, secciones de contacto y aplica regex
    para detectar patrones de email y telefono.
    """
    resultado = {
        'emails': [],
        'telefonos': [],
        'texto': '',
    }

    # Regex para emails y telefonos
    patron_email = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
    patron_telefono = re.compile(
        r'(?:\+?\d{1,3}[\s\-.]?)?'          # codigo de pais opcional
        r'(?:\(?\d{1,4}\)?[\s\-.]?)?'        # codigo de area opcional
        r'\d{3,4}[\s\-.]?\d{3,4}'            # numero principal
        r'(?:[\s\-.]?\d{2,4})?'              # extension opcional
    )

    # Buscar en secciones de footer/contacto por id o class
    secciones = []
    footer_tag = soup.find('footer')
    if footer_tag:
        secciones.append(footer_tag)

    for selector_attr in ['id', 'class']:
        for seccion in soup.find_all(['section', 'div', 'aside'],
                                      attrs={selector_attr: re.compile(r'footer|contact|about|pie|contacto', re.I)}):
            if seccion not in secciones:
                secciones.append(seccion)

    # Armar texto completo de las secciones footer/contacto
    textos = []
    for seccion in secciones:
        texto = seccion.get_text(separator=' ', strip=True)
        if texto:
            textos.append(texto)

    texto_footer = ' '.join(textos)

    # Si no hay footer explicito, buscar en todo el documento
    if not texto_footer:
        texto_footer = soup.get_text(separator=' ', strip=True)

    # Extraer emails
    emails_encontrados = list(set(patron_email.findall(texto_footer)))
    # Filtrar emails genericos/placeholder
    resultado['emails'] = [
        e for e in emails_encontrados
        if not any(x in e.lower() for x in ['example', 'test', 'noreply', 'no-reply', 'yourdomain'])
    ][:10]

    # Extraer telefonos (solo los que tienen >= 7 digitos para evitar falsos positivos)
    telefonos_raw = patron_telefono.findall(texto_footer)
    telefonos_validos = []
    for tel in telefonos_raw:
        solo_digitos = re.sub(r'\D', '', tel)
        if len(solo_digitos) >= 7:
            tel_limpio = tel.strip()
            if tel_limpio not in telefonos_validos:
                telefonos_validos.append(tel_limpio)
    resultado['telefonos'] = telefonos_validos[:10]

    # Texto del primer bloque de footer (primeros 600 chars)
    if textos:
        resultado['texto'] = textos[0][:600]

    return resultado


def _formatear_salida_txt(
    metadatos: Dict,
    contenido: str,
    footer: Dict,
    links: List[Dict],
    opciones: Dict
) -> str:
    """
    Arma el archivo TXT final con secciones claramente delimitadas.
    Usa CRLF para compatibilidad con Notepad de Windows.
    """
    sep = '=' * 80
    lineas = []

    # === METADATOS ===
    if opciones.get('incluir_metadatos', True):
        lineas += [sep, 'METADATOS', sep]
        if metadatos.get('titulo'):
            lineas.append(f"Titulo:      {metadatos['titulo']}")
        if metadatos.get('url'):
            lineas.append(f"URL:         {metadatos['url']}")
        if metadatos.get('sitio'):
            lineas.append(f"Sitio:       {metadatos['sitio']}")
        if metadatos.get('fecha'):
            lineas.append(f"Fecha:       {metadatos['fecha']}")
        if metadatos.get('autor'):
            lineas.append(f"Autor:       {metadatos['autor']}")
        if metadatos.get('descripcion'):
            lineas.append(f"Descripcion: {metadatos['descripcion']}")
        lineas.append('')

    # === CONTENIDO PRINCIPAL ===
    if opciones.get('incluir_contenido', True):
        formato = opciones.get('formato_salida', 'markdown')
        etiqueta = 'CONTENIDO PRINCIPAL (Markdown)' if formato == 'markdown' else 'CONTENIDO PRINCIPAL'
        lineas += [sep, etiqueta, sep, contenido, '']

    # === FOOTER / CONTACTO ===
    if opciones.get('incluir_footer', True):
        lineas += [sep, 'FOOTER / CONTACTO', sep]
        if footer.get('emails'):
            lineas.append(f"Correos:    {', '.join(footer['emails'])}")
        if footer.get('telefonos'):
            lineas.append(f"Telefonos:  {', '.join(footer['telefonos'])}")
        if footer.get('texto'):
            lineas.append(f"\nTexto del footer:\n{footer['texto']}")
        if not footer.get('emails') and not footer.get('telefonos') and not footer.get('texto'):
            lineas.append('(No se encontro informacion de contacto en el footer)')
        lineas.append('')

    # === LINKS ===
    if opciones.get('incluir_links', True) and links:
        lineas += [sep, f'LINKS ({len(links)} encontrados)', sep]
        for link in links:
            lineas.append(f"- {link['texto']}: {link['url']}")
        lineas.append('')

    # CRLF para compatibilidad con Notepad de Windows
    return '\r\n'.join(lineas)


def scrapear_url(url: str, opciones: Dict, trabajo_id: str) -> Path:
    """
    Funcion principal del scraper: descarga la URL, extrae contenido
    estructurado y genera un archivo ZIP con el TXT resultante.

    Args:
        url: URL a scrapear
        opciones: Opciones de extraccion (formato_salida, incluir_*)
        trabajo_id: ID del trabajo para actualizar progreso

    Returns:
        Ruta al archivo ZIP generado
    """
    _verificar_dependencias()

    job_manager.actualizar_progreso(trabajo_id, 10, "Descargando pagina")
    html, url_final = _descargar_pagina(url)
    logger.info(f"Descargado {len(html)} bytes desde {url_final[:80]}")

    job_manager.actualizar_progreso(trabajo_id, 25, "Analizando estructura HTML")
    soup = BeautifulSoup(html, 'lxml')

    job_manager.actualizar_progreso(trabajo_id, 40, "Extrayendo metadatos")
    metadatos = _extraer_metadatos(soup, url_final)
    logger.info(f"Metadatos: titulo='{metadatos.get('titulo', '')[:50]}', autor='{metadatos.get('autor', '')}'")

    job_manager.actualizar_progreso(trabajo_id, 55, "Extrayendo contenido principal")
    formato = opciones.get('formato_salida', 'markdown')
    contenido = _extraer_contenido_body(html, url_final, formato)
    if formato == 'markdown' and opciones.get('eliminar_enlaces', False):
        contenido = _eliminar_enlaces_markdown(contenido)
        logger.info("Eliminar_enlaces activado: URLs removidas del Markdown")
    logger.info(f"Contenido extraido: {len(contenido)} caracteres (formato: {formato})")

    job_manager.actualizar_progreso(trabajo_id, 72, "Extrayendo footer y links")
    footer = _extraer_footer(soup)
    links = _extraer_links(soup, url_final)
    logger.info(f"Footer: {len(footer['emails'])} emails, {len(footer['telefonos'])} telefonos | Links: {len(links)}")

    job_manager.actualizar_progreso(trabajo_id, 85, "Generando archivo de salida")
    texto_final = _formatear_salida_txt(metadatos, contenido, footer, links, opciones)

    # Nombre de archivo basado en dominio
    dominio = urlparse(url_final).netloc.replace('.', '_').replace('www_', '')
    nombre_txt = f"{dominio}_scrape.txt"
    nombre_zip = f"{trabajo_id}_{dominio}_scrape.zip"
    ruta_zip = config.OUTPUT_FOLDER / nombre_zip

    # Crear ZIP con maxima compresion
    buffer_txt = texto_final.encode('utf-8')
    with zipfile.ZipFile(ruta_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr(nombre_txt, buffer_txt)

    logger.info(f"ZIP generado: {ruta_zip.name} ({ruta_zip.stat().st_size} bytes)")
    job_manager.actualizar_progreso(trabajo_id, 95, "Finalizando")

    return ruta_zip


def procesar_scrape_url(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal del scraper. Llamado por el job_manager.

    Nota: archivo_id no se usa (no hay archivo subido, la URL viene en parametros).

    Args:
        trabajo_id: ID del trabajo
        archivo_id: No usado (None)
        parametros: Debe contener 'url' y opcionalmente 'opciones'

    Returns:
        dict con ruta_resultado y mensaje
    """
    url = parametros.get('url')
    if not url:
        raise ValueError("No se especifico URL")

    opciones = parametros.get('opciones', {})

    job_manager.actualizar_progreso(trabajo_id, 2, "Iniciando scraping")
    ruta_resultado = scrapear_url(url, opciones, trabajo_id)

    return {
        'ruta_resultado': str(ruta_resultado),
        'mensaje': 'Contenido extraido y comprimido correctamente'
    }


# Registrar procesador en el job_manager
job_manager.registrar_procesador('scrape-url', procesar_scrape_url)
