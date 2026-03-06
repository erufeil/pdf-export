# -*- coding: utf-8 -*-
"""
Servicio de extraccion de imagenes de PDF para PDFexport.
Extrae las imagenes incrustadas en un documento PDF.
"""

import logging
from pathlib import Path
from typing import Dict, List, Tuple
from io import BytesIO

import fitz  # PyMuPDF
from PIL import Image

import config
import models
from utils import file_manager, job_manager

logger = logging.getLogger(__name__)


def contar_imagenes_pdf(ruta_pdf: Path) -> int:
    """
    Cuenta el numero de imagenes en un PDF.

    Args:
        ruta_pdf: Ruta al archivo PDF

    Returns:
        Numero total de imagenes
    """
    doc = fitz.open(str(ruta_pdf))
    total_imagenes = 0

    for pagina in doc:
        imagenes = pagina.get_images(full=True)
        total_imagenes += len(imagenes)

    doc.close()
    return total_imagenes


def extraer_imagenes_pdf(ruta_pdf: Path, opciones: Dict, trabajo_id: str, nombre_original: str = None) -> List[Tuple[Path, str]]:
    """
    Extrae todas las imagenes de un PDF.

    Args:
        ruta_pdf: Ruta al archivo PDF
        opciones: Opciones de extraccion
        trabajo_id: ID del trabajo para progreso
        nombre_original: Nombre original del archivo (con extension)

    Returns:
        Lista de tuplas (ruta_imagen, nombre_archivo)
    """
    formato_salida = opciones.get('formato_salida', 'original')
    tamano_minimo = opciones.get('tamano_minimo_px', 50)

    doc = fitz.open(str(ruta_pdf))
    num_paginas = len(doc)
    imagenes_extraidas = []
    contador_imagen = 0

    # Usar nombre original con extension, o nombre del archivo si no se proporciona
    nombre_base = nombre_original if nombre_original else ruta_pdf.name

    job_manager.actualizar_progreso(trabajo_id, 5, "Analizando documento")

    # Primero contar total de imagenes para progreso
    total_imagenes = sum(len(pagina.get_images(full=True)) for pagina in doc)

    if total_imagenes == 0:
        doc.close()
        return []

    imagenes_procesadas = 0

    for num_pag, pagina in enumerate(doc):
        lista_imagenes = pagina.get_images(full=True)

        for img_info in lista_imagenes:
            imagenes_procesadas += 1
            progreso = 10 + int((imagenes_procesadas / total_imagenes) * 80)
            job_manager.actualizar_progreso(
                trabajo_id, progreso,
                f"Extrayendo imagen {imagenes_procesadas} de {total_imagenes}"
            )

            try:
                xref = img_info[0]
                imagen_base = doc.extract_image(xref)

                if not imagen_base:
                    continue

                img_bytes = imagen_base["image"]
                ext_original = imagen_base["ext"]
                ancho = imagen_base.get("width", 0)
                alto = imagen_base.get("height", 0)

                # Filtrar por tamano minimo
                if ancho < tamano_minimo or alto < tamano_minimo:
                    continue

                contador_imagen += 1

                # Determinar extension de salida
                if formato_salida == 'original':
                    ext = ext_original
                elif formato_salida == 'png':
                    ext = 'png'
                elif formato_salida == 'jpg':
                    ext = 'jpg'
                else:
                    ext = ext_original

                # Nombre del archivo con formato: "nombre_original - imagen XXX.ext"
                padding = len(str(total_imagenes))
                nombre_imagen = str(contador_imagen).zfill(padding)
                nombre_archivo = f"{nombre_base} - imagen {nombre_imagen}.{ext}"
                ruta_imagen = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_archivo}"

                # Convertir formato si es necesario
                if formato_salida != 'original' and ext != ext_original:
                    # Usar PIL para convertir
                    img_pil = Image.open(BytesIO(img_bytes))

                    # Convertir a RGB si es necesario (para JPG)
                    if ext == 'jpg' and img_pil.mode in ('RGBA', 'P'):
                        img_pil = img_pil.convert('RGB')

                    # Guardar en nuevo formato
                    if ext == 'jpg':
                        img_pil.save(str(ruta_imagen), 'JPEG', quality=85)
                    else:
                        img_pil.save(str(ruta_imagen), ext.upper())
                else:
                    # Guardar imagen original
                    with open(ruta_imagen, 'wb') as f:
                        f.write(img_bytes)

                imagenes_extraidas.append((ruta_imagen, nombre_archivo))

            except Exception as e:
                logger.warning(f"Error extrayendo imagen de pagina {num_pag + 1}: {e}")
                continue

    doc.close()
    return imagenes_extraidas


def procesar_extract_images(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal de extraccion de imagenes.
    Esta funcion es llamada por el job_manager.

    Args:
        trabajo_id: ID del trabajo
        archivo_id: ID del archivo a procesar
        parametros: Opciones de extraccion

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
    job_manager.actualizar_progreso(trabajo_id, 2, "Iniciando extraccion de imagenes")

    # Extraer imagenes
    imagenes = extraer_imagenes_pdf(ruta_pdf, parametros, trabajo_id, nombre_original)

    if not imagenes:
        raise ValueError("No se encontraron imagenes en el documento")

    job_manager.actualizar_progreso(trabajo_id, 92, "Comprimiendo archivos")

    # Crear ZIP
    nombre_base = Path(archivo['nombre_original']).stem
    nombre_zip = f"{trabajo_id}_{nombre_base}_imagenes.zip"

    archivos_para_zip = [(str(ruta), nombre) for ruta, nombre in imagenes]
    ruta_zip = file_manager.crear_zip(archivos_para_zip, nombre_zip)

    # Limpiar archivos temporales
    for ruta, _ in imagenes:
        if ruta.exists():
            ruta.unlink()

    return {
        'ruta_resultado': str(ruta_zip),
        'mensaje': f'{len(imagenes)} imagenes extraidas'
    }


def obtener_conteo_imagenes(archivo_id: str) -> dict:
    """
    Obtiene el conteo de imagenes en un PDF.

    Args:
        archivo_id: ID del archivo

    Returns:
        dict con informacion de imagenes
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo fisico no encontrado")

    num_imagenes = contar_imagenes_pdf(ruta_pdf)

    return {
        'num_imagenes': num_imagenes
    }


# Registrar el procesador en el job_manager
job_manager.registrar_procesador('extract-images', procesar_extract_images)
