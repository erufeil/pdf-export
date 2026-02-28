# -*- coding: utf-8 -*-
"""
Servicio de extraccion de tablas de PDF a CSV para PDFexport (Etapa 15).
Usa pdfplumber como extractor principal, con fallback a PyMuPDF.
"""

import csv
import io
import logging
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import fitz  # PyMuPDF

import config
import models
from utils import file_manager, job_manager

logger = logging.getLogger(__name__)


def _normalizar_cabecera(texto: str) -> str:
    """Normaliza texto de cabecera para comparacion: lowercase sin espacios."""
    return texto.strip().lower().replace(' ', '')


def _normalizar_nombre_archivo(texto: str) -> str:
    """
    Limpia texto para usarlo como nombre de archivo.
    Remueve caracteres no validos y limita a 20 caracteres.
    """
    # Descomponer caracteres Unicode (para remover tildes)
    texto_norm = unicodedata.normalize('NFKD', str(texto))
    texto_norm = ''.join(c for c in texto_norm if not unicodedata.combining(c))
    # Remover caracteres no validos para nombres de archivo
    texto_norm = re.sub(r'[\\/:*?"<>|\n\r\t]', '', texto_norm)
    texto_norm = texto_norm.strip()
    resultado = texto_norm[:20] if texto_norm else 'sin_titulo'
    return resultado


def _detectar_titulo_tabla(page, tabla_bbox: Tuple) -> str:
    """
    Busca el titulo de una tabla: texto con letra mas grande o en negrita
    en los 15 renglones antes de la posicion superior de la tabla.

    Args:
        page: objeto pagina de pdfplumber
        tabla_bbox: (x0, top, x1, bottom) posicion de la tabla en la pagina

    Returns:
        Texto del titulo normalizado (maximo 20 caracteres), o 'sin_titulo'
    """
    try:
        tabla_top = tabla_bbox[1]  # posicion Y superior de la tabla

        # Zona de busqueda: ~15 lineas de 14pt hacia arriba
        altura_busqueda = 15 * 14
        zona_top = max(0, tabla_top - altura_busqueda)

        # Extraer palabras de la pagina con atributos de fuente si es posible
        try:
            palabras = page.extract_words(
                extra_attrs=['size', 'fontname'],
                y_tolerance=3,
                x_tolerance=3
            )
        except TypeError:
            # Versiones antiguas de pdfplumber sin extra_attrs
            palabras = page.extract_words(y_tolerance=3, x_tolerance=3)

        # Filtrar palabras en la zona antes de la tabla
        palabras_zona = [
            p for p in palabras
            if zona_top <= p.get('top', 0) < tabla_top
        ]

        if not palabras_zona:
            return 'sin_titulo'

        # Intentar detectar por tamanio de fuente
        if palabras_zona and 'size' in palabras_zona[0]:
            tamanios = [p.get('size', 0) for p in palabras_zona]
            mayor_tam = max(tamanios) if tamanios else 0

            if mayor_tam > 0:
                # Recopilar lineas con el mayor tamanio de fuente
                # Agrupar por posicion Y aproximada
                lineas_y = {}
                for p in palabras_zona:
                    if p.get('size', 0) >= mayor_tam * 0.85:
                        y_key = round(p.get('top', 0))
                        lineas_y.setdefault(y_key, []).append(p)

                if lineas_y:
                    # Tomar la ultima linea (la mas cercana a la tabla)
                    y_elegido = max(lineas_y.keys())
                    palabras_linea = sorted(lineas_y[y_elegido], key=lambda x: x.get('x0', 0))
                    titulo = ' '.join(p['text'] for p in palabras_linea)
                    return _normalizar_nombre_archivo(titulo)

        # Fallback: buscar negrita en fontname
        negritas = [
            p for p in palabras_zona
            if 'bold' in (p.get('fontname') or '').lower()
        ]
        if negritas:
            y_max_bold = max(p.get('top', 0) for p in negritas)
            linea_bold = [
                p for p in negritas
                if abs(p.get('top', 0) - y_max_bold) < 5
            ]
            linea_bold.sort(key=lambda x: x.get('x0', 0))
            titulo = ' '.join(p['text'] for p in linea_bold)
            return _normalizar_nombre_archivo(titulo)

        # Ultimo recurso: ultima linea de texto antes de la tabla
        y_max = max(p.get('top', 0) for p in palabras_zona)
        ultima_linea = [
            p for p in palabras_zona
            if abs(p.get('top', 0) - y_max) < 5
        ]
        ultima_linea.sort(key=lambda x: x.get('x0', 0))
        titulo = ' '.join(p['text'] for p in ultima_linea)
        return _normalizar_nombre_archivo(titulo)

    except Exception as e:
        logger.warning(f"Error detectando titulo: {e}")
        return 'sin_titulo'


