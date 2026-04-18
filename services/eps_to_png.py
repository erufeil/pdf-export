# -*- coding: utf-8 -*-
"""
Etapa 27 — EPS a PNG usando Pillow + Ghostscript.

Convierte un archivo EPS a PNG con escala configurable.
Pillow delega el rasterizado a Ghostscript (gs debe estar en el PATH).
Retorna el PNG directamente (sin ZIP) al ser un unico archivo de salida.

Escalas disponibles:
  1x → dimensiones originales del EPS
  2x → doble resolución  (recomendado)
  3x → triple resolución (calidad alta)
  4x → cuádruple resolución (calidad maxima, archivos grandes)
"""

import logging
from pathlib import Path

from PIL import Image

import config
import models
from utils import job_manager

logger = logging.getLogger(__name__)


def procesar_eps_to_png(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal registrado en job_manager como 'eps-to-png'.
    Convierte el EPS subido a PNG usando Pillow + Ghostscript.

    parametros esperados:
      escala: 1, 2, 3 o 4  (multiplicador de resolución, default 2)
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError('Archivo no encontrado')

    ruta_eps = Path(archivo['ruta_archivo'])
    nombre_original = archivo['nombre_original']

    if not ruta_eps.exists():
        raise FileNotFoundError(f'Archivo no encontrado en disco: {ruta_eps.name}')

    escala = int(parametros.get('escala', 2))
    escala = max(1, min(escala, 4))

    job_manager.actualizar_progreso(trabajo_id, 10, 'Leyendo archivo EPS...')

    nombre_base = Path(nombre_original).stem
    nombre_png  = f'{trabajo_id}_{nombre_base}.png'
    ruta_png    = config.OUTPUT_FOLDER / nombre_png

    job_manager.actualizar_progreso(trabajo_id, 35, f'Rasterizando EPS con Ghostscript (escala {escala}x)...')

    try:
        img = Image.open(str(ruta_eps))
        img.load(scale=escala)
        img = img.convert('RGBA')
    except OSError as exc:
        if 'ghostscript' in str(exc).lower() or 'gs' in str(exc).lower():
            raise ValueError(
                'Ghostscript no está disponible. '
                'Verificar que "ghostscript" esté instalado en el contenedor.'
            )
        raise ValueError(f'Error al abrir el archivo EPS: {exc}')

    job_manager.actualizar_progreso(trabajo_id, 80, 'Guardando PNG...')

    img.save(str(ruta_png), 'PNG')

    if not ruta_png.exists() or ruta_png.stat().st_size == 0:
        raise ValueError('No se generó el archivo PNG')

    job_manager.actualizar_progreso(trabajo_id, 90, 'PNG generado correctamente')

    tam_kb = ruta_png.stat().st_size / 1024
    logger.info(f'[eps-png] {nombre_original} → {nombre_png} ({tam_kb:.1f} KB, escala {escala}x)')

    return {
        'ruta_resultado': str(ruta_png),
        'mensaje': f'"{nombre_original}" convertido a PNG ({escala}x) — {tam_kb:.0f} KB',
    }


# Registrar procesador
job_manager.registrar_procesador('eps-to-png', procesar_eps_to_png)
