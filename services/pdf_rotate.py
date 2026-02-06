# -*- coding: utf-8 -*-
"""
Servicio de rotacion de paginas PDF para PDFexport.
Permite rotar paginas individuales de un PDF.
"""

import logging
from pathlib import Path
from typing import Dict

import fitz  # PyMuPDF

import config
import models
from utils import file_manager, job_manager

logger = logging.getLogger(__name__)

# Angulos de rotacion validos
ANGULOS_VALIDOS = [0, 90, 180, 270]


def rotar_paginas_pdf(ruta_pdf: Path, rotaciones: Dict[int, int], trabajo_id: str, nombre_original: str) -> Path:
    """
    Rota paginas especificas de un PDF.

    Args:
        ruta_pdf: Ruta al archivo PDF original
        rotaciones: Diccionario {numero_pagina: angulo} (paginas 1-indexed)
        trabajo_id: ID del trabajo para progreso
        nombre_original: Nombre original del archivo

    Returns:
        Ruta al PDF con las rotaciones aplicadas
    """
    job_manager.actualizar_progreso(trabajo_id, 5, "Abriendo documento")

    doc = fitz.open(str(ruta_pdf))
    num_paginas = len(doc)

    # Validar y aplicar rotaciones
    paginas_rotadas = 0
    total_rotaciones = len(rotaciones)

    for num_pagina_str, angulo in rotaciones.items():
        try:
            num_pagina = int(num_pagina_str)

            # Validar numero de pagina
            if num_pagina < 1 or num_pagina > num_paginas:
                logger.warning(f"Pagina {num_pagina} fuera de rango, ignorando")
                continue

            # Validar angulo
            if angulo not in ANGULOS_VALIDOS:
                logger.warning(f"Angulo {angulo} no valido, ignorando")
                continue

            # Aplicar rotacion (PyMuPDF usa 0-indexed)
            pagina = doc[num_pagina - 1]
            pagina.set_rotation(angulo)
            paginas_rotadas += 1

            # Actualizar progreso
            progreso = 10 + int((paginas_rotadas / max(total_rotaciones, 1)) * 80)
            job_manager.actualizar_progreso(
                trabajo_id, progreso,
                f"Rotando pagina {num_pagina} a {angulo}°"
            )

        except Exception as e:
            logger.error(f"Error rotando pagina {num_pagina_str}: {e}")

    job_manager.actualizar_progreso(trabajo_id, 92, "Guardando documento")

    # Guardar documento rotado
    nombre_salida = f"{trabajo_id}_{nombre_original} - rotado.pdf"
    ruta_salida = config.OUTPUT_FOLDER / nombre_salida

    doc.save(str(ruta_salida))
    doc.close()

    return ruta_salida


def obtener_info_paginas(archivo_id: str, pagina_inicio: int = 1, cantidad: int = 20) -> Dict:
    """
    Obtiene informacion de las paginas para mostrar miniaturas.

    Args:
        archivo_id: ID del archivo
        pagina_inicio: Pagina inicial (1-indexed)
        cantidad: Cantidad de paginas a obtener

    Returns:
        dict con informacion de paginas
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo fisico no encontrado")

    doc = fitz.open(str(ruta_pdf))
    num_paginas = len(doc)

    # Ajustar rango
    pagina_inicio = max(1, min(pagina_inicio, num_paginas))
    pagina_fin = min(pagina_inicio + cantidad - 1, num_paginas)

    paginas = []
    for i in range(pagina_inicio - 1, pagina_fin):
        pagina = doc[i]
        paginas.append({
            'numero': i + 1,
            'rotacion_actual': pagina.rotation,
            'ancho': int(pagina.rect.width),
            'alto': int(pagina.rect.height)
        })

    doc.close()

    return {
        'total_paginas': num_paginas,
        'pagina_inicio': pagina_inicio,
        'pagina_fin': pagina_fin,
        'paginas': paginas
    }


def procesar_rotate(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal de rotacion de PDF.
    Esta funcion es llamada por el job_manager.

    Args:
        trabajo_id: ID del trabajo
        archivo_id: ID del archivo a procesar
        parametros: Parametros con las rotaciones
            - rotaciones: Dict {numero_pagina: angulo}

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

    rotaciones = parametros.get('rotaciones', {})

    if not rotaciones:
        raise ValueError("No se especificaron rotaciones")

    nombre_original = archivo['nombre_original']

    job_manager.actualizar_progreso(trabajo_id, 2, "Iniciando rotacion")

    # Rotar
    ruta_resultado = rotar_paginas_pdf(ruta_pdf, rotaciones, trabajo_id, nombre_original)

    return {
        'ruta_resultado': str(ruta_resultado),
        'mensaje': f'{len(rotaciones)} paginas rotadas'
    }


# Registrar el procesador en el job_manager
job_manager.registrar_procesador('rotate', procesar_rotate)
