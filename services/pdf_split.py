# -*- coding: utf-8 -*-
"""
Servicio de corte de PDF para PDFexport.
Permite dividir un PDF en multiples partes segun rangos de paginas.
"""

import logging
from pathlib import Path
from typing import List, Dict
import uuid

import fitz  # PyMuPDF

import config
import models
from utils import file_manager, job_manager

logger = logging.getLogger(__name__)


def validar_cortes(num_paginas: int, cortes: List[Dict]) -> List[Dict]:
    """
    Valida y normaliza los rangos de corte.

    Args:
        num_paginas: Numero total de paginas del PDF
        cortes: Lista de diccionarios con 'inicio' y 'fin'

    Returns:
        Lista de cortes validados

    Raises:
        ValueError: Si los cortes son invalidos
    """
    if not cortes:
        raise ValueError("Debe especificar al menos un corte")

    if len(cortes) > 20:
        raise ValueError("Maximo 20 cortes permitidos")

    cortes_validados = []

    for i, corte in enumerate(cortes):
        inicio = corte.get('inicio', 1)
        fin = corte.get('fin', num_paginas)

        # Convertir a enteros
        try:
            inicio = int(inicio)
            fin = int(fin)
        except (TypeError, ValueError):
            raise ValueError(f"Corte {i+1}: valores de pagina invalidos")

        # Validar rango
        if inicio < 1:
            inicio = 1
        if fin > num_paginas:
            fin = num_paginas
        if inicio > fin:
            raise ValueError(f"Corte {i+1}: pagina inicial ({inicio}) mayor que final ({fin})")

        cortes_validados.append({
            'inicio': inicio,
            'fin': fin,
            'nombre': corte.get('nombre', f'parte_{i+1}')
        })

    return cortes_validados


def calcular_cortes_iguales(num_paginas: int, num_partes: int) -> List[Dict]:
    """
    Calcula cortes para dividir el PDF en N partes iguales.

    Args:
        num_paginas: Numero total de paginas
        num_partes: Numero de partes deseadas

    Returns:
        Lista de cortes calculados
    """
    if num_partes < 1:
        num_partes = 1
    if num_partes > 20:
        num_partes = 20
    if num_partes > num_paginas:
        num_partes = num_paginas

    paginas_por_parte = num_paginas // num_partes
    paginas_extra = num_paginas % num_partes

    cortes = []
    pagina_actual = 1

    for i in range(num_partes):
        # Distribuir paginas extra en las primeras partes
        paginas_esta_parte = paginas_por_parte + (1 if i < paginas_extra else 0)
        fin = pagina_actual + paginas_esta_parte - 1

        cortes.append({
            'inicio': pagina_actual,
            'fin': fin,
            'nombre': f'parte_{i+1}'
        })

        pagina_actual = fin + 1

    return cortes


def ejecutar_corte(ruta_pdf: Path, cortes: List[Dict], trabajo_id: str) -> List[Path]:
    """
    Ejecuta los cortes en el PDF.

    Args:
        ruta_pdf: Ruta al archivo PDF original
        cortes: Lista de cortes a realizar
        trabajo_id: ID del trabajo para reportar progreso

    Returns:
        Lista de rutas a los PDFs generados
    """
    archivos_generados = []

    try:
        doc = fitz.open(str(ruta_pdf))
        total_cortes = len(cortes)

        for i, corte in enumerate(cortes):
            # Actualizar progreso
            progreso = int((i / total_cortes) * 90)
            job_manager.actualizar_progreso(
                trabajo_id, progreso,
                f"Procesando corte {i+1} de {total_cortes}"
            )

            # Crear nuevo documento con las paginas del rango
            # PyMuPDF usa indices 0-based
            inicio_idx = corte['inicio'] - 1
            fin_idx = corte['fin'] - 1

            nuevo_doc = fitz.open()

            # Insertar paginas del rango
            nuevo_doc.insert_pdf(
                doc,
                from_page=inicio_idx,
                to_page=fin_idx
            )

            # Guardar archivo
            nombre_archivo = f"{corte['nombre']}_p{corte['inicio']}-{corte['fin']}.pdf"
            ruta_salida = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_archivo}"
            nuevo_doc.save(str(ruta_salida))
            nuevo_doc.close()

            archivos_generados.append(ruta_salida)
            logger.info(f"Corte generado: {nombre_archivo} ({corte['fin'] - corte['inicio'] + 1} paginas)")

        doc.close()
        return archivos_generados

    except Exception as e:
        logger.error(f"Error ejecutando cortes: {e}")
        # Limpiar archivos parciales
        for archivo in archivos_generados:
            if archivo.exists():
                archivo.unlink()
        raise


def procesar_split(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal de corte de PDF.
    Esta funcion es llamada por el job_manager.

    Args:
        trabajo_id: ID del trabajo
        archivo_id: ID del archivo a procesar
        parametros: Parametros de la conversion
            - cortes: Lista de rangos [{inicio, fin, nombre}, ...]
            - num_partes: Numero de partes iguales (alternativa a cortes)

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

    num_paginas = archivo['num_paginas']

    # Determinar cortes
    if 'num_partes' in parametros and parametros['num_partes']:
        # Calcular cortes automaticos
        cortes = calcular_cortes_iguales(num_paginas, parametros['num_partes'])
    elif 'cortes' in parametros and parametros['cortes']:
        # Usar cortes especificados
        cortes = validar_cortes(num_paginas, parametros['cortes'])
    else:
        raise ValueError("Debe especificar cortes o numero de partes")

    job_manager.actualizar_progreso(trabajo_id, 5, f"Preparando {len(cortes)} cortes")

    # Ejecutar cortes
    archivos_generados = ejecutar_corte(ruta_pdf, cortes, trabajo_id)

    # Crear ZIP con los resultados
    job_manager.actualizar_progreso(trabajo_id, 95, "Comprimiendo archivos")

    nombre_base = Path(archivo['nombre_original']).stem
    nombre_zip = f"{trabajo_id}_{nombre_base}_cortes.zip"

    archivos_para_zip = [
        (str(ruta), ruta.name) for ruta in archivos_generados
    ]

    ruta_zip = file_manager.crear_zip(archivos_para_zip, nombre_zip)

    # Limpiar archivos individuales (solo dejamos el ZIP)
    for archivo_temp in archivos_generados:
        if archivo_temp.exists():
            archivo_temp.unlink()

    return {
        'ruta_resultado': str(ruta_zip),
        'mensaje': f'{len(cortes)} cortes generados correctamente'
    }


# Registrar el procesador en el job_manager
job_manager.registrar_procesador('split', procesar_split)
