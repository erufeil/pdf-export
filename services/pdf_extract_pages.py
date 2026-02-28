# -*- coding: utf-8 -*-
"""
Servicio de extraccion de paginas especificas de un PDF para PDFexport.
Permite extraer paginas seleccionadas como un unico PDF o archivos separados.
"""

import logging
import zipfile
from pathlib import Path
from typing import List

import fitz  # PyMuPDF

import config
import models
from utils import file_manager, job_manager

logger = logging.getLogger(__name__)


def parsear_paginas(texto: str, num_paginas: int) -> List[int]:
    """
    Convierte un string de seleccion de paginas a lista de numeros.
    Soporta: numeros sueltos, rangos con guion y combinaciones.
    Ejemplos: "1, 3, 5-10, 15" → [1, 3, 5, 6, 7, 8, 9, 10, 15]

    Args:
        texto: String con la seleccion de paginas
        num_paginas: Total de paginas del documento (para validar rango)

    Returns:
        Lista de numeros de pagina ordenados y sin duplicados
    """
    paginas = set()

    for parte in texto.replace(' ', '').split(','):
        if not parte:
            continue
        if '-' in parte:
            # Es un rango: "5-10"
            extremos = parte.split('-', 1)
            try:
                inicio = int(extremos[0])
                fin = int(extremos[1])
                for p in range(inicio, fin + 1):
                    if 1 <= p <= num_paginas:
                        paginas.add(p)
            except (ValueError, IndexError):
                logger.warning(f"Rango invalido ignorado: '{parte}'")
        else:
            # Es un numero suelto
            try:
                p = int(parte)
                if 1 <= p <= num_paginas:
                    paginas.add(p)
            except ValueError:
                logger.warning(f"Numero de pagina invalido ignorado: '{parte}'")

    return sorted(paginas)


def extraer_paginas(ruta_pdf: Path, paginas: List[int], formato_salida: str,
                    trabajo_id: str, nombre_base: str, num_paginas_total: int) -> List[tuple]:
    """
    Extrae las paginas seleccionadas del PDF.

    Args:
        ruta_pdf: Ruta al archivo PDF original
        paginas: Lista de numeros de pagina (1-based) a extraer
        formato_salida: 'unico' (un solo PDF) o 'separados' (un PDF por pagina)
        trabajo_id: ID del trabajo para reportar progreso
        nombre_base: Nombre original del archivo (con extension)
        num_paginas_total: Total de paginas del documento (para padding de ceros)

    Returns:
        Lista de tuplas (ruta_fisica, nombre_en_zip)
    """
    archivos_generados = []
    num_digitos = len(str(num_paginas_total))

    try:
        doc = fitz.open(str(ruta_pdf))

        if formato_salida == 'unico':
            # Un solo PDF con todas las paginas seleccionadas
            job_manager.actualizar_progreso(trabajo_id, 20, "Extrayendo paginas seleccionadas")

            nuevo_doc = fitz.open()
            for num_pag in paginas:
                # fitz usa indices 0-based
                nuevo_doc.insert_pdf(doc, from_page=num_pag - 1, to_page=num_pag - 1)

            # Nombre del archivo: incluye primera y ultima pagina seleccionada
            primera = str(paginas[0]).zfill(num_digitos)
            ultima = str(paginas[-1]).zfill(num_digitos)
            nombre_archivo = f"{nombre_base} - paginas {primera}-{ultima}.pdf"
            ruta_salida = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_archivo}"

            nuevo_doc.save(str(ruta_salida))
            nuevo_doc.close()
            archivos_generados.append((ruta_salida, nombre_archivo))
            logger.info(f"PDF unico generado: {nombre_archivo} ({len(paginas)} paginas)")

        else:
            # Un PDF por pagina
            total = len(paginas)
            num_digitos_paginas = len(str(total))

            for i, num_pag in enumerate(paginas):
                progreso = int(10 + (i / total) * 85)
                job_manager.actualizar_progreso(
                    trabajo_id, progreso,
                    f"Extrayendo pagina {i+1} de {total}"
                )

                nuevo_doc = fitz.open()
                nuevo_doc.insert_pdf(doc, from_page=num_pag - 1, to_page=num_pag - 1)

                # Nombre: "archivo.pdf - pagina 003.pdf"
                num_pag_str = str(num_pag).zfill(num_digitos)
                nombre_archivo = f"{nombre_base} - pagina {num_pag_str}.pdf"
                ruta_salida = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_archivo}"

                nuevo_doc.save(str(ruta_salida))
                nuevo_doc.close()
                archivos_generados.append((ruta_salida, nombre_archivo))

            logger.info(f"Generados {len(paginas)} PDFs individuales")

        doc.close()
        return archivos_generados

    except Exception as e:
        logger.error(f"Error extrayendo paginas: {e}")
        for ruta, _ in archivos_generados:
            if ruta.exists():
                ruta.unlink()
        raise


def procesar_extract_pages(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal de extraccion de paginas.
    Llamado por el job_manager.

    Args:
        trabajo_id: ID del trabajo
        archivo_id: ID del archivo PDF a procesar
        parametros:
            - paginas: Lista de numeros de pagina [1, 3, 5, 6, ...]
            - formato_salida: 'unico' | 'separados'

    Returns:
        dict con ruta_resultado y mensaje
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo fisico no encontrado")

    num_paginas = archivo['num_paginas']
    nombre_base = archivo['nombre_original']

    # Obtener y validar lista de paginas
    paginas = parametros.get('paginas', [])
    if not paginas:
        raise ValueError("Debe seleccionar al menos una pagina")

    # Filtrar paginas fuera de rango y ordenar
    paginas = sorted(set(p for p in paginas if 1 <= p <= num_paginas))
    if not paginas:
        raise ValueError("Ninguna pagina seleccionada es valida para este documento")

    formato_salida = parametros.get('formato_salida', 'unico')
    if formato_salida not in ('unico', 'separados'):
        formato_salida = 'unico'

    job_manager.actualizar_progreso(trabajo_id, 5, f"Preparando extraccion de {len(paginas)} paginas")

    # Extraer paginas
    archivos_generados = extraer_paginas(
        ruta_pdf, paginas, formato_salida,
        trabajo_id, nombre_base, num_paginas
    )

    # Crear ZIP
    job_manager.actualizar_progreso(trabajo_id, 95, "Comprimiendo archivos")

    # Nombre del ZIP descriptivo
    nombre_base_sin_ext = Path(nombre_base).stem
    tipo = 'paginas' if formato_salida == 'unico' else 'paginas_sep'
    nombre_zip = f"{trabajo_id}_{nombre_base_sin_ext}_{tipo}.zip"

    archivos_para_zip = [(str(ruta), nombre) for ruta, nombre in archivos_generados]
    ruta_zip = file_manager.crear_zip(archivos_para_zip, nombre_zip)

    # Limpiar archivos temporales individuales
    for ruta_temp, _ in archivos_generados:
        if ruta_temp.exists():
            ruta_temp.unlink()

    return {
        'ruta_resultado': str(ruta_zip),
        'mensaje': f'{len(paginas)} paginas extraidas correctamente'
    }


# Registrar procesador en el job_manager
job_manager.registrar_procesador('extract-pages', procesar_extract_pages)
