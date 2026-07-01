# -*- coding: utf-8 -*-
"""
Servicio de conversion Excel a CSV para PDFexport (Etapa 35).
Convierte .xlsx y .xls a CSV, una hoja por archivo.
Retorna CSV directo si hay 1 hoja, ZIP si hay multiples.
"""

import logging
import re
from pathlib import Path

import openpyxl
import pandas as pd

import config
import models
from utils import file_manager, job_manager

logger = logging.getLogger(__name__)


def _engine_para(extension: str) -> str:
    return 'openpyxl' if extension == '.xlsx' else 'xlrd'


def _sanitizar_nombre(nombre: str) -> str:
    """Elimina caracteres invalidos para nombre de archivo."""
    return re.sub(r'[<>:"/\\|?*]', '', nombre).strip() or 'hoja'


def analizar_xlsx(archivo_id: str) -> dict:
    """
    Retorna nombres de hojas del Excel sin leer todos los datos.
    Llamado de forma sincrona desde /xlsx-to-csv/info.
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta = Path(archivo['ruta_archivo'])
    extension = Path(archivo['nombre_original']).suffix.lower()

    if extension == '.xlsx':
        wb = openpyxl.load_workbook(str(ruta), read_only=True, data_only=True)
        hojas = list(wb.sheetnames)
        wb.close()
    else:
        import xlrd
        wb = xlrd.open_workbook(str(ruta), on_demand=True)
        hojas = wb.sheet_names()

    return {'hojas': hojas, 'num_hojas': len(hojas)}


def procesar_xlsx_to_csv(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal registrado en job_manager como 'xlsx-to-csv'.
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

    separador = parametros.get('separador', ';')
    if separador not in (',', ';'):
        separador = ';'
    codificacion = parametros.get('codificacion', 'utf-8-sig')
    if codificacion not in ('utf-8-sig', 'utf-8', 'latin-1'):
        codificacion = 'utf-8-sig'

    job_manager.actualizar_progreso(trabajo_id, 10, "Leyendo archivo Excel")

    engine = _engine_para(extension)
    hojas_df = pd.read_excel(str(ruta), sheet_name=None, engine=engine)
    nombres_hojas = list(hojas_df.keys())
    num_hojas = len(nombres_hojas)

    if num_hojas == 0:
        raise ValueError("El archivo Excel no contiene hojas de datos")

    job_manager.actualizar_progreso(trabajo_id, 30, f"Convirtiendo {num_hojas} hoja(s)")

    archivos_generados = []
    padding = len(str(num_hojas))

    for i, nombre_hoja in enumerate(nombres_hojas):
        df = hojas_df[nombre_hoja]
        n_str = str(i + 1).zfill(padding)
        hoja_safe = _sanitizar_nombre(nombre_hoja)
        nombre_csv = f"{nombre_base} - hoja {n_str} {hoja_safe}.csv"
        ruta_csv = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_csv}"

        df.to_csv(str(ruta_csv), index=False, sep=separador, encoding=codificacion)
        archivos_generados.append((ruta_csv, nombre_csv))

        progreso = int(30 + ((i + 1) / num_hojas) * 55)
        job_manager.actualizar_progreso(trabajo_id, progreso, f"Hoja {i+1}/{num_hojas}: {nombre_hoja}")

    # Una sola hoja: CSV directo (sin ZIP)
    if num_hojas == 1:
        ruta_csv, _ = archivos_generados[0]
        filas = len(hojas_df[nombres_hojas[0]])
        return {
            'ruta_resultado': str(ruta_csv),
            'mensaje': f'1 hoja convertida: {nombres_hojas[0]} ({filas} filas)'
        }

    job_manager.actualizar_progreso(trabajo_id, 88, "Comprimiendo CSVs")

    nombre_zip = f"{trabajo_id}_{nombre_base}_csv.zip"
    archivos_para_zip = [(str(ruta), nombre) for ruta, nombre in archivos_generados]
    ruta_zip = file_manager.crear_zip(archivos_para_zip, nombre_zip)

    for ruta_temp, _ in archivos_generados:
        if ruta_temp.exists():
            ruta_temp.unlink()

    total_filas = sum(len(df) for df in hojas_df.values())
    return {
        'ruta_resultado': str(ruta_zip),
        'mensaje': f'{num_hojas} hojas convertidas ({total_filas} filas en total)'
    }


# Registrar procesador en job_manager
job_manager.registrar_procesador('xlsx-to-csv', procesar_xlsx_to_csv)