def _extraer_tablas_pdfplumber(ruta_pdf: Path, max_paginas: int = None) -> List[Dict]:
    """
    Extrae tablas del PDF usando pdfplumber (extractor principal).
    pdfplumber detecta tablas con lineas visibles mejor que PyMuPDF.

    Args:
        max_paginas: si se indica, procesa solo las primeras N paginas (para analisis rapido)

    Returns:
        Lista de dicts con: pagina, tabla_num, datos, titulo, cabeceras
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber no instalado. Agregar 'pdfplumber' a requirements.txt")

    tablas_encontradas = []

    with pdfplumber.open(str(ruta_pdf)) as pdf:
        paginas = pdf.pages[:max_paginas] if max_paginas else pdf.pages
        for num_pagina, page in enumerate(paginas, start=1):
            try:
                # Estrategia 1: lineas explicitas (tablas con bordes visibles)
                tablas_pag = page.find_tables(table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                })

                # Estrategia 2: si no encontro nada, probar alineacion de texto
                # (tablas sin bordes visibles, ej: PDFs exportados desde Excel sin cuadricula)
                if not tablas_pag:
                    tablas_pag = page.find_tables(table_settings={
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                    })

                for idx_tabla, tabla_obj in enumerate(tablas_pag, start=1):
                    try:
                        datos = tabla_obj.extract()

                        if not datos:
                            continue

                        # Limpiar celdas: None y saltos de linea → string
                        datos_limpios = []
                        for fila in datos:
                            if fila is None:
                                continue
                            fila_limpia = []
                            for celda in fila:
                                if celda is None:
                                    fila_limpia.append('')
                                else:
                                    # Reemplazar saltos de linea internos por espacio
                                    fila_limpia.append(str(celda).replace('\n', ' ').strip())
                            # Ignorar filas completamente vacias
                            if any(c for c in fila_limpia):
                                datos_limpios.append(fila_limpia)

                        if not datos_limpios:
                            continue

                        # Detectar titulo mirando texto antes de la tabla
                        titulo = _detectar_titulo_tabla(page, tabla_obj.bbox)

                        # Cabeceras normalizadas para comparar luego
                        cabeceras = [_normalizar_cabecera(c) for c in datos_limpios[0]]

                        tablas_encontradas.append({
                            'pagina': num_pagina,
                            'tabla_num': idx_tabla,
                            'datos': datos_limpios,
                            'titulo': titulo,
                            'cabeceras': cabeceras,
                        })
                        logger.debug(f"Tabla: pag {num_pagina}, tabla {idx_tabla}, {len(datos_limpios)} filas")

                    except Exception as e:
                        logger.warning(f"Error extrayendo tabla {idx_tabla} pag {num_pagina}: {e}")
                        continue

            except Exception as e:
                logger.warning(f"Error procesando pagina {num_pagina}: {e}")
                continue

    return tablas_encontradas


def _extraer_tablas_fitz(ruta_pdf: Path, max_paginas: int = None) -> List[Dict]:
    """
    Fallback: extrae tablas usando PyMuPDF (fitz).
    Disponible desde PyMuPDF 1.23+. Menos preciso que pdfplumber para PDFs
    con lineas de tabla poco definidas.

    Returns:
        Lista de dicts con: pagina, tabla_num, datos, titulo, cabeceras
    """
    tablas_encontradas = []

    try:
        doc = fitz.open(str(ruta_pdf))
        total_paginas = min(len(doc), max_paginas) if max_paginas else len(doc)

        for num_pagina in range(total_paginas):
            page = doc[num_pagina]
            try:
                # find_tables() disponible en PyMuPDF >= 1.23.0
                # Estrategia default (lineas explicitas)
                tabs = page.find_tables()
                # Si no encontro tablas, intentar con estrategia de texto
                if not tabs.tables:
                    tabs = page.find_tables(strategy="text")

                for idx_tabla, tabla in enumerate(tabs.tables, start=1):
                    try:
                        datos = tabla.extract()

                        if not datos:
                            continue

                        datos_limpios = []
                        for fila in datos:
                            if fila is None:
                                continue
                            fila_limpia = []
                            for celda in fila:
                                if celda is None:
                                    fila_limpia.append('')
                                else:
                                    fila_limpia.append(str(celda).replace('\n', ' ').strip())
                            if any(c for c in fila_limpia):
                                datos_limpios.append(fila_limpia)

                        if not datos_limpios:
                            continue

                        cabeceras = [_normalizar_cabecera(c) for c in datos_limpios[0]]

                        tablas_encontradas.append({
                            'pagina': num_pagina + 1,
                            'tabla_num': idx_tabla,
                            'datos': datos_limpios,
                            'titulo': f'tabla_fitz_{num_pagina + 1}_{idx_tabla}',
                            'cabeceras': cabeceras,
                        })

                    except Exception as e:
                        logger.warning(f"Error tabla fitz {idx_tabla} pag {num_pagina + 1}: {e}")
                        continue

            except Exception as e:
                logger.warning(f"Error fitz pagina {num_pagina + 1}: {e}")
                continue

        doc.close()

    except Exception as e:
        logger.error(f"Error abriendo PDF con fitz: {e}")

    return tablas_encontradas


def _consolidar_continuaciones(tablas: List[Dict]) -> List[Dict]:
    """
    Detecta y fusiona tablas que son continuacion de la tabla de la pagina anterior.

    Caso tipico: tabla de 121 paginas donde la cabecera solo aparece en la pagina 1.
    pdfplumber/fitz ve 121 tablas separadas; esta funcion las fusiona en una sola.

    Criterio de continuacion: misma cantidad de columnas en paginas consecutivas.
    La primera tabla del grupo conserva sus datos completos (incluye cabecera).
    Las tablas siguientes aportan solo sus filas (sin repetir cabecera).
    """
    if len(tablas) <= 1:
        return tablas

    # Ordenar por pagina y tabla dentro de la pagina
    tablas_sorted = sorted(tablas, key=lambda t: (t['pagina'], t['tabla_num']))

    grupos = [[tablas_sorted[0]]]

    for i in range(1, len(tablas_sorted)):
        tabla_prev = grupos[-1][-1]
        tabla_curr = tablas_sorted[i]

        num_cols_prev = len(tabla_prev['datos'][0]) if tabla_prev['datos'] else 0
        num_cols_curr = len(tabla_curr['datos'][0]) if tabla_curr['datos'] else 0

        # Es continuacion: misma cantidad de columnas Y pagina inmediatamente siguiente
        paginas_consecutivas = tabla_curr['pagina'] == tabla_prev['pagina'] + 1
        mismas_columnas = (num_cols_prev == num_cols_curr and num_cols_prev > 0)

        if paginas_consecutivas and mismas_columnas:
            grupos[-1].append(tabla_curr)
        else:
            grupos.append([tabla_curr])

    # Consolidar cada grupo en una sola tabla
    resultado = []
    for grupo in grupos:
        if len(grupo) == 1:
            resultado.append(grupo[0])
        else:
            tabla_base = dict(grupo[0])
            # Datos de la primera tabla (con cabecera) + filas de las continuaciones
            datos_fusionados = list(grupo[0]['datos'])
            for tabla_cont in grupo[1:]:
                datos_fusionados.extend(tabla_cont['datos'])

            tabla_base['datos'] = datos_fusionados
            logger.info(
                f"Continuacion detectada: {len(grupo)} tablas fusionadas "
                f"(pags {grupo[0]['pagina']}-{grupo[-1]['pagina']})"
            )
            resultado.append(tabla_base)

    return resultado


def _generar_csv_bytes(datos: List[List[str]], separador: str, saltos_linea: str) -> bytes:
    """
    Genera los bytes del archivo CSV con las opciones indicadas.
    Incluye BOM UTF-8 para compatibilidad con Excel en Windows.

    Args:
        datos: Lista de filas (cada fila es lista de celdas)
        separador: ',' o ';'
        saltos_linea: 'CRLF' o 'LF'

    Returns:
        bytes del CSV con BOM UTF-8
    """
    terminador = '\r\n' if saltos_linea == 'CRLF' else '\n'

    buf = io.StringIO()
    writer = csv.writer(
        buf,
        delimiter=separador,
        quoting=csv.QUOTE_MINIMAL,
        lineterminator=terminador
    )

    for fila in datos:
        writer.writerow(fila)

    # BOM UTF-8 + contenido: hace que Excel abra el CSV en UTF-8 correctamente
    return '\ufeff'.encode('utf-8') + buf.getvalue().encode('utf-8')


def _agrupar_tablas_iguales(tablas: List[Dict]) -> List[List[Dict]]:
    """
    Agrupa tablas que tienen las mismas cabeceras en el mismo orden.
    Solo se unifican si las cabeceras coinciden exactamente (orden incluido).

    Returns:
        Lista de grupos. Cada grupo es una lista de tablas con cabeceras iguales.
    """
    grupos = []
    tablas_restantes = list(tablas)

    while tablas_restantes:
        tabla_ref = tablas_restantes.pop(0)
        cabs_ref = tabla_ref['cabeceras']

        grupo = [tabla_ref]
        no_matchean = []

        for tabla in tablas_restantes:
            if tabla['cabeceras'] == cabs_ref:
                grupo.append(tabla)
            else:
                no_matchean.append(tabla)

        grupos.append(grupo)
        tablas_restantes = no_matchean

    return grupos


def _analizar_rapido_fitz(ruta_pdf: Path, max_paginas: int = 5) -> Dict:
    """
    Analisis rapido usando solo fitz.get_drawings() y get_text("words").
    NO usa find_tables() — no puede colgarse porque solo lee metadatos.

    Detecta dos tipos de tablas:
    - Con bordes: muchas lineas horizontales y verticales dibujadas
    - Sin bordes: texto alineado en columnas consistentes (ej: exportado de Excel)

    Returns:
        Dict con: tiene_tablas (bool), tipo ('bordes'|'texto'|'ninguno')
    """
    doc = fitz.open(str(ruta_pdf))
    total = min(len(doc), max_paginas)

    tiene_bordes = False
    tiene_texto_tabla = False

    for i in range(total):
        page = doc[i]

        # --- Check 1: Lineas geometricas (tabla con cuadricula visible) ---
        drawings = page.get_drawings()
        h_lines = 0
        v_lines = 0
        for d in drawings:
            for item in d.get('items', []):
                if item[0] == 'l':          # segmento de linea
                    p1, p2 = item[1], item[2]
                    dy = abs(p2[1] - p1[1])
                    dx = abs(p2[0] - p1[0])
                    if dy < 1.5 and dx > 20:    # horizontal
                        h_lines += 1
                    elif dx < 1.5 and dy > 10:  # vertical
                        v_lines += 1
                elif item[0] == 're':       # rectangulo = 4 lineas de tabla
                    h_lines += 2
                    v_lines += 2

        if h_lines >= 4 and v_lines >= 1:
            tiene_bordes = True
            break

        # --- Check 2: Texto alineado en columnas (tabla sin bordes) ---
        words = page.get_text("words")  # (x0, y0, x1, y1, text, block, line, word)
        if words:
            # Agrupar palabras por fila (posicion Y aproximada)
            filas = {}
            for w in words:
                y_key = round(w[1] / 4) * 4  # tolerancia ±4 pts
                filas.setdefault(y_key, []).append(w[0])  # guardar x0

            # Contar filas con 3 o mas columnas de texto
            filas_multi_col = [xs for xs in filas.values() if len(xs) >= 3]

            if len(filas_multi_col) >= 4:
                # Verificar que las columnas son consistentes entre filas
                # (los x0 de distintas filas se agrupan en las mismas zonas)
                todos_x0 = sorted(set(round(x / 10) * 10 for xs in filas_multi_col for x in xs))
                if len(todos_x0) >= 3:
                    tiene_texto_tabla = True
                    break

    doc.close()

    tipo = 'bordes' if tiene_bordes else ('texto' if tiene_texto_tabla else 'ninguno')
    return {'tiene_tablas': tiene_bordes or tiene_texto_tabla, 'tipo': tipo}


def analizar_tablas(archivo_id: str) -> Dict:
    """
    Analiza un PDF y detecta si contiene tablas (operacion sincrona, sin cuelgue).

    Usa heuristicas rapidas (get_drawings + posicion de texto) en lugar de
    find_tables() para evitar cuelgues en PDFs con tablas densas.

    Returns:
        Dict con: num_tablas, tablas_iguales, hay_continuaciones, mensaje, encoding
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo fisico no encontrado")

    num_paginas_pdf = archivo.get('num_paginas', 0)

    # Analisis rapido: detecta tipo de tabla sin riesgo de cuelgue
    info = _analizar_rapido_fitz(ruta_pdf, max_paginas=5)
    tiene_tablas = info['tiene_tablas']
    tipo_tabla = info['tipo']

    logger.info(f"Analisis rapido: tiene_tablas={tiene_tablas}, tipo={tipo_tabla}, pags={num_paginas_pdf}")

    if not tiene_tablas:
        return {
            'num_tablas': 0,
            'tablas_iguales': False,
            'hay_continuaciones': False,
            'mensaje': 'No se detectaron tablas en el documento (puede ser PDF escaneado o solo texto)',
            'encoding': 'utf-8-bom',
        }

    # Con tablas confirmadas, armar mensaje descriptivo
    if num_paginas_pdf > 5:
        if tipo_tabla == 'bordes':
            mensaje = (
                f'Tablas con bordes detectadas '
                f'(analisis rapido, {num_paginas_pdf} paginas). '
                f'Se extraeran al ejecutar.'
            )
        else:
            mensaje = (
                f'Tablas sin bordes visibles detectadas (alineacion de texto). '
                f'Se extraeran al ejecutar ({num_paginas_pdf} paginas).'
            )
    else:
        mensaje = f'Tablas detectadas en el documento ({tipo_tabla})'

    # Estimar si puede haber continuaciones (documento multi-pagina con una sola tabla)
    hay_continuaciones = num_paginas_pdf > 1

    return {
        'num_tablas': 1,   # estimacion minima; el conteo real ocurre al ejecutar
        'tablas_iguales': False,
        'hay_continuaciones': hay_continuaciones,
        'mensaje': mensaje,
        'encoding': 'utf-8-bom',
    }


