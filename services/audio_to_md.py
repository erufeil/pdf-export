# -*- coding: utf-8 -*-
"""
Servicio Audio→MD para PDFexport (Etapa 41).
Transcribe audio usando un servidor Whisper propio (API compatible OpenAI)
y genera un archivo Markdown con la transcripción.
"""

import logging
from pathlib import Path

import requests

import config
import models
from utils import job_manager

logger = logging.getLogger(__name__)

_FORMATOS = {'.wav', '.mp3', '.mp4', '.m4a'}

_MIME_POR_EXT = {
    '.wav': 'audio/wav',
    '.mp3': 'audio/mpeg',
    '.mp4': 'video/mp4',
    '.m4a': 'audio/mp4',
}


def verificar_whisper() -> dict:
    """Retorna {'disponible': bool, 'url': str, 'mensaje': str}."""
    url = (getattr(config, 'WHISPER_URL', '') or '').rstrip('/')
    if not url:
        return {'disponible': False, 'url': '', 'mensaje': 'WHISPER_URL no está configurado'}
    try:
        r = requests.get(f"{url}/v1/models", timeout=5)
        r.raise_for_status()
        return {'disponible': True, 'url': url, 'mensaje': 'Servidor Whisper disponible'}
    except requests.exceptions.ConnectionError:
        return {'disponible': False, 'url': url, 'mensaje': f'No se puede conectar a {url}'}
    except Exception as e:
        return {'disponible': False, 'url': url, 'mensaje': str(e)}


def procesar_audio_to_md(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """Procesador principal registrado como 'audio-to-md'."""
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta = Path(archivo['ruta_archivo'])
    if not ruta.exists():
        raise ValueError("Archivo físico no encontrado")

    whisper_url = (getattr(config, 'WHISPER_URL', '') or '').rstrip('/')
    if not whisper_url:
        raise ValueError(
            "WHISPER_URL no está configurado. "
            "Defina la variable de entorno WHISPER_URL apuntando a su servidor Whisper."
        )

    nombre_original = archivo['nombre_original']
    ext = Path(nombre_original).suffix.lower()
    if ext not in _FORMATOS:
        raise ValueError(f"Formato no soportado. Use: {', '.join(sorted(_FORMATOS))}")

    idioma = parametros.get('idioma', 'auto')

    job_manager.actualizar_progreso(trabajo_id, 10, "Enviando audio a Whisper")

    mime = _MIME_POR_EXT.get(ext, 'application/octet-stream')
    try:
        with open(ruta, 'rb') as audio_file:
            form = {
                'model':           (None, 'whisper-1'),
                'file':            (nombre_original, audio_file, mime),
                'response_format': (None, 'json'),
            }
            if idioma and idioma != 'auto':
                form['language'] = (None, idioma)

            r = requests.post(
                f"{whisper_url}/v1/audio/transcriptions",
                files=form,
                timeout=600,
            )
            r.raise_for_status()
            datos = r.json()

    except requests.exceptions.ConnectionError:
        raise ValueError(f"No se pudo conectar al servidor Whisper en {whisper_url}")
    except requests.exceptions.Timeout:
        raise ValueError("El servidor Whisper tardó demasiado en responder (>10 min)")
    except requests.exceptions.HTTPError as e:
        raise ValueError(f"Error del servidor Whisper ({r.status_code}): {e}")
    except Exception as e:
        raise ValueError(f"Error al transcribir: {e}")

    texto = (datos.get('text') or '').strip()
    if not texto:
        raise ValueError("La transcripción está vacía")

    job_manager.actualizar_progreso(trabajo_id, 88, "Generando Markdown")

    nombre_base = Path(nombre_original).stem
    formato = ext.lstrip('.').upper()
    idioma_md = idioma if idioma != 'auto' else 'detectado automáticamente'

    lineas = [
        f'# Transcripción — {nombre_original}',
        '',
        f'**Formato:** {formato}  ',
        f'**Idioma:** {idioma_md}  ',
        '',
        '---',
        '',
        texto,
        '',
    ]
    contenido_md = '\n'.join(lineas)

    job_manager.actualizar_progreso(trabajo_id, 93, "Guardando archivo")

    ruta_md = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_base}.md"
    with open(ruta_md, 'w', encoding='utf-8') as f:
        f.write(contenido_md)

    return {
        'ruta_resultado': str(ruta_md),
        'mensaje': f'Transcripción completada: {len(texto)} caracteres'
    }


job_manager.registrar_procesador('audio-to-md', procesar_audio_to_md)
