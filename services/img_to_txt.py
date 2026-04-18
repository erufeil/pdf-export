# -*- coding: utf-8 -*-
"""
Etapa 24 — Imagen a TXT via OCR usando Apache Tika.

Flujo:
  Imagen (JPG/PNG/TIFF/BMP/GIF/WEBP) → PUT /tika (Accept: text/plain) → TXT

Tika delega el OCR a Tesseract. El resultado es texto plano con el
contenido reconocido de la imagen.

Retorna el TXT directamente (sin ZIP), igual que webp-to-png.
"""

import logging
from pathlib import Path

import config
import models
from utils import job_manager

logger = logging.getLogger(__name__)

# Tipos MIME reconocidos por Tika + Tesseract
MIME_POR_EXTENSION = {
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png':  'image/png',
    '.tiff': 'image/tiff',
    '.tif':  'image/tiff',
    '.bmp':  'image/bmp',
    '.gif':  'image/gif',
    '.webp': 'image/webp',
}


def _url_tika() -> str:
    """Retorna la URL base de Tika con esquema asegurado."""
    url = config.TIKA_URL.rstrip('/')
    if url and not url.startswith(('http://', 'https://')):
        url = f'http://{url}'
    return url


def verificar_tika_img() -> dict:
    """
    Verifica disponibilidad de Apache Tika.
    Retorna dict con 'tika_disponible' y 'mensaje'.
    """
    import requests as _req
    url = _url_tika()
    if not url:
        return {'tika_disponible': False, 'mensaje': 'TIKA_URL no configurada'}
    try:
        r = _req.get(f'{url}/', timeout=5)
        if r.status_code == 200:
            return {'tika_disponible': True, 'mensaje': 'Apache Tika disponible'}
        return {'tika_disponible': False, 'mensaje': f'Tika respondió HTTP {r.status_code}'}
    except Exception:
        return {'tika_disponible': False, 'mensaje': 'Tika no alcanzable — verificar que el servicio esté activo'}


def _enviar_imagen_tika(ruta_imagen: Path, mime_type: str, idioma_ocr: str) -> str:
    """
    Envia la imagen a Tika y obtiene el texto plano resultante.

    PUT /tika con:
      - Content-Type: image/jpeg (o el MIME correspondiente)
      - Accept: text/plain
      - X-Tika-OCRLanguage: spa (u otro idioma)

    Retorna el texto extraído, o lanza excepción si falla.
    """
    import requests as _req

    url_tika = f'{_url_tika()}/tika'
    headers = {
        'Content-Type':       mime_type,
        'Accept':             'text/plain',
        'X-Tika-OCRLanguage': idioma_ocr,
    }

    logger.info(f'[img-txt] Enviando {ruta_imagen.name} a Tika ({url_tika}), '
                f'mime={mime_type}, idioma={idioma_ocr}')

    with open(str(ruta_imagen), 'rb') as f_img:
        resp = _req.put(
            url_tika,
            headers=headers,
            data=f_img,
            timeout=300,  # 5 min — suficiente para una imagen
        )

    logger.info(f'[img-txt] Tika respuesta: HTTP {resp.status_code}, {len(resp.content)} bytes')
    resp.raise_for_status()
    return resp.content.decode('utf-8')


def procesar_img_to_txt(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal registrado en job_manager como 'img-to-txt'.
    Extrae texto de una imagen usando Tika + Tesseract OCR.

    parametros esperados:
      idioma_ocr: codigo de idioma Tesseract (default 'spa')
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError('Archivo no encontrado')

    ruta_img = Path(archivo['ruta_archivo'])
    nombre_original = archivo['nombre_original']

    if not ruta_img.exists():
        raise FileNotFoundError(f'Archivo no encontrado en disco: {ruta_img.name}')

    # Determinar MIME type segun extension
    ext = ruta_img.suffix.lower()
    mime_type = MIME_POR_EXTENSION.get(ext)
    if not mime_type:
        raise ValueError(f'Formato no soportado: {ext}. '
                         f'Use: {", ".join(MIME_POR_EXTENSION.keys())}')

    idioma_ocr = parametros.get('idioma_ocr', 'spa')

    job_manager.actualizar_progreso(trabajo_id, 10, 'Verificando servicio OCR...')

    # Verificar Tika disponible antes de enviar
    estado_tika = verificar_tika_img()
    if not estado_tika['tika_disponible']:
        raise ConnectionError(f'Apache Tika no disponible: {estado_tika["mensaje"]}')

    job_manager.actualizar_progreso(trabajo_id, 20, f'Enviando imagen a Tika (idioma: {idioma_ocr})...')

    try:
        texto_extraido = _enviar_imagen_tika(ruta_img, mime_type, idioma_ocr)
    except Exception as exc:
        logger.error(f'[img-txt] Error en Tika: {exc}')
        raise ValueError(f'Error al procesar imagen con OCR: {exc}')

    job_manager.actualizar_progreso(trabajo_id, 80, 'Guardando resultado...')

    # Limpiar texto: remover líneas completamente vacías consecutivas
    lineas = texto_extraido.splitlines()
    lineas_limpias = []
    linea_vacia_previa = False
    for linea in lineas:
        if linea.strip() == '':
            if not linea_vacia_previa:
                lineas_limpias.append('')
            linea_vacia_previa = True
        else:
            lineas_limpias.append(linea)
            linea_vacia_previa = False
    texto_limpio = '\n'.join(lineas_limpias).strip()

    if not texto_limpio:
        logger.warning(f'[img-txt] Tika no extrajo texto de {nombre_original}')
        texto_limpio = '(No se detectó texto en la imagen)'

    # Guardar TXT
    nombre_base = Path(nombre_original).stem
    nombre_txt  = f'{trabajo_id}_{nombre_base}.txt'
    ruta_txt    = config.OUTPUT_FOLDER / nombre_txt

    # UTF-8 BOM para compatibilidad con Notepad/Excel en Windows
    with open(str(ruta_txt), 'w', encoding='utf-8-sig', newline='\r\n') as f:
        f.write(texto_limpio)

    num_lineas    = texto_limpio.count('\n') + 1
    num_caracteres = len(texto_limpio)
    logger.info(f'[img-txt] {nombre_original} → {nombre_txt} '
                f'({num_lineas} líneas, {num_caracteres} caracteres)')

    return {
        'ruta_resultado': str(ruta_txt),
        'mensaje': f'"{nombre_original}" procesado — {num_lineas} líneas extraídas',
    }


# Registrar procesador
job_manager.registrar_procesador('img-to-txt', procesar_img_to_txt)
