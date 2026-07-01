# -*- coding: utf-8 -*-
"""
Servicio de conversion Excel a Markdown para PDFexport (Etapa 39).
Convierte .xlsx y .xls a Markdown. Todas las hojas en un unico .md.
"""

import logging
from pathlib import Path

import pandas as pd

import config
import models
from utils import job_manager

logger = logging.getLogger(__name__)


def _engine_para(extension: str) -> str:
    return 'openpyxl' if extension == '.xlsx' else 'xlrd'


def _df_a_md_table(df: pd.DataFrame) -> str:
    """Convierte un DataFrame pandas a pipe table Markdown."""
    if df.empty:
        return '*Hoja vacía — sin datos*'

    df = df.fillna('')
    cols = [str(c) for c in df.columns]
    filas_str = [
        [str(v).replace('\n', ' ').replace('|', '\\|') for v in row]
        for _, row in df.iterrows()
    ]

    # Calcular anchos de columna (mínimo 3 para el separador)
    anchos = [max(len(c), 3) for c in cols]
    for fila in filas_str:
        for i, v in enumerate(fila):
            if i < len(anchos):
                anchos[i] = max(anchos[i], len(v))

    lineas = []
    # Encabezado
    lineas.append('| ' + ' | '.join(cols[i].ljust(anchos[i]) for i in range(len(cols))) + ' |')
    # Separador
    lineas.append('| ' + ' | '.join('-' * anchos[i] for i in range(len(cols))) + ' |')
    # Filas de datos
    for fila in filas_str:
        while len(fila) < len(cols):
            fila.append('')
        lineas.append('| ' + ' | '.join(fila[i].ljust(anchos[i]) for i in range(len(cols))) + ' |')

    return '\n'.join(lineas)


def procesar_excel_to_md(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal registrado en job_manager como 'excel-to-md'.
    Todas las hojas seleccionadas se unen en un unico archivo .md.
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta = Path(archivo['ruta_archivo'])
    if not ruta.exists():
        raise ValueError("Archivo fisico no encontrado")

    nombre_original = archivo['nombre_original']
    extension = Path(nombre_original).suffix.lower()
    nombre_base = Path(nombre_original).stem
    engine = _engine_para(extension)

    hojas_param = parametros.get('hojas', None)  # None = todas las hojas

    job_manager.actualizar_progreso(trabajo_id, 10, "Leyendo Excel")

    todos_dfs = pd.read_excel(str(ruta), sheet_name=None, engine=engine)

    if not todos_dfs:
        raise ValueError("El archivo Excel no contiene hojas de datos")

    # Filtrar hojas segun seleccion del usuario
    if hojas_param:
        dfs = {k: v for k, v in todos_dfs.items() if k in hojas_param}
        if not dfs:
            raise ValueError("Ninguna de las hojas seleccionadas existe en el archivo")
    else:
        dfs = todos_dfs

    num_hojas = len(dfs)
    job_manager.actualizar_progreso(trabajo_id, 30, f"Convirtiendo {num_hojas} hoja(s) a Markdown")

    partes = []

    # Encabezado del documento solo cuando hay multiples hojas
    if num_hojas > 1:
        partes.append(f'# {nombre_base}\n')

    for i, (nombre_hoja, df) in enumerate(dfs.items()):
        progreso = 30 + int((i + 1) / num_hojas * 50)
        job_manager.actualizar_progreso(trabajo_id, progreso, f"Hoja {i + 1}/{num_hojas}: {nombre_hoja}")

        if num_hojas > 1:
            partes.append(f'## {nombre_hoja}\n')

        partes.append(_df_a_md_table(df))

    contenido_md = '\n\n'.join(partes)

    job_manager.actualizar_progreso(trabajo_id, 85, "Guardando archivo")

    ruta_md = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_base}.md"
    with open(ruta_md, 'w', encoding='utf-8') as f:
        f.write(contenido_md)

    filas_totales = sum(len(df) for df in dfs.values())
    return {
        'ruta_resultado': str(ruta_md),
        'mensaje': f'Markdown generado: {num_hojas} hoja(s), {filas_totales} filas'
    }


job_manager.registrar_procesador('excel-to-md', procesar_excel_to_md)
