# -*- coding: utf-8 -*-
"""
Etapa 23 — SVG a PNG usando cairosvg.

Convierte un archivo SVG a PNG con escala configurable.
Retorna el PNG directamente (sin ZIP) al ser un unico archivo de salida.

Escalas disponibles:
  1x → dimensiones originales del SVG
  2x → doble resolución  (recomendado para pantallas HiDPI)
  3x → triple resolución (calidad alta)
  4x → cuádruple resolución (calidad maxima, archivos grandes)
"""

import logging
from pathlib import Path

import config
import models
from utils import job_manager

logger = logging.getLogger(__name__)


def procesar_svg_to_png(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal registrado en job_manager como 'svg-to-png'.
    Convierte el SVG subido a PNG usando cairosvg.

    parametros esperados:
      escala: 1, 2, 3 o 4  (multiplicador de resolución, default 2)
    """
    import cairosvg

    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError('Archivo no encontrado')

    ruta_svg = Path(archivo['ruta_archivo'])
    nombre_original = archivo['nombre_original']

    if not ruta_svg.exists():
        raise FileNotFoundError(f'Archivo no encontrado en disco: {ruta_svg.name}')

    escala = int(parametros.get('escala', 2))
    # Limitar escala a rango válido
    escala = max(1, min(escala, 4))

    job_manager.actualizar_progreso(trabajo_id, 10, 'Leyendo archivo SVG...')

    # Construir nombre de salida
    nombre_base = Path(nombre_original).stem
    nombre_png  = f'{trabajo_id}_{nombre_base}.png'
    ruta_png    = config.OUTPUT_FOLDER / nombre_png

    job_manager.actualizar_progreso(trabajo_id, 40, f'Convirtiendo SVG a PNG (escala {escala}x)...')

    try:
        cairosvg.svg2png(
            url=str(ruta_svg),
            write_to=str(ruta_png),
            scale=escala,
        )
    except Exception as exc:
        logger.error(f'[svg-png] Error cairosvg: {exc}')
        raise ValueError(f'Error al convertir SVG: {exc}')

    if not ruta_png.exists() or ruta_png.stat().st_size == 0:
        raise ValueError('cairosvg no generó el archivo PNG')

    job_manager.actualizar_progreso(trabajo_id, 90, 'PNG generado correctamente')

    tam_kb = ruta_png.stat().st_size / 1024
    logger.info(f'[svg-png] {nombre_original} → {nombre_png} ({tam_kb:.1f} KB, escala {escala}x)')

    return {
        'ruta_resultado': str(ruta_png),
        'mensaje': f'"{nombre_original}" convertido a PNG ({escala}x) — {tam_kb:.0f} KB',
    }


# Registrar procesador
job_manager.registrar_procesador('svg-to-png', procesar_svg_to_png)
