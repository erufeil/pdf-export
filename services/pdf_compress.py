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
    Comprime un archivo PDF.

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
        # Configuracion personalizada
        dpi_maximo = opciones.get('dpi_maximo', 120)
        calidad_jpg = opciones.get('calidad_jpg', 75)

    eliminar_metadatos = opciones.get('eliminar_metadatos', False)
    eliminar_anotaciones = opciones.get('eliminar_anotaciones', False)
    eliminar_bookmarks = opciones.get('eliminar_bookmarks', False)
    escala_grises = opciones.get('escala_grises', False)

    job_manager.actualizar_progreso(trabajo_id, 5, "Analizando documento")

    # Abrir documento original
    doc = fitz.open(str(ruta_pdf))
    num_paginas = len(doc)

    # Crear nuevo documento para el resultado
    nuevo_doc = fitz.open()

    imagenes_procesadas = 0
    total_imagenes = 0

    # Contar imagenes primero para progreso
    for pagina in doc:
        total_imagenes += len(pagina.get_images(full=True))

    job_manager.actualizar_progreso(
        trabajo_id, 10,
        f"Procesando {num_paginas} paginas con {total_imagenes} imagenes"
    )

    # Procesar cada pagina
    for num_pag in range(num_paginas):
        progreso = 10 + int((num_pag / num_paginas) * 70)
        job_manager.actualizar_progreso(
            trabajo_id, progreso,
            f"Procesando pagina {num_pag + 1} de {num_paginas}"
        )

        pagina_original = doc[num_pag]

        # Insertar pagina en el nuevo documento
        nuevo_doc.insert_pdf(doc, from_page=num_pag, to_page=num_pag)
        pagina_nueva = nuevo_doc[num_pag]

        # Eliminar anotaciones si se solicita
        if eliminar_anotaciones:
            for annot in list(pagina_nueva.annots() or []):
                pagina_nueva.delete_annot(annot)

        # Procesar imagenes de la pagina
        lista_imagenes = pagina_original.get_images(full=True)

        for img_info in lista_imagenes:
            try:
                xref = img_info[0]

                # Obtener imagen original
                imagen_base = doc.extract_image(xref)
                if not imagen_base:
                    continue

                img_bytes = imagen_base["image"]
                ext = imagen_base["ext"]
                ancho = imagen_base.get("width", 0)
                alto = imagen_base.get("height", 0)

                # Calcular si necesita redimension basada en DPI
                # Asumimos que el PDF tiene 72 DPI base
                factor_escala = dpi_maximo / 150  # Factor relativo a 150 DPI

                if factor_escala < 1:
                    nuevo_ancho = int(ancho * factor_escala)
                    nuevo_alto = int(alto * factor_escala)

                    # Solo redimensionar si hay reduccion significativa
                    if nuevo_ancho > 50 and nuevo_alto > 50:
                        try:
                            img = Image.open(BytesIO(img_bytes))

                            if escala_grises:
                                img = img.convert('L')
                            elif img.mode == 'RGBA':
                                img = img.convert('RGB')
                            elif img.mode not in ('RGB', 'L'):
                                img = img.convert('RGB')

                            img = img.resize((nuevo_ancho, nuevo_alto), Image.LANCZOS)

                            buffer = BytesIO()
                            img.save(buffer, format='JPEG', quality=calidad_jpg, optimize=True)
                            img_bytes = buffer.getvalue()
                            ext = 'jpeg'

                        except Exception as e:
                            logger.warning(f"Error redimensionando imagen: {e}")

                else:
                    # Solo recomprimir sin redimensionar
                    img_bytes = comprimir_imagen(img_bytes, ext, calidad_jpg, escala_grises)

                imagenes_procesadas += 1

            except Exception as e:
                logger.warning(f"Error procesando imagen en pagina {num_pag + 1}: {e}")

    # Eliminar metadatos si se solicita
    if eliminar_metadatos:
        nuevo_doc.set_metadata({})

    # Eliminar bookmarks/TOC si se solicita
    if eliminar_bookmarks:
        nuevo_doc.set_toc([])

    job_manager.actualizar_progreso(trabajo_id, 85, "Optimizando y guardando")

    # Guardar con opciones de compresion
    nombre_salida = f"{trabajo_id}_{nombre_original} - comprimido.pdf"
    ruta_salida = config.OUTPUT_FOLDER / nombre_salida

    # Guardar con garbage collection y compresion
    nuevo_doc.save(
        str(ruta_salida),
        garbage=4,           # Maxima limpieza de objetos no usados
        deflate=True,        # Compresion deflate
        clean=True,          # Limpiar contenido
        linear=True          # Linearizar para web
    )

    nuevo_doc.close()
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
