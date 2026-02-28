# -*- coding: utf-8 -*-
"""
Servicio de reordenamiento de paginas PDF para PDFexport.
Permite cambiar el orden de las paginas de un PDF mediante una lista de posiciones.
"""

import logging
from pathlib import Path
from typing import List

import fitz  # PyMuPDF

import config
import models
from utils import file_manager, job_manager

logger = logging.getLogger(__name__)


def reordenar_paginas_pdf(ruta_pdf: Path, nuevo_orden: List[int],
                          trabajo_id: str, nombre_original: str) -> Path:
    """
    Crea un nuevo PDF con las paginas en el orden indicado.

    Args:
        ruta_pdf: Ruta al archivo PDF original
        nuevo_orden: Lista de numeros de pagina (1-indexed) en el nuevo orden deseado.
                     Ejemplo: [3, 1, 2] → pagina 3 primero, luego 1, luego 2.
        trabajo_id: ID del trabajo para reportar progreso
        nombre_original: Nombre original del archivo (con extension)

    Returns:
        Ruta al nuevo PDF reordenado
    """
    job_manager.actualizar_progreso(trabajo_id, 5, "Abriendo documento")

    doc_original = fitz.open(str(ruta_pdf))
    num_paginas = len(doc_original)

    # Filtrar valores invalidos y convertir a 0-indexed para PyMuPDF
    indices_validos = []
    for num_pag in nuevo_orden:
        if 1 <= num_pag <= num_paginas:
            indices_validos.append(num_pag - 1)
        else:
            logger.warning(f"Pagina {num_pag} fuera de rango ({num_paginas} paginas), ignorada")

    if not indices_validos:
        doc_original.close()
        raise ValueError("Ninguna pagina del nuevo orden es valida")

    total = len(indices_validos)
    job_manager.actualizar_progreso(trabajo_id, 10, f"Reordenando {total} paginas")

    # Crear nuevo documento insertando paginas en el orden indicado
    nuevo_doc = fitz.open()
    for i, idx in enumerate(indices_validos):
        nuevo_doc.insert_pdf(doc_original, from_page=idx, to_page=idx)

        progreso = 10 + int((i / total) * 80)
        job_manager.actualizar_progreso(
            trabajo_id, progreso,
            f"Copiando pagina {i + 1} de {total}"
        )

    job_manager.actualizar_progreso(trabajo_id, 92, "Guardando documento")

    nombre_salida = f"{trabajo_id}_{nombre_original} - reordenado.pdf"
    ruta_salida = config.OUTPUT_FOLDER / nombre_salida

    nuevo_doc.save(str(ruta_salida))
    nuevo_doc.close()
    doc_original.close()

    logger.info(f"PDF reordenado guardado: {nombre_salida} ({total} paginas)")
    return ruta_salida


def procesar_reorder(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal de reordenamiento de paginas.
    Llamado por el job_manager.

    Args:
        trabajo_id: ID del trabajo
        archivo_id: ID del archivo PDF a procesar
        parametros:
            - nuevo_orden: Lista de numeros de pagina (1-indexed) en el orden deseado

    Returns:
        dict con ruta_resultado y mensaje
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo fisico no encontrado")

    nuevo_orden = parametros.get('nuevo_orden', [])
    if not nuevo_orden:
        raise ValueError("Debe proporcionar el nuevo orden de paginas")

    num_paginas = archivo['num_paginas']
    nombre_original = archivo['nombre_original']

    job_manager.actualizar_progreso(trabajo_id, 2, "Validando orden de paginas")

    # Ejecutar reordenamiento
    ruta_resultado = reordenar_paginas_pdf(
        ruta_pdf, nuevo_orden, trabajo_id, nombre_original
    )

    # Empaquetar en ZIP
    job_manager.actualizar_progreso(trabajo_id, 95, "Comprimiendo resultado")

    nombre_base_sin_ext = Path(nombre_original).stem
    nombre_zip = f"{trabajo_id}_{nombre_base_sin_ext}_reordenado.zip"

    archivos_para_zip = [(str(ruta_resultado), ruta_resultado.name.replace(f"{trabajo_id}_", ""))]
    ruta_zip = file_manager.crear_zip(archivos_para_zip, nombre_zip)

    # Limpiar archivo temporal
    if ruta_resultado.exists():
        ruta_resultado.unlink()

    return {
        'ruta_resultado': str(ruta_zip),
        'mensaje': f'PDF reordenado con {len(nuevo_orden)} paginas'
    }


# Registrar procesador en el job_manager
job_manager.registrar_procesador('reorder', procesar_reorder)
