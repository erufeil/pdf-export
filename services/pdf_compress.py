# -*- coding: utf-8 -*-
"""
Servicio de compresion de PDF para PDFexport.
Reduce el tamano del PDF comprimiendo imagenes y optimizando estructura.
"""

import logging
from pathlib import Path
from typing import Dict
from io import BytesIO

import fitz  # PyMuPDF
from PIL import Image

import config
import models
from utils import file_manager, job_manager

logger = logging.getLogger(__name__)

# Niveles de compresion predefinidos
NIVELES_COMPRESION = {
    'baja': {
        'dpi_maximo': 150,
        'calidad_jpg': 90,
        'descripcion': 'Mejor calidad, menor reduccion'
    },
    'media': {
        'dpi_maximo': 120,
        'calidad_jpg': 75,
        'descripcion': 'Equilibrado'
    },
    'alta': {
        'dpi_maximo': 96,
        'calidad_jpg': 60,
        'descripcion': 'Maxima reduccion'
    }
}


def comprimir_imagen(imagen_bytes: bytes, formato: str, calidad: int, escala_grises: bool = False) -> bytes:
    """
    Comprime una imagen usando PIL.

    Args:
        imagen_bytes: Bytes de la imagen original
        formato: Formato de la imagen (jpeg, png, etc)
        calidad: Calidad de compresion (1-100)
        escala_grises: Convertir a escala de grises

    Returns:
        Bytes de la imagen comprimida
    """
    try:
        img = Image.open(BytesIO(imagen_bytes))

        # Convertir a escala de grises si se solicita
        if escala_grises:
            img = img.convert('L')
        elif img.mode == 'RGBA':
            # Convertir RGBA a RGB para JPEG
            img = img.convert('RGB')
        elif img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')

        # Guardar con compresion
        buffer = BytesIO()
        if formato.lower() in ('jpg', 'jpeg'):
            img.save(buffer, format='JPEG', quality=calidad, optimize=True)
        elif formato.lower() == 'png':
            img.save(buffer, format='PNG', optimize=True)
        else:
            # Para otros formatos, convertir a JPEG
            img.save(buffer, format='JPEG', quality=calidad, optimize=True)

        return buffer.getvalue()

    except Exception as e:
        logger.warning(f"No se pudo comprimir imagen: {e}")
        return imagen_bytes


def comprimir_pdf(ruta_pdf: Path, opciones: Dict, trabajo_id: str, nombre_original: str) -> Path:
    """
    Comprime un archivo PDF reemplazando imagenes con versiones comprimidas.

    Trabaja directamente sobre el documento, reemplazando cada imagen
    por su version comprimida/redimensionada usando PyMuPDF.

    Args:
        ruta_pdf: Ruta al archivo PDF original
        opciones: Opciones de compresion
        trabajo_id: ID del trabajo para progreso
        nombre_original: Nombre original del archivo

    Returns:
        Ruta al PDF comprimido
    """
    # Obtener configuracion segun nivel o personalizada
    nivel = opciones.get('nivel', 'media')

    if nivel in NIVELES_COMPRESION:
        dpi_maximo = NIVELES_COMPRESION[nivel]['dpi_maximo']
        calidad_jpg = NIVELES_COMPRESION[nivel]['calidad_jpg']
    else:
        dpi_maximo = opciones.get('dpi_maximo', 120)
        calidad_jpg = opciones.get('calidad_jpg', 75)

    eliminar_metadatos = opciones.get('eliminar_metadatos', False)
    eliminar_anotaciones = opciones.get('eliminar_anotaciones', False)
    eliminar_bookmarks = opciones.get('eliminar_bookmarks', False)
    escala_grises = opciones.get('escala_grises', False)

    job_manager.actualizar_progreso(trabajo_id, 5, "Analizando documento")

    # Abrir documento - trabajamos sobre el mismo documento
    doc = fitz.open(str(ruta_pdf))
    num_paginas = len(doc)

    # Recopilar todos los xrefs de imagenes unicos del documento
    # (una imagen puede aparecer en multiples paginas con el mismo xref)
    xrefs_procesados = set()
    xrefs_imagenes = []

    for pagina in doc:
        for img_info in pagina.get_images(full=True):
            xref = img_info[0]
            if xref not in xrefs_procesados:
                xrefs_procesados.add(xref)
                xrefs_imagenes.append(xref)

    total_imagenes = len(xrefs_imagenes)
    imagenes_procesadas = 0

    job_manager.actualizar_progreso(
        trabajo_id, 10,
        f"Procesando {total_imagenes} imagenes unicas en {num_paginas} paginas"
    )

    # Procesar cada imagen unica y reemplazarla en el documento
    for xref in xrefs_imagenes:
        try:
            # Extraer imagen original
            imagen_base = doc.extract_image(xref)
            if not imagen_base:
                continue

            img_bytes_original = imagen_base["image"]
            ancho = imagen_base.get("width", 0)
            alto = imagen_base.get("height", 0)

            # Abrir con PIL para procesar
            img = Image.open(BytesIO(img_bytes_original))

            # Convertir a escala de grises si se solicita
            if escala_grises:
                img = img.convert('L')
            elif img.mode == 'RGBA':
                img = img.convert('RGB')
            elif img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')

            # Calcular redimension basada en DPI
            factor_escala = dpi_maximo / 150.0
            if factor_escala < 1.0:
                nuevo_ancho = max(50, int(ancho * factor_escala))
                nuevo_alto = max(50, int(alto * factor_escala))
                img = img.resize((nuevo_ancho, nuevo_alto), Image.LANCZOS)

            # Guardar como JPEG comprimido
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=calidad_jpg, optimize=True)
            img_bytes_nuevo = buffer.getvalue()

            # Solo reemplazar si la imagen nueva es mas chica
            if len(img_bytes_nuevo) < len(img_bytes_original):
                # Crear Pixmap de PyMuPDF desde los bytes JPEG
                nuevo_pixmap = fitz.Pixmap(img_bytes_nuevo)

                # Reemplazar la imagen en la primera pagina que la contenga
                # (al reemplazar por xref, se actualiza en todas las paginas)
                for pagina in doc:
                    imagenes_pagina = [i[0] for i in pagina.get_images(full=True)]
                    if xref in imagenes_pagina:
                        pagina.replace_image(xref, pixmap=nuevo_pixmap)
                        break

            imagenes_procesadas += 1

            # Actualizar progreso
            progreso = 10 + int((imagenes_procesadas / max(total_imagenes, 1)) * 70)
            job_manager.actualizar_progreso(
                trabajo_id, progreso,
                f"Imagen {imagenes_procesadas} de {total_imagenes}"
            )

        except Exception as e:
            logger.warning(f"Error procesando imagen xref={xref}: {e}")
            imagenes_procesadas += 1

    # Eliminar anotaciones de todas las paginas si se solicita
    if eliminar_anotaciones:
        for pagina in doc:
            for annot in list(pagina.annots() or []):
                pagina.delete_annot(annot)

    # Eliminar metadatos si se solicita
    if eliminar_metadatos:
        doc.set_metadata({})

    # Eliminar bookmarks/TOC si se solicita
    if eliminar_bookmarks:
        doc.set_toc([])

    job_manager.actualizar_progreso(trabajo_id, 85, "Optimizando y guardando")

    # Guardar con opciones de optimizacion
    nombre_salida = f"{trabajo_id}_{nombre_original} - comprimido.pdf"
    ruta_salida = config.OUTPUT_FOLDER / nombre_salida

    doc.save(
        str(ruta_salida),
        garbage=4,           # Maxima limpieza de objetos no usados
        deflate=True,        # Compresion deflate
        clean=True,          # Limpiar contenido
    )

    doc.close()

    return ruta_salida


