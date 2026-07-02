# -*- coding: utf-8 -*-
"""
Servicio YouTube CC→MD para PDFexport (Etapa 43).
Descarga subtítulos/CC de YouTube y los convierte a Markdown.
Usa youtube-transcript-api v1.2.4 (instancia, no classmethods).

Workaround IP block: YOUTUBE_PROXY_URL o YOUTUBE_COOKIES_FILE en env.
"""

import re
import time
import logging
import http.cookiejar
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    CouldNotRetrieveTranscript,
)
from youtube_transcript_api.proxies import GenericProxyConfig

import config
import models
from utils import job_manager

logger = logging.getLogger(__name__)

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
}


def verificar_youtube_config() -> dict:
    """
    Retorna el estado de configuración del workaround de IP block.
    Usado por GET /youtube-to-md/check.
    """
    proxy_url = config.YOUTUBE_PROXY_URL
    cookies_file = config.YOUTUBE_COOKIES_FILE

    if proxy_url:
        return {
            'modo': 'proxy',
            'configurado': True,
            'mensaje': f'Proxy configurado ({proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url})'
        }

    if cookies_file:
        ruta = Path(cookies_file)
        if ruta.exists():
            return {
                'modo': 'cookies',
                'configurado': True,
                'mensaje': f'Cookies configuradas ({ruta.name})'
            }
        else:
            return {
                'modo': 'cookies',
                'configurado': False,
                'mensaje': f'Archivo de cookies no encontrado: {cookies_file}'
            }

    return {
        'modo': 'ninguno',
        'configurado': False,
        'mensaje': 'Sin proxy ni cookies — puede fallar en IPs de nube/datacenter'
    }


def _crear_ytt() -> YouTubeTranscriptApi:
    """Crea instancia de YouTubeTranscriptApi con proxy o cookies si están configurados."""
    proxy_url = config.YOUTUBE_PROXY_URL
    cookies_file = config.YOUTUBE_COOKIES_FILE

    if proxy_url:
        proxy_cfg = GenericProxyConfig(http_url=proxy_url, https_url=proxy_url)
        return YouTubeTranscriptApi(proxy_config=proxy_cfg)

    if cookies_file:
        ruta = Path(cookies_file)
        if ruta.exists():
            sesion = requests.Session()
            jar = http.cookiejar.MozillaCookieJar(str(ruta))
            jar.load(ignore_discard=True, ignore_expires=True)
            sesion.cookies = jar
            return YouTubeTranscriptApi(http_client=sesion)
        else:
            logger.warning(f'YOUTUBE_COOKIES_FILE no encontrado: {cookies_file}')

    return YouTubeTranscriptApi()


def _extraer_video_id(url: str) -> str:
    """Extrae el video_id de distintos formatos de URL de YouTube."""
    parsed = urlparse(url)
    host = (parsed.hostname or '').lower()

    if host == 'youtu.be':
        vid = parsed.path.lstrip('/')
        if vid:
            return vid.split('?')[0]

    if host in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
        if parsed.path == '/watch':
            qs = parse_qs(parsed.query)
            ids = qs.get('v', [])
            if ids:
                return ids[0]
        partes = parsed.path.split('/')
        if len(partes) >= 3 and partes[1] in ('shorts', 'embed', 'v'):
            return partes[2]

    raise ValueError(
        "URL inválida — debe ser youtube.com/watch?v=..., youtu.be/... o /shorts/..."
    )


def _extraer_meta_youtube(url: str, video_id: str) -> dict:
    """Obtiene título, descripción, keywords y canal desde las meta tags de la página."""
    meta = {'titulo': f'Video {video_id}'}
    try:
        r = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'lxml')

        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            meta['titulo'] = og_title['content'].strip()
        else:
            tag = soup.find('title')
            if tag:
                meta['titulo'] = tag.get_text(strip=True).replace(' - YouTube', '').strip()

        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            meta['descripcion'] = og_desc['content'].strip()
        else:
            m = soup.find('meta', attrs={'name': 'description'})
            if m and m.get('content'):
                meta['descripcion'] = m['content'].strip()

        kw = soup.find('meta', attrs={'name': 'keywords'})
        if kw and kw.get('content'):
            meta['keywords'] = kw['content'].strip()

        # Canal: itemprop author > name
        author = soup.find(attrs={'itemprop': 'author'})
        if author:
            name_tag = author.find(attrs={'itemprop': 'name'})
            if name_tag:
                meta['canal'] = name_tag.get('content') or name_tag.get_text(strip=True)

    except Exception as e:
        logger.warning(f"Error extrayendo metadatos YouTube {video_id}: {e}")

    return meta


