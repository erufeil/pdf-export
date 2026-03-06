# -*- coding: utf-8 -*-
"""
Servicio de conversion de PDF a imagenes (PNG/JPG) para PDFexport.
Usa PyMuPDF (fitz) para el rendering — sin dependencia de poppler,
sin riesgo de cuelgues en paginas problematicas.
"""

import logging
from pathlib import Path
from typing import Dict, List, Tuple

import fitz  # PyMuPDF
from PIL import Image as PILImage

import config
import models
from utils import file_manager, job_manager

logger = logging.getLogger(__name__)

# Configuracion de DPI disponibles
DPI_OPCIONES = {
    72: 'Baja (72 DPI)',
    150: 'Media (150 DPI)',
    300: 'Alta (300 DPI)',
    600: 'Muy Alta (600 DPI)'
}


def parsear_paginas(paginas_str: str, total_paginas: int) -> List[int]:
    """
    Parsea una cadena de paginas a lista de numeros.

    Formatos soportados:
    - "all" -> todas las paginas
    - "1,3,5" -> paginas especificas
    - "1-10" -> rango
    - "1,3,5-10,15" -> combinacion

    Args:
        paginas_str: Cadena con las paginas
        total_paginas: Total de paginas del documento

    Returns:
        Lista de numeros de pagina (1-indexed)
    """
    if not paginas_str or paginas_str.lower() == 'all':
        return list(range(1, total_paginas + 1))

    paginas = set()
    partes = paginas_str.replace(' ', '').split(',')

    for parte in partes:
        if '-' in parte:
            # Rango
            try:
                inicio, fin = parte.split('-')
                inicio = max(1, int(inicio))
                fin = min(total_paginas, int(fin))
                paginas.update(range(inicio, fin + 1))
            except ValueError:
                continue
        else:
            # Pagina individual
            try:
                num = int(parte)
                if 1 <= num <= total_paginas:
                    paginas.add(num)
            except ValueError:
                continue

    return sorted(list(paginas))


def estimar_tamano(num_paginas: int, dpi: int, formato: str = 'png') -> int:
    """
    Estima el tamano aproximado del resultado.

    Args:
        num_paginas: Numero de paginas a convertir
        dpi: DPI de salida
        formato: 'png' o 'jpg'

    Returns:
        Tamano estimado en bytes
    """
    # Estimacion basada en tamano promedio de pagina A4
    # A 150 DPI, una pagina A4 en PNG es aproximadamente 1.5MB
    base_size_png = 1.5 * 1024 * 1024  # 1.5 MB base a 150 DPI

    # Ajustar por DPI (escala cuadratica)
    factor_dpi = (dpi / 150) ** 2

    # JPG es aproximadamente 70% mas pequeno
    factor_formato = 0.3 if formato == 'jpg' else 1.0

    tamano_por_pagina = base_size_png * factor_dpi * factor_formato

    return int(tamano_por_pagina * num_paginas)


def convertir_pdf_a_imagenes(
    ruta_pdf: Path,
    opciones: Dict,
    trabajo_id: str,
    formato: str = 'png',
    nombre_original: str = None
) -> List[Tuple[Path, str]]:
    """
    Convierte un PDF a imagenes usando PyMuPDF (sin poppler).

    Args:
        ruta_pdf: Ruta al archivo PDF
        opciones: Opciones de conversion (dpi, paginas, calidad_jpg)
        trabajo_id: ID del trabajo para progreso
        formato: 'png' o 'jpg'
        nombre_original: Nombre original del archivo (con extension)

    Returns:
        Lista de tuplas (ruta_imagen, nombre_archivo)
    """
    dpi = opciones.get('dpi', 150)
    paginas_str = opciones.get('paginas', 'all')
    calidad_jpg = opciones.get('calidad', 85)  # Solo para JPG

    # PyMuPDF usa una matriz de escala; 72 pt = 1 unidad PDF
    # factor = dpi / 72 convierte a la resolucion deseada
    factor = dpi / 72.0
    matriz = fitz.Matrix(factor, factor)

    doc = fitz.open(str(ruta_pdf))
    total_paginas = len(doc)

    # Parsear paginas a convertir
    paginas = parsear_paginas(paginas_str, total_paginas)
    num_paginas = len(paginas)

    job_manager.actualizar_progreso(
        trabajo_id, 5,
        f"Preparando conversion de {num_paginas} paginas a {formato.upper()} ({dpi} DPI)"
    )

    imagenes_generadas = []
    nombre_base = nombre_original if nombre_original else ruta_pdf.name
    padding = len(str(total_paginas))

    for i, num_pagina in enumerate(paginas):
        progreso = 10 + int((i / num_paginas) * 80)
        job_manager.actualizar_progreso(
            trabajo_id, progreso,
            f"Convirtiendo pagina {num_pagina} de {total_paginas}"
        )

        try:
            # Renderizar pagina con PyMuPDF (0-indexed)
            pagina = doc.load_page(num_pagina - 1)
            pix = pagina.get_pixmap(matrix=matriz, alpha=False)

            # Nombre de salida con padding
            nombre_pagina = str(num_pagina).zfill(padding)
            nombre_archivo = f"{nombre_base} - pagina {nombre_pagina}.{formato}"
            ruta_imagen = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_archivo}"

            if formato == 'jpg':
                # Convertir pixmap a Pillow para guardar como JPEG con calidad
                img_pil = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img_pil.save(str(ruta_imagen), 'JPEG', quality=calidad_jpg, optimize=True)
            else:
                # PNG: guardar directamente con PyMuPDF (mas rapido)
                pix.save(str(ruta_imagen))

            imagenes_generadas.append((ruta_imagen, nombre_archivo))
            logger.debug(f"Pagina {num_pagina} convertida: {nombre_archivo}")

        except Exception as e:
            logger.error(f"Error convirtiendo pagina {num_pagina}: {e}")
            # Continuar con las demas paginas

    doc.close()
    return imagenes_generadas