def obtener_info_compresion(archivo_id: str) -> Dict:
    """
    Obtiene informacion del archivo para estimar compresion.

    Args:
        archivo_id: ID del archivo

    Returns:
        dict con informacion del archivo
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo fisico no encontrado")

    tamano_actual = ruta_pdf.stat().st_size

    # Abrir para obtener mas info
    doc = fitz.open(str(ruta_pdf))
    num_paginas = len(doc)

    # Contar imagenes y estimar potencial de compresion
    total_imagenes = 0
    tamano_imagenes = 0

    for pagina in doc:
        for img_info in pagina.get_images(full=True):
            try:
                xref = img_info[0]
                imagen = doc.extract_image(xref)
                if imagen:
                    total_imagenes += 1
                    tamano_imagenes += len(imagen.get("image", b""))
            except:
                pass

    doc.close()

    # Estimar reduccion potencial
    # Si hay muchas imagenes, la reduccion puede ser mayor
    porcentaje_imagenes = (tamano_imagenes / tamano_actual * 100) if tamano_actual > 0 else 0

    return {
        'tamano_actual': tamano_actual,
        'tamano_actual_texto': file_manager.formatear_tamano(tamano_actual),
        'num_paginas': num_paginas,
        'total_imagenes': total_imagenes,
        'porcentaje_imagenes': round(porcentaje_imagenes, 1),
        'estimaciones': {
            'baja': {
                'tamano': int(tamano_actual * 0.7),
                'tamano_texto': file_manager.formatear_tamano(int(tamano_actual * 0.7)),
                'reduccion': 30
            },
            'media': {
                'tamano': int(tamano_actual * 0.5),
                'tamano_texto': file_manager.formatear_tamano(int(tamano_actual * 0.5)),
                'reduccion': 50
            },
            'alta': {
                'tamano': int(tamano_actual * 0.3),
                'tamano_texto': file_manager.formatear_tamano(int(tamano_actual * 0.3)),
                'reduccion': 70
            }
        }
    }


def procesar_compress(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal de compresion de PDF.
    Esta funcion es llamada por el job_manager.

    Args:
        trabajo_id: ID del trabajo
        archivo_id: ID del archivo a procesar
        parametros: Opciones de compresion

    Returns:
        dict con ruta_resultado y mensaje
    """
    # Obtener archivo
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo fisico no encontrado")

    nombre_original = archivo['nombre_original']
    tamano_original = ruta_pdf.stat().st_size

    job_manager.actualizar_progreso(trabajo_id, 2, "Iniciando compresion")

    # Comprimir
    ruta_comprimido = comprimir_pdf(ruta_pdf, parametros, trabajo_id, nombre_original)

    # Calcular reduccion
    tamano_final = ruta_comprimido.stat().st_size
    reduccion = ((tamano_original - tamano_final) / tamano_original * 100) if tamano_original > 0 else 0

    job_manager.actualizar_progreso(trabajo_id, 95, "Finalizando")

    return {
        'ruta_resultado': str(ruta_comprimido),
        'mensaje': f'PDF comprimido: {file_manager.formatear_tamano(tamano_original)} -> {file_manager.formatear_tamano(tamano_final)} (reduccion del {reduccion:.1f}%)'
    }


# Registrar el procesador en el job_manager
job_manager.registrar_procesador('compress', procesar_compress)