def _obtener_transcripcion(video_id: str, idioma: str) -> tuple:
    """
    Retorna (texto_continuo, idioma_usado).
    idioma='auto' → primera disponible (manual antes que auto-generada).
    """
    ytt = _crear_ytt()

    if idioma == 'auto':
        lista = ytt.list(video_id)
        try:
            transcript = lista.find_manually_created_transcript(['es', 'en'])
        except NoTranscriptFound:
            transcript = lista.find_generated_transcript(['es', 'en'])
        fetched = transcript.fetch()
        idioma_usado = transcript.language_code
    else:
        langs_pref = [idioma]
        if idioma not in ('es', 'en'):
            langs_pref += ['es', 'en']
        try:
            fetched = ytt.fetch(video_id, languages=langs_pref)
            idioma_usado = idioma
        except NoTranscriptFound:
            lista = ytt.list(video_id)
            try:
                base = lista.find_manually_created_transcript(['es', 'en'])
            except NoTranscriptFound:
                base = lista.find_generated_transcript(['es', 'en'])
            fetched = base.translate(idioma).fetch()
            idioma_usado = f'{idioma} (traducido de {base.language_code})'

    fragmentos = fetched.to_raw_data()
    partes = []
    for f in fragmentos:
        t = f.get('text', '').strip()
        if t:
            t = re.sub(r'\[.*?\]', '', t).strip()
            if t:
                partes.append(t)

    texto = ' '.join(partes)
    texto = re.sub(r' {2,}', ' ', texto)
    return texto.strip(), idioma_usado


def procesar_youtube_to_md(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal registrado como 'youtube-to-md'.
    archivo_id no se usa (no hay archivo subido; URL viene en parametros).
    """
    url    = parametros.get('url', '').strip()
    idioma = parametros.get('idioma', 'auto')

    if not url:
        raise ValueError("No se recibió URL de YouTube")

    job_manager.actualizar_progreso(trabajo_id, 5, "Validando URL")

    video_id = _extraer_video_id(url)

    job_manager.actualizar_progreso(trabajo_id, 15, "Obteniendo metadatos del video")
    meta = _extraer_meta_youtube(url, video_id)
    titulo = meta.get('titulo', f'Video {video_id}')

    job_manager.actualizar_progreso(trabajo_id, 35, "Obteniendo transcripción")

    ultimo_error = None
    for intento in range(3):
        try:
            texto_cc, idioma_usado = _obtener_transcripcion(video_id, idioma)
            break
        except TranscriptsDisabled:
            raise ValueError("Este video no tiene subtítulos disponibles")
        except NoTranscriptFound:
            raise ValueError(
                f"No se encontró transcripción en idioma '{idioma}'. "
                "Probá con 'auto' para usar la primera disponible."
            )
        except CouldNotRetrieveTranscript as e:
            ultimo_error = e
            if intento < 2:
                time.sleep(2)
    else:
        raise ValueError(f"No se pudo obtener la transcripción: {ultimo_error}")

    if not texto_cc:
        raise ValueError("La transcripción está vacía")

    job_manager.actualizar_progreso(trabajo_id, 80, "Generando Markdown")

    lineas = [f'# {titulo}', '']
    lineas.append(f'**URL:** {url}  ')
    if 'canal' in meta:
        lineas.append(f'**Canal:** {meta["canal"]}  ')
    lineas.append(f'**Idioma transcripción:** {idioma_usado}  ')
    if meta.get('keywords'):
        lineas.append(f'**Keywords:** {meta["keywords"]}  ')

    if meta.get('descripcion'):
        lineas += ['', '---', '', '## Descripción', '', meta['descripcion']]

    lineas += ['', '---', '', '## Transcripción', '', texto_cc, '']

    contenido_md = '\n'.join(lineas)

    job_manager.actualizar_progreso(trabajo_id, 90, "Guardando archivo")

    nombre_base = re.sub(r'[^\w\s-]', '', titulo)[:60].strip()
    nombre_base = re.sub(r'\s+', '_', nombre_base) or video_id

    ruta_md = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_base}.md"
    with open(ruta_md, 'w', encoding='utf-8') as f:
        f.write(contenido_md)

    return {
        'ruta_resultado': str(ruta_md),
        'mensaje': f'Markdown generado: "{titulo}" · {len(contenido_md)} caracteres'
    }


job_manager.registrar_procesador('youtube-to-md', procesar_youtube_to_md)
