# -*- coding: utf-8 -*-
"""
Gestor de archivos para PDFexport.
Maneja subida, almacenamiento y limpieza de archivos.
"""

import os
import hashlib
import uuid
import shutil
import zipfile
import logging
from pathlib import Path
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

import fitz  # PyMuPDF

import config
import models

logger = logging.getLogger(__name__)


def extension_permitida(nombre_archivo: str) -> bool:
    """Verifica si la extension del archivo esta permitida."""
    return '.' in nombre_archivo and \
           nombre_archivo.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS


def sanitizar_nombre(nombre: str) -> str:
    """
    Sanitiza el nombre del archivo para evitar problemas de seguridad.
    Usa secure_filename de Werkzeug y agrega UUID para unicidad.
    """
    nombre_seguro = secure_filename(nombre)
    if not nombre_seguro:
        nombre_seguro = 'archivo.pdf'
    return nombre_seguro


def generar_hash_archivo(ruta: Path) -> str:
    """Genera hash MD5 del archivo para detectar duplicados."""
    hash_md5 = hashlib.md5()
    with open(ruta, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def obtener_info_pdf(ruta: Path) -> dict:
    """
    Obtiene informacion del PDF usando PyMuPDF.
    Retorna numero de paginas y metadatos basicos.
    """
    try:
        doc = fitz.open(str(ruta))
        info = {
            'num_paginas': len(doc),
            'metadata': doc.metadata,
            'es_encriptado': doc.is_encrypted
        }
        doc.close()
        return info
    except Exception as e:
        logger.error(f"Error al leer PDF {ruta}: {e}")
        return {'num_paginas': 0, 'metadata': {}, 'es_encriptado': False}


def guardar_archivo(archivo, nombre_original: str, fecha_modificacion: str = None) -> dict:
    """
    Guarda un archivo subido y lo registra en la base de datos.

    Args:
        archivo: Objeto FileStorage de Flask
        nombre_original: Nombre original del archivo
        fecha_modificacion: Fecha de modificacion del archivo (ISO format)

    Returns:
        dict con informacion del archivo guardado o None si hay error
    """
    # Sanitizar nombre
    nombre_seguro = sanitizar_nombre(nombre_original)

    # Generar nombre unico para almacenamiento
    archivo_id = str(uuid.uuid4())
    extension = nombre_seguro.rsplit('.', 1)[1].lower() if '.' in nombre_seguro else 'pdf'
    nombre_guardado = f"{archivo_id}.{extension}"
    ruta_destino = config.UPLOAD_FOLDER / nombre_guardado

    try:
        # Guardar archivo temporalmente
        archivo.save(str(ruta_destino))

        # Obtener tamanio
        tamano_bytes = ruta_destino.stat().st_size

        # Verificar tamanio maximo
        if tamano_bytes > config.MAX_CONTENT_LENGTH:
            ruta_destino.unlink()
            logger.warning(f"Archivo muy grande: {tamano_bytes} bytes")
            return None

        # Obtener info del PDF
        info_pdf = obtener_info_pdf(ruta_destino)

        # Generar hash para detectar duplicados
        hash_archivo = generar_hash_archivo(ruta_destino)

        # Registrar en base de datos
        nuevo_id = models.crear_archivo(
            nombre_original=nombre_original,
            nombre_guardado=nombre_guardado,
            tamano_bytes=tamano_bytes,
            fecha_modificacion=fecha_modificacion or datetime.now().isoformat(),
            ruta_archivo=str(ruta_destino),
            hash_archivo=hash_archivo,
            num_paginas=info_pdf['num_paginas']
        )

        logger.info(f"Archivo guardado: {nombre_original} ({tamano_bytes} bytes, {info_pdf['num_paginas']} paginas)")

        return {
            'id': nuevo_id,
            'nombre_original': nombre_original,
            'nombre_guardado': nombre_guardado,
            'tamano_bytes': tamano_bytes,
            'num_paginas': info_pdf['num_paginas'],
            'ruta': str(ruta_destino)
        }

    except Exception as e:
        logger.error(f"Error al guardar archivo: {e}")
        if ruta_destino.exists():
            ruta_destino.unlink()
        return None


def buscar_archivo_duplicado(nombre: str, tamano: int, fecha_mod: str) -> dict:
    """
    Busca si ya existe un archivo identico en el servidor.
    Retorna info del archivo si existe, None si no.
    """
    archivo_existente = models.buscar_archivo_existente(nombre, tamano, fecha_mod)

    if archivo_existente:
        # Verificar que el archivo fisico existe
        ruta = Path(archivo_existente['ruta_archivo'])
        if ruta.exists():
            logger.info(f"Archivo duplicado encontrado: {nombre}")
            return archivo_existente
        else:
            # El registro existe pero el archivo no, eliminar registro
            models.eliminar_archivo(archivo_existente['id'])

    return None


def eliminar_archivo_fisico(archivo_id: str) -> bool:
    """
    Elimina un archivo del sistema de archivos y de la base de datos.
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        return False

    ruta = Path(archivo['ruta_archivo'])

    try:
        if ruta.exists():
            ruta.unlink()
            logger.info(f"Archivo fisico eliminado: {ruta}")

        models.eliminar_archivo(archivo_id)
        return True

    except Exception as e:
        logger.error(f"Error al eliminar archivo {archivo_id}: {e}")
        return False


def crear_zip(archivos: list, nombre_zip: str) -> Path:
    """
    Crea un archivo ZIP con maxima compresion.

    Args:
        archivos: Lista de tuplas (ruta_archivo, nombre_en_zip)
        nombre_zip: Nombre del archivo ZIP resultante

    Returns:
        Path al archivo ZIP creado
    """
    ruta_zip = config.OUTPUT_FOLDER / nombre_zip

    with zipfile.ZipFile(str(ruta_zip), 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for ruta_archivo, nombre_en_zip in archivos:
            if Path(ruta_archivo).exists():
                zf.write(ruta_archivo, nombre_en_zip)

    logger.info(f"ZIP creado: {ruta_zip} ({ruta_zip.stat().st_size} bytes)")
    return ruta_zip


def limpiar_archivos_expirados() -> dict:
    """
    Elimina archivos y trabajos que han superado el tiempo de retencion.
    Se ejecuta periodicamente (cada hora).

    Returns:
        dict con cantidad de archivos y trabajos eliminados
    """
    fecha_limite = datetime.now() - timedelta(hours=config.FILE_RETENTION_HOURS)
    archivos_eliminados = 0
    trabajos_eliminados = 0

    # Obtener archivos expirados de la BD
    archivos = models.listar_archivos()

    for archivo in archivos:
        fecha_subida = datetime.fromisoformat(archivo['fecha_subida'])
        if fecha_subida < fecha_limite:
            ruta = Path(archivo['ruta_archivo'])
            if ruta.exists():
                try:
                    ruta.unlink()
                    archivos_eliminados += 1
                except Exception as e:
                    logger.error(f"Error eliminando {ruta}: {e}")

    # Limpiar registros de la BD
    models.eliminar_archivos_expirados()
    trabajos_eliminados = models.eliminar_trabajos_expirados()

    # Limpiar archivos huerfanos en uploads/
    for archivo in config.UPLOAD_FOLDER.iterdir():
        if archivo.is_file():
            edad = datetime.now() - datetime.fromtimestamp(archivo.stat().st_mtime)
            if edad > timedelta(hours=config.FILE_RETENTION_HOURS):
                try:
                    archivo.unlink()
                    archivos_eliminados += 1
                except Exception as e:
                    logger.error(f"Error eliminando huerfano {archivo}: {e}")

    # Limpiar archivos huerfanos en outputs/
    for archivo in config.OUTPUT_FOLDER.iterdir():
        if archivo.is_file():
            edad = datetime.now() - datetime.fromtimestamp(archivo.stat().st_mtime)
            if edad > timedelta(hours=config.FILE_RETENTION_HOURS):
                try:
                    archivo.unlink()
                    archivos_eliminados += 1
                except Exception as e:
                    logger.error(f"Error eliminando huerfano {archivo}: {e}")

    if archivos_eliminados > 0 or trabajos_eliminados > 0:
        logger.info(f"Limpieza: {archivos_eliminados} archivos, {trabajos_eliminados} trabajos eliminados")

    return {
        'archivos_eliminados': archivos_eliminados,
        'trabajos_eliminados': trabajos_eliminados
    }


def generar_miniatura(ruta_pdf: Path, pagina: int = 0) -> bytes:
    """
    Genera una miniatura PNG de una pagina del PDF.

    Args:
        ruta_pdf: Ruta al archivo PDF
        pagina: Numero de pagina (0-indexed)

    Returns:
        Bytes de la imagen PNG
    """
    try:
        doc = fitz.open(str(ruta_pdf))

        if pagina >= len(doc):
            pagina = len(doc) - 1

        pag = doc[pagina]

        # Calcular zoom para el tamanio deseado
        zoom = config.THUMBNAIL_DPI / 72
        matriz = fitz.Matrix(zoom, zoom)

        # Renderizar pagina
        pix = pag.get_pixmap(matrix=matriz)

        # Convertir a PNG
        png_bytes = pix.tobytes("png")

        doc.close()
        return png_bytes

    except Exception as e:
        logger.error(f"Error generando miniatura: {e}")
        return None


def obtener_ruta_archivo(archivo_id: str) -> Path:
    """Obtiene la ruta fisica de un archivo por su ID."""
    archivo = models.obtener_archivo(archivo_id)
    if archivo:
        return Path(archivo['ruta_archivo'])
    return None


def formatear_tamano(tamano_bytes: int) -> str:
    """
    Formatea un tamano en bytes a una cadena legible.

    Args:
        tamano_bytes: Tamano en bytes

    Returns:
        Cadena formateada (ej: "1.5 MB")
    """
    if tamano_bytes == 0:
        return "0 Bytes"

    unidades = ['Bytes', 'KB', 'MB', 'GB', 'TB']
    i = 0
    tamano = float(tamano_bytes)

    while tamano >= 1024 and i < len(unidades) - 1:
        tamano /= 1024
        i += 1

    return f"{tamano:.2f} {unidades[i]}"