def procesar_to_png(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal de conversion PDF a PNG.
    Esta funcion es llamada por el job_manager.

    Args:
        trabajo_id: ID del trabajo
        archivo_id: ID del archivo a procesar
        parametros: Opciones de conversion

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
    job_manager.actualizar_progreso(trabajo_id, 2, "Iniciando conversion a PNG")

    # Convertir
    imagenes = convertir_pdf_a_imagenes(ruta_pdf, parametros, trabajo_id, 'png', nombre_original)

    if not imagenes:
        raise ValueError("No se generaron imagenes")

    job_manager.actualizar_progreso(trabajo_id, 92, "Comprimiendo archivos")

    # Crear ZIP
    nombre_base = Path(archivo['nombre_original']).stem
    nombre_zip = f"{trabajo_id}_{nombre_base}_png.zip"

    archivos_para_zip = [(str(ruta), nombre) for ruta, nombre in imagenes]
    ruta_zip = file_manager.crear_zip(archivos_para_zip, nombre_zip)

    # Limpiar archivos temporales
    for ruta, _ in imagenes:
        if ruta.exists():
            ruta.unlink()

    return {
        'ruta_resultado': str(ruta_zip),
        'mensaje': f'{len(imagenes)} imagenes PNG generadas'
    }


def procesar_to_jpg(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal de conversion PDF a JPG.
    Esta funcion es llamada por el job_manager.

    Args:
        trabajo_id: ID del trabajo
        archivo_id: ID del archivo a procesar
        parametros: Opciones de conversion

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
    job_manager.actualizar_progreso(trabajo_id, 2, "Iniciando conversion a JPG")

    # Convertir
    imagenes = convertir_pdf_a_imagenes(ruta_pdf, parametros, trabajo_id, 'jpg', nombre_original)

    if not imagenes:
        raise ValueError("No se generaron imagenes")

    job_manager.actualizar_progreso(trabajo_id, 92, "Comprimiendo archivos")

    # Crear ZIP
    nombre_base = Path(archivo['nombre_original']).stem
    nombre_zip = f"{trabajo_id}_{nombre_base}_jpg.zip"

    archivos_para_zip = [(str(ruta), nombre) for ruta, nombre in imagenes]
    ruta_zip = file_manager.crear_zip(archivos_para_zip, nombre_zip)

    # Limpiar archivos temporales
    for ruta, _ in imagenes:
        if ruta.exists():
            ruta.unlink()

    return {
        'ruta_resultado': str(ruta_zip),
        'mensaje': f'{len(imagenes)} imagenes JPG generadas'
    }


def obtener_info_conversion(archivo_id: str, opciones: dict) -> dict:
    """
    Obtiene informacion para preview de la conversion.

    Args:
        archivo_id: ID del archivo
        opciones: Opciones de conversion

    Returns:
        dict con informacion de la conversion
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo fisico no encontrado")

    # Obtener total de paginas
    doc = fitz.open(str(ruta_pdf))
    total_paginas = len(doc)
    doc.close()

    # Parsear paginas
    paginas_str = opciones.get('paginas', 'all')
    paginas = parsear_paginas(paginas_str, total_paginas)

    dpi = opciones.get('dpi', 150)
    formato = opciones.get('formato', 'png')
    calidad = opciones.get('calidad', 85)

    # Estimar tamano
    tamano_png = estimar_tamano(len(paginas), dpi, 'png')
    tamano_jpg = estimar_tamano(len(paginas), dpi, 'jpg')

    return {
        'total_paginas': total_paginas,
        'paginas_seleccionadas': len(paginas),
        'dpi': dpi,
        'tamano_estimado_png': tamano_png,
        'tamano_estimado_jpg': tamano_jpg,
        'tamano_estimado_png_texto': file_manager.formatear_tamano(tamano_png),
        'tamano_estimado_jpg_texto': file_manager.formatear_tamano(tamano_jpg)
    }


# Registrar los procesadores en el job_manager
job_manager.registrar_procesador('to-png', procesar_to_png)
job_manager.registrar_procesador('to-jpg', procesar_to_jpg)
