# -*- coding: utf-8 -*-
"""
Servicio WEBP a PNG para PDFexport.
Convierte un archivo WEBP a PNG conservando la maxima calidad.
Si el WEBP es animado, extrae solo el primer frame.
"""

import logging
from pathlib import Path

from PIL import Image as PILImage

import config
import models
from utils import job_manager

logger = logging.getLogger(__name__)


def procesar_webp_to_png(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal registrado en job_manager como 'webp-to-png'.
    Convierte el WEBP subido a PNG de maxima calidad.

    Args:
        trabajo_id: ID del trabajo en curso
        archivo_id: ID del archivo WEBP ya subido
        parametros: No se usan opciones — conversion directa

    Returns:
        Dict con 'ruta_resultado' y 'mensaje'
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_webp = Path(archivo['ruta_archivo'])
    nombre_original = archivo['nombre_original']

    if not ruta_webp.exists():
        raise FileNotFoundError(f"Archivo no encontrado en disco: {ruta_webp.name}")

    job_manager.actualizar_progreso(trabajo_id, 10, "Abriendo imagen WEBP")

    # Abrir con Pillow — si es animado solo toma el primer frame
    with PILImage.open(str(ruta_webp)) as img:
        # Saltar al primer frame en caso de WEBP animado
        try:
            img.seek(0)
        except EOFError:
            pass  # Imagen estatica, seek(0) no aplica

        job_manager.actualizar_progreso(trabajo_id, 40, "Convirtiendo a PNG")

        # Convertir a RGBA para preservar transparencia, luego a RGB si no la tiene
        # PNG soporta transparencia, no es necesario aplanar el canal alpha
        if img.mode not in ('RGB', 'RGBA', 'L', 'LA'):
            img = img.convert('RGBA')

        # Construir nombre de salida: misma base, extension .png
        nombre_base = Path(nombre_original).stem
        nombre_png = f"{trabajo_id}_{nombre_base}.png"
        ruta_png = config.OUTPUT_FOLDER / nombre_png

        job_manager.actualizar_progreso(trabajo_id, 70, "Guardando PNG")

        # Guardar como PNG sin perdida de calidad
        img.save(str(ruta_png), format='PNG', optimize=False)

    logger.info(f"WEBP convertido a PNG: {nombre_original} → {nombre_png}")

    return {
        'ruta_resultado': str(ruta_png),
        'mensaje': f'"{nombre_original}" convertido a PNG correctamente'
    }


# Registrar procesador en el job_manager
job_manager.registrar_procesador('webp-to-png', procesar_webp_to_png)