def procesar_to_csv(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal: extrae todas las tablas del PDF y genera archivos CSV.
    Llamado por el job_manager en el worker thread.

    Args:
        trabajo_id: ID del trabajo
        archivo_id: ID del archivo PDF a procesar
        parametros:
            - unificar_iguales: bool — unifica tablas con mismas cabeceras
            - separador: ';' o ',' (default ';')
            - saltos_linea: 'CRLF' o 'LF' (default 'CRLF')

    Returns:
        dict con ruta_resultado y mensaje
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo fisico no encontrado")

    nombre_original = archivo['nombre_original']
    nombre_base_sin_ext = Path(nombre_original).stem

    # Opciones con valores por defecto
    unificar_iguales = parametros.get('unificar_iguales', False)
    separador = parametros.get('separador', ';')
    saltos_linea = parametros.get('saltos_linea', 'CRLF')

    # Validaciones
    if separador not in [',', ';']:
        separador = ';'
    if saltos_linea not in ['CRLF', 'LF']:
        saltos_linea = 'CRLF'

    job_manager.actualizar_progreso(trabajo_id, 5, "Analizando documento")

    # Extraer tablas: pdfplumber primero, fitz como fallback
    tablas = []
    try:
        tablas = _extraer_tablas_pdfplumber(ruta_pdf)
        logger.info(f"pdfplumber encontro {len(tablas)} tablas en {nombre_original}")
    except ImportError:
        logger.warning("pdfplumber no disponible, usando PyMuPDF como fallback")

    if not tablas:
        tablas = _extraer_tablas_fitz(ruta_pdf)
        logger.info(f"PyMuPDF encontro {len(tablas)} tablas en {nombre_original}")

    if not tablas:
        raise ValueError(
            "No se encontraron tablas en el documento. "
            "El PDF puede ser escaneado (solo imagen) o no contener tablas detectables."
        )

    job_manager.actualizar_progreso(trabajo_id, 18, f"Detectadas {len(tablas)} secciones, consolidando continuaciones")

    # Fusionar tablas que son continuacion de la pagina anterior
    # (mismo numero de columnas en paginas consecutivas = una sola tabla multi-pagina)
    tablas = _consolidar_continuaciones(tablas)
    logger.info(f"Tras consolidar continuaciones: {len(tablas)} tabla(s) en {nombre_original}")

    job_manager.actualizar_progreso(trabajo_id, 20, f"Generando CSV para {len(tablas)} tabla(s)")

    archivos_temp = []
    archivos_para_zip = []

    if unificar_iguales:
        # Agrupar tablas con mismas cabeceras
        grupos = _agrupar_tablas_iguales(tablas)
        total_grupos = len(grupos)

        for idx_grupo, grupo in enumerate(grupos):
            progreso = 20 + int((idx_grupo / total_grupos) * 70)
            job_manager.actualizar_progreso(
                trabajo_id, progreso,
                f"Generando CSV {idx_grupo + 1} de {total_grupos}"
            )

            tabla_ref = grupo[0]

            if len(grupo) == 1:
                # Una sola tabla con estas cabeceras — nombre normal
                nombre_csv = (
                    f"tabla_pag{tabla_ref['pagina']}_{tabla_ref['tabla_num']}"
                    f"_{tabla_ref['titulo']}.csv"
                )
                datos = tabla_ref['datos']
            else:
                # Varias tablas con las mismas cabeceras — unificar
                nombre_csv = (
                    f"tabla_pag{tabla_ref['pagina']}_{tabla_ref['tabla_num']}_unificada.csv"
                )
                # Primera fila = cabecera original (de la primera tabla)
                datos = [tabla_ref['datos'][0]]
                # Agregar filas de datos de todas las tablas del grupo (sin repetir cabecera)
                for tabla in grupo:
                    datos.extend(tabla['datos'][1:])

            csv_bytes = _generar_csv_bytes(datos, separador, saltos_linea)
            ruta_temp = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_csv}"
            ruta_temp.write_bytes(csv_bytes)

            archivos_temp.append(ruta_temp)
            archivos_para_zip.append((str(ruta_temp), nombre_csv))

    else:
        # Sin unificar: un CSV por tabla
        total_tablas = len(tablas)

        for idx, tabla in enumerate(tablas):
            progreso = 20 + int((idx / total_tablas) * 70)
            job_manager.actualizar_progreso(
                trabajo_id, progreso,
                f"Generando CSV {idx + 1} de {total_tablas}"
            )

            nombre_csv = (
                f"tabla_pag{tabla['pagina']}_{tabla['tabla_num']}"
                f"_{tabla['titulo']}.csv"
            )
            csv_bytes = _generar_csv_bytes(tabla['datos'], separador, saltos_linea)

            ruta_temp = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_csv}"
            ruta_temp.write_bytes(csv_bytes)

            archivos_temp.append(ruta_temp)
            archivos_para_zip.append((str(ruta_temp), nombre_csv))

    job_manager.actualizar_progreso(trabajo_id, 92, "Comprimiendo archivos CSV")

    # Crear ZIP de salida
    nombre_zip = f"{trabajo_id}_{nombre_base_sin_ext}_csv.zip"
    ruta_zip = file_manager.crear_zip(archivos_para_zip, nombre_zip)

    # Limpiar archivos temporales
    for ruta_temp in archivos_temp:
        if ruta_temp.exists():
            ruta_temp.unlink()

    total_csv = len(archivos_para_zip)
    logger.info(f"CSV generados: {total_csv} archivos en {nombre_zip}")

    return {
        'ruta_resultado': str(ruta_zip),
        'mensaje': f'{total_csv} archivo(s) CSV generado(s)'
    }


# Registrar procesador en el job_manager
job_manager.registrar_procesador('to-csv', procesar_to_csv)
