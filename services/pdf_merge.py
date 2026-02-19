# -*- coding: utf-8 -*-
"""
Servicio de union de PDFs para PDFexport.
Combina multiples PDFs en uno solo, con opcion de marcadores.
"""

import logging
import zipfile
from pathlib import Path
from typing import List, Dict

import fitz  # PyMuPDF

import config
import models
from utils import job_manager

logger = logging.getLogger(__name__)


def obtener_info_archivos(archivo_ids: List[str]) -> List[Dict]:
    """
    Obtiene informacion de una lista de archivos por sus IDs.

    Args:
        archivo_ids: Lista de IDs de archivos

    Returns:
        Lista de dicts con info de cada archivo (en el mismo orden)
    """
    resultado = []
    for aid in archivo_ids:
        archivo = models.obtener_archivo(aid)
        if archivo:
            resultado.append({
                'id': archivo['id'],
                'nombre_original': archivo['nombre_original'],
                'num_paginas': archivo['num_paginas'],
                'tamano_bytes': archivo['tamano_bytes'],
                'ruta_archivo': archivo['ruta_archivo']
            })
    return resultado


def unir_pdfs(archivos_ordenados: List[Dict], trabajo_id: str, agregar_marcadores: bool) -> Path:
    """
    Une los PDFs en el orden indicado y devuelve la ruta del PDF resultante.

    Args:
        archivos_ordenados: Lista de dicts con 'nombre_original' y 'ruta_archivo', ya ordenados
        trabajo_id: ID del trabajo para reportar progreso
        agregar_marcadores: Si True, agrega un bookmark por cada PDF fuente

    Returns:
        Ruta al PDF unido generado
    """
    doc_resultado = fitz.open()
    total = len(archivos_ordenados)

    for i, archivo in enumerate(archivos_ordenados):
        progreso = int((i / total) * 85)
        job_manager.actualizar_progreso(
            trabajo_id, progreso,
            f"Uniendo archivo {i+1} de {total}: {archivo['nombre_original']}"
        )

        ruta = Path(archivo['ruta_archivo'])
        if not ruta.exists():
            raise FileNotFoundError(f"Archivo no encontrado en disco: {ruta.name}")

        doc_origen = fitz.open(str(ruta))

        # Guardar donde empieza este archivo para el bookmark
        pagina_inicio_marcador = len(doc_resultado)

        # Insertar todas las paginas
        doc_resultado.insert_pdf(doc_origen)
        doc_origen.close()

        # Agregar bookmark con el nombre del archivo (sin extension)
        if agregar_marcadores:
            nombre_sin_ext = Path(archivo['nombre_original']).stem
            doc_resultado.set_toc(
                doc_resultado.get_toc() + [[1, nombre_sin_ext, pagina_inicio_marcador + 1]]
            )

        logger.info(f"Agregado: {archivo['nombre_original']} ({archivo['num_paginas']} paginas)")

    job_manager.actualizar_progreso(trabajo_id, 90, "Guardando PDF unido")

    nombre_resultado = f"{trabajo_id}_merged.pdf"
    ruta_resultado = config.OUTPUT_FOLDER / nombre_resultado
    doc_resultado.save(str(ruta_resultado), deflate=True)
    doc_resultado.close()

    logger.info(f"PDF unido guardado: {ruta_resultado} ({len(archivos_ordenados)} archivos)")
    return ruta_resultado


def procesar_merge(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal del servicio de union de PDFs.
    Registrado en job_manager como 'merge'.

    Args:
        trabajo_id: ID del trabajo
        archivo_id: No se usa (merge trabaja con lista de archivos)
        parametros: {
            'archivos': [{'file_id': str, 'orden': int}, ...],
            'agregar_marcadores': bool
        }

    Returns:
        Dict con ruta_resultado y mensaje
    """
    lista_archivos = parametros.get('archivos', [])
    agregar_marcadores = parametros.get('agregar_marcadores', False)

    if len(lista_archivos) < 2:
        raise ValueError("Se requieren al menos 2 archivos para unir")

    # Ordenar por el campo 'orden'
    lista_archivos_ordenada = sorted(lista_archivos, key=lambda x: x.get('orden', 0))

    job_manager.actualizar_progreso(trabajo_id, 5, "Verificando archivos")

    # Obtener info de cada archivo en el orden correcto
    archivos_info = []
    for item in lista_archivos_ordenada:
        archivo = models.obtener_archivo(item['file_id'])
        if not archivo:
            raise ValueError(f"Archivo no encontrado: {item['file_id']}")
        archivos_info.append(archivo)

    total_paginas = sum(a['num_paginas'] for a in archivos_info)
    logger.info(f"Uniendo {len(archivos_info)} PDFs, total estimado: {total_paginas} paginas")

    # Unir los PDFs
    ruta_pdf_unido = unir_pdfs(archivos_info, trabajo_id, agregar_marcadores)

    # Comprimir en ZIP
    job_manager.actualizar_progreso(trabajo_id, 95, "Comprimiendo resultado")

    # Usar el nombre del primer archivo como base para el ZIP
    nombre_base = Path(archivos_info[0]['nombre_original']).stem
    nombre_zip = f"{trabajo_id}_{nombre_base}_merged.zip"
    ruta_zip = config.OUTPUT_FOLDER / nombre_zip

    with zipfile.ZipFile(str(ruta_zip), 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        nombre_dentro_zip = f"{nombre_base} - merged.pdf"
        zf.write(str(ruta_pdf_unido), nombre_dentro_zip)

    # Eliminar PDF intermedio
    ruta_pdf_unido.unlink(missing_ok=True)

    return {
        'ruta_resultado': str(ruta_zip),
        'mensaje': f'{len(archivos_info)} PDFs unidos correctamente ({total_paginas} paginas totales)'
    }


# Registrar procesador en el job_manager
job_manager.registrar_procesador('merge', procesar_merge)
