# -*- coding: utf-8 -*-
"""
Servicio de extraccion de tablas de PDF a CSV (Etapa 15).

Estrategia de extraccion:
1. pdfplumber con bordes visibles (vertical/horizontal_strategy="lines")
2. pdfplumber con alineacion de texto (strategy="text") si no hay bordes
3. PyMuPDF como fallback completo si pdfplumber no esta disponible

Funciones clave:
- analizar_tablas()   → respuesta sincrona rapida (sin riesgo de cuelgue)
- procesar_to_csv()   → procesador asincronico registrado en job_manager
"""

import csv
import io
import logging
import re
import threading
import unicodedata
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import fitz  # PyMuPDF

import config
import models
from utils import file_manager, job_manager

logger = logging.getLogger(__name__)

# Timeout maximo por pagina para find_tables().
# Si la pagina no termina en este tiempo, se usa extraccion por texto como fallback.
# Valor en segundos. 10s es mas que suficiente para paginas normales.
TIMEOUT_PAGINA_SEG = 10

# pdfminer es dependencia de pdfplumber y genera miles de lineas DEBUG por pagina.
# Lo silenciamos aqui ademas de en app.py para mayor seguridad.
for _mod in ['pdfminer', 'pdfminer.psparser', 'pdfminer.pdfinterp',
             'pdfminer.cmapdb', 'pdfminer.pdfpage', 'pdfminer.converter']:
    logging.getLogger(_mod).setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Funciones auxiliares de nombre y texto
# ---------------------------------------------------------------------------

def _normalizar_cabecera(texto: str) -> str:
    """Normaliza texto de cabecera para comparacion: lowercase sin espacios."""
    return texto.strip().lower().replace(' ', '')


def _normalizar_nombre_archivo(texto: str) -> str:
    """
    Convierte texto arbitrario en un nombre de archivo valido (max 20 chars).
    Remueve tildes y caracteres no permitidos en sistemas de archivos.
    """
    # Descomponer Unicode y eliminar marcas de acento
    sin_tildes = unicodedata.normalize('NFKD', str(texto))
    sin_tildes = ''.join(c for c in sin_tildes if not unicodedata.combining(c))
    # Eliminar caracteres invalidos para nombres de archivo
    limpio = re.sub(r'[\\/:*?"<>|\n\r\t]', '_', sin_tildes).strip()
    return limpio[:20] if limpio else 'sin_titulo'


# ---------------------------------------------------------------------------
# Deteccion de titulo de tabla
# ---------------------------------------------------------------------------

def _detectar_titulo_tabla(page, tabla_bbox: Tuple) -> str:
    """
    Busca el titulo de una tabla: texto con letra mas grande o en negrita
    en los ~15 renglones (aprox 210 pt) antes de la posicion superior de la tabla.

    Args:
        page    : pagina de pdfplumber
        tabla_bbox: (x0, top, x1, bottom) de la tabla

    Returns:
        Nombre normalizado (<=20 chars) para usar en el nombre del CSV
    """
    try:
        tabla_top = tabla_bbox[1]
        zona_top  = max(0, tabla_top - 210)   # ~15 lineas de 14pt

        try:
            palabras = page.extract_words(
                extra_attrs=['size', 'fontname'], y_tolerance=3, x_tolerance=3
            )
        except TypeError:
            palabras = page.extract_words(y_tolerance=3, x_tolerance=3)

        # Solo palabras en la zona de busqueda antes de la tabla
        zona = [p for p in palabras if zona_top <= p.get('top', 0) < tabla_top]
        if not zona:
            return 'sin_titulo'

        # Intentar por tamanio de fuente (texto mas grande = titulo)
        if 'size' in zona[0]:
            tam_max = max(p.get('size', 0) for p in zona)
            if tam_max > 0:
                lineas_y = {}
                for p in zona:
                    if p.get('size', 0) >= tam_max * 0.85:
                        y_key = round(p.get('top', 0))
                        lineas_y.setdefault(y_key, []).append(p)
                if lineas_y:
                    y_elegido = max(lineas_y)
                    fila = sorted(lineas_y[y_elegido], key=lambda x: x.get('x0', 0))
                    return _normalizar_nombre_archivo(' '.join(p['text'] for p in fila))

        # Fallback: texto en negrita mas cercano a la tabla
        negritas = [p for p in zona if 'bold' in (p.get('fontname') or '').lower()]
        if negritas:
            y_max = max(p.get('top', 0) for p in negritas)
            fila  = sorted([p for p in negritas if abs(p.get('top', 0) - y_max) < 5],
                           key=lambda x: x.get('x0', 0))
            return _normalizar_nombre_archivo(' '.join(p['text'] for p in fila))

        # Ultimo recurso: ultima linea de texto antes de la tabla
        y_max = max(p.get('top', 0) for p in zona)
        fila  = sorted([p for p in zona if abs(p.get('top', 0) - y_max) < 5],
                       key=lambda x: x.get('x0', 0))
        return _normalizar_nombre_archivo(' '.join(p['text'] for p in fila))

    except Exception as exc:
        logger.debug(f"_detectar_titulo_tabla: {exc}")
        return 'sin_titulo'


# ---------------------------------------------------------------------------
# Extraccion de tablas
# ---------------------------------------------------------------------------

def _limpiar_datos_tabla(datos_raw: List) -> List[List[str]]:
    """
    Convierte datos crudos de pdfplumber/fitz en lista de listas de strings.
    Ignora filas completamente vacias.
    """
    resultado = []
    for fila in (datos_raw or []):
        if fila is None:
            continue
        fila_limpia = [
            str(celda).replace('\n', ' ').strip() if celda is not None else ''
            for celda in fila
        ]
        if any(c for c in fila_limpia):   # descartar filas 100% vacias
            resultado.append(fila_limpia)
    return resultado


def _extraer_tablas_pdfplumber(
    ruta_pdf: Path,
    max_paginas: int = None,
    trabajo_id: str = None,
    progreso_offset: int = 2,
    progreso_rango: int = 68,
) -> List[Dict]:
    """
    Extrae tablas usando pdfplumber (fallback cuando PyMuPDF no encuentra nada).

    Estrategia por pagina:
      1. Bordes visibles   (vertical_strategy="lines", horizontal_strategy="lines")
      2. Alineacion texto  (strategy="text")  si paso 1 no encuentra nada

    Actualiza la barra de progreso del UI en cada pagina si se provee trabajo_id.

    Returns:
        Lista de dicts: pagina, tabla_num, datos, titulo, cabeceras
    """
    import pdfplumber   # import diferido: puede no estar instalado

    tablas = []

    with pdfplumber.open(str(ruta_pdf)) as pdf:
        paginas = pdf.pages[:max_paginas] if max_paginas else pdf.pages
        total   = len(paginas)

        for idx, page in enumerate(paginas):
            num_pagina = idx + 1

            # Actualizar UI: progreso de extraccion pagina a pagina
            if trabajo_id:
                pct = progreso_offset + int((idx / total) * progreso_rango)
                job_manager.actualizar_progreso(
                    trabajo_id, pct,
                    f"[pdfplumber] Extrayendo página {num_pagina}/{total}..."
                )

            tablas_pag = []
            try:
                # Estrategia 1: tablas con bordes dibujados (la mas precisa)
                tablas_pag = page.find_tables(table_settings={
                    "vertical_strategy":   "lines",
                    "horizontal_strategy": "lines",
                })

                # Estrategia 2: tablas sin bordes, detectadas por alineacion de texto
                if not tablas_pag:
                    tablas_pag = page.find_tables(table_settings={
                        "vertical_strategy":   "text",
                        "horizontal_strategy": "text",
                    })

                encontradas_pag = 0
                for idx_t, tabla_obj in enumerate(tablas_pag, start=1):
                    datos = _limpiar_datos_tabla(tabla_obj.extract())
                    if not datos:
                        continue
                    titulo    = _detectar_titulo_tabla(page, tabla_obj.bbox)
                    cabeceras = [_normalizar_cabecera(c) for c in datos[0]]
                    tablas.append({
                        'pagina':    num_pagina,
                        'tabla_num': idx_t,
                        'datos':     datos,
                        'titulo':    titulo,
                        'cabeceras': cabeceras,
                    })
                    encontradas_pag += 1

                logger.info(
                    f"[to-csv] pdfplumber  pag {num_pagina:>4}/{total}  "
                    f"→ {encontradas_pag} tabla(s)"
                )

            except Exception as exc:
                logger.warning(f"[to-csv] pdfplumber  pag {num_pagina}/{total}: {exc}")

    return tablas


def _find_tables_con_timeout(page, timeout_seg: int = TIMEOUT_PAGINA_SEG):
    """
    Ejecuta page.find_tables() en un thread daemon con timeout.

    Si la pagina supera el tiempo limite (e.g. paginas con celdas muy complejas
    que disparan O(n^2) en el algoritmo de interseccion), retorna None.
    El thread interno queda como daemon y se limpia al salir el proceso.

    Returns:
        Objeto TableFinder de fitz, o None si hubo timeout.
    """
    resultado = {'tablas': None}

    def _worker():
        try:
            tabs = page.find_tables()
            if not tabs.tables:
                tabs = page.find_tables(strategy="text")
            resultado['tablas'] = tabs
        except Exception:
            pass  # resultado queda en None

    hilo = threading.Thread(target=_worker, daemon=True)
    hilo.start()
    hilo.join(timeout=timeout_seg)

    if hilo.is_alive():
        # find_tables() sigue corriendo: timeout alcanzado
        return None
    return resultado['tablas']


def _extraer_por_palabras(page) -> List[List[str]]:
    """
    Extrae el contenido de una pagina como tabla usando posicion de palabras.
    Fallback garantizado sin cuelgue: solo llama a page.get_text("words").

    Algoritmo:
    1. Obtener palabras con posiciones (x0, y0, x1, y1, texto)
    2. Agrupar por fila (Y similar con tolerancia de 3pt)
    3. Detectar columnas: los X0 de inicio se agrupan en zonas
    4. Asignar cada palabra a su columna y concatenar multi-palabra

    Returns:
        Lista de filas (lista de strings). Vacio si no parece tabular.
    """
    words = page.get_text("words")   # (x0, y0, x1, y1, texto, blk, ln, wrd)
    if not words:
        return []

    TOLERANCIA_Y  = 3.0   # puntos de tolerancia vertical para agrupar en misma fila
    GAP_COLUMNA   = 15.0  # separacion minima en X para que sea columna nueva

    # --- Paso 1: agrupar palabras por fila ---
    filas: Dict[float, list] = {}
    for w in words:
        x0, y0, x1, y1, texto = w[0], w[1], w[2], w[3], w[4]
        y_key = None
        for yk in filas:
            if abs(yk - y0) <= TOLERANCIA_Y:
                y_key = yk
                break
        if y_key is None:
            y_key = y0
        filas.setdefault(y_key, []).append((x0, x1, texto))

    if not filas:
        return []

    # --- Paso 2: ordenar filas por Y, palabras por X dentro de cada fila ---
    filas_ordenadas = [
        sorted(filas[yk], key=lambda w: w[0])
        for yk in sorted(filas)
    ]

    # --- Paso 3: detectar columnas por clustering de X0 ---
    all_x0 = sorted(set(round(w[0]) for fila in filas_ordenadas for w in fila))
    if not all_x0:
        return []

    columnas = [all_x0[0]]
    for x in all_x0[1:]:
        if x - columnas[-1] > GAP_COLUMNA:
            columnas.append(x)

    if len(columnas) < 2:
        return []   # menos de 2 columnas → no es tabla

    # --- Paso 4: asignar palabras a columnas y construir filas ---
    def _asignar_col(x0_palabra: float) -> int:
        mejor = 0
        for i, col_x in enumerate(columnas):
            if x0_palabra >= col_x - GAP_COLUMNA / 2:
                mejor = i
        return mejor

    datos = []
    for fila in filas_ordenadas:
        celda = [''] * len(columnas)
        for x0, x1, texto in fila:
            col = _asignar_col(x0)
            if col < len(columnas):
                celda[col] = (celda[col] + ' ' + texto).strip()
        if any(c for c in celda):
            datos.append(celda)

    if not datos:
        return []

    # Descartar filas con muy pocas celdas ocupadas (probables headers/footers)
    max_ocup = max(sum(1 for c in fila if c) for fila in datos)
    if max_ocup < 2:
        return []
    datos = [f for f in datos if sum(1 for c in f if c) >= max(2, max_ocup * 0.4)]

    return datos


def _extraer_tablas_fitz(
    ruta_pdf: Path,
    max_paginas: int = None,
    trabajo_id: str = None,
    progreso_offset: int = 2,
    progreso_rango: int = 68,
) -> List[Dict]:
    """
    Extrae tablas usando PyMuPDF — extractor PRIMARIO (implementacion en C, ~10x mas rapido).
    Requiere PyMuPDF >= 1.23.

    Estrategia por pagina:
      1. Deteccion automatica (bordes visibles)
      2. Estrategia texto si paso 1 no encuentra nada (tablas sin bordes)

    Actualiza la barra de progreso del UI en cada pagina si se provee trabajo_id.

    Returns:
        Lista de dicts: pagina, tabla_num, datos, titulo, cabeceras
    """
    tablas = []
    doc    = fitz.open(str(ruta_pdf))
    total  = min(len(doc), max_paginas) if max_paginas else len(doc)

    # FLAG: una vez que find_tables() hace timeout en cualquier pagina,
    # todas las paginas restantes usan extraccion por texto directamente.
    # Esto evita acumular threads daemon bloqueados al 100% CPU.
    usar_solo_texto = False

    for i in range(total):
        num_pagina = i + 1
        page       = doc[i]

        # Actualizar UI: progreso de extraccion pagina a pagina
        if trabajo_id:
            pct = progreso_offset + int((i / total) * progreso_rango)
            job_manager.actualizar_progreso(
                trabajo_id, pct,
                f"Extrayendo página {num_pagina}/{total}..."
            )

        try:
            encontradas_pag = 0

            if usar_solo_texto:
                # Modo texto: find_tables() desactivado para el resto del documento.
                # Se activa al primer timeout para evitar acumular threads bloqueados.
                datos = _extraer_por_palabras(page)
                if datos:
                    cabeceras = [_normalizar_cabecera(c) for c in datos[0]]
                    tablas.append({
                        'pagina':    num_pagina,
                        'tabla_num': 1,
                        'datos':     datos,
                        'titulo':    f'tabla_{num_pagina}_1',
                        'cabeceras': cabeceras,
                    })
                    encontradas_pag = 1
            else:
                # Llamar find_tables() con timeout para evitar cuelgue en paginas complejas
                tabs = _find_tables_con_timeout(page, TIMEOUT_PAGINA_SEG)

                if tabs is None:
                    # TIMEOUT: activar modo texto para TODAS las paginas restantes.
                    # Si esta pagina tarda demasiado, las siguientes tambien lo haran
                    # (mismo formato de documento). Evita acumular threads al 100% CPU.
                    usar_solo_texto = True
                    logger.warning(
                        f"[to-csv] fitz  pag {num_pagina:>4}/{total}  "
                        f"TIMEOUT ({TIMEOUT_PAGINA_SEG}s) → modo texto activado "
                        f"para páginas {num_pagina}-{total}"
                    )
                    datos = _extraer_por_palabras(page)
                    if datos:
                        cabeceras = [_normalizar_cabecera(c) for c in datos[0]]
                        tablas.append({
                            'pagina':    num_pagina,
                            'tabla_num': 1,
                            'datos':     datos,
                            'titulo':    f'tabla_{num_pagina}_1',
                            'cabeceras': cabeceras,
                        })
                        encontradas_pag = 1
                else:
                    # find_tables() completado normalmente
                    for idx_t, tabla in enumerate(tabs.tables, start=1):
                        datos = _limpiar_datos_tabla(tabla.extract())
                        if not datos:
                            continue
                        cabeceras = [_normalizar_cabecera(c) for c in datos[0]]
                        tablas.append({
                            'pagina':    num_pagina,
                            'tabla_num': idx_t,
                            'datos':     datos,
                            'titulo':    f'tabla_{num_pagina}_{idx_t}',
                            'cabeceras': cabeceras,
                        })
                        encontradas_pag += 1

            logger.info(
                f"[to-csv] fitz        pag {num_pagina:>4}/{total}  "
                f"→ {encontradas_pag} tabla(s)"
            )

        except Exception as exc:
            logger.warning(f"[to-csv] fitz        pag {num_pagina}/{total}: {exc}")

    doc.close()
    return tablas


# ---------------------------------------------------------------------------
# Consolidacion de tablas multi-pagina
# ---------------------------------------------------------------------------

def _consolidar_continuaciones(tablas: List[Dict]) -> List[Dict]:
    """
    Fusiona tablas que son continuacion de la tabla de la pagina anterior.

    Caso tipico: tabla de N paginas donde la cabecera solo aparece en pag 1.
    Cada extractor ve N tablas separadas; esta funcion las fusiona en una.

    Criterio de continuacion:
      - Paginas consecutivas (pag_actual == pag_anterior + 1)
      - Mismo numero de columnas

    La primera tabla del grupo conserva su titulo y cabecera.
    Las tablas siguientes aportan sus filas de datos (sin repetir cabecera).
    """
    if len(tablas) <= 1:
        return tablas

    # Ordenar por pagina y numero de tabla dentro de la pagina
    ordenadas = sorted(tablas, key=lambda t: (t['pagina'], t['tabla_num']))

    grupos = [[ordenadas[0]]]

    for tabla_curr in ordenadas[1:]:
        tabla_prev   = grupos[-1][-1]
        cols_prev    = len(tabla_prev['datos'][0]) if tabla_prev['datos'] else 0
        cols_curr    = len(tabla_curr['datos'][0]) if tabla_curr['datos'] else 0
        consecutivas = tabla_curr['pagina'] == tabla_prev['pagina'] + 1
        mismas_cols  = cols_prev == cols_curr and cols_prev > 0

        if consecutivas and mismas_cols:
            grupos[-1].append(tabla_curr)
        else:
            grupos.append([tabla_curr])

    resultado = []
    for grupo in grupos:
        if len(grupo) == 1:
            resultado.append(grupo[0])
        else:
            # Fusionar: datos de la primera + filas de las continuaciones
            tabla_base = dict(grupo[0])
            datos_unidos = list(grupo[0]['datos'])
            for cont in grupo[1:]:
                datos_unidos.extend(cont['datos'])
            tabla_base['datos'] = datos_unidos
            logger.info(
                f"[to-csv] Continuacion detectada: {len(grupo)} paginas fusionadas "
                f"(pags {grupo[0]['pagina']}-{grupo[-1]['pagina']}, "
                f"{len(datos_unidos)} filas totales)"
            )
            resultado.append(tabla_base)

    return resultado


# ---------------------------------------------------------------------------
# Generacion de CSV
# ---------------------------------------------------------------------------

def _generar_csv_bytes(datos: List[List[str]], separador: str, saltos_linea: str) -> bytes:
    """
    Genera bytes del archivo CSV con BOM UTF-8 (compatible con Excel en Windows).

    Args:
        datos       : Lista de filas (cada fila = lista de celdas string)
        separador   : ',' o ';'
        saltos_linea: 'CRLF' o 'LF'

    Returns:
        bytes con BOM UTF-8 al inicio
    """
    terminador = '\r\n' if saltos_linea == 'CRLF' else '\n'
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=separador, quoting=csv.QUOTE_MINIMAL,
                        lineterminator=terminador)
    for fila in datos:
        writer.writerow(fila)
    # BOM UTF-8: hace que Excel reconozca la codificacion automaticamente
    return '\ufeff'.encode('utf-8') + buf.getvalue().encode('utf-8')


def _agrupar_tablas_iguales(tablas: List[Dict]) -> List[List[Dict]]:
    """
    Agrupa tablas que tienen exactamente las mismas cabeceras en el mismo orden.
    Usado cuando el usuario activa la opcion 'unificar_iguales'.

    Returns:
        Lista de grupos. Grupos con 1 elemento = tabla unica.
        Grupos con N>1 elementos = tablas a unificar en un solo CSV.
    """
    grupos        = []
    por_procesar  = list(tablas)

    while por_procesar:
        ref  = por_procesar.pop(0)
        cabs = ref['cabeceras']
        grupo = [ref]
        resto = []
        for t in por_procesar:
            if t['cabeceras'] == cabs:
                grupo.append(t)
            else:
                resto.append(t)
        grupos.append(grupo)
        por_procesar = resto

    return grupos


# ---------------------------------------------------------------------------
# Analisis rapido (endpoint sincrono, sin riesgo de cuelgue)
# ---------------------------------------------------------------------------

def _analizar_rapido_fitz(ruta_pdf: Path, max_paginas: int = 5) -> Dict:
    """
    Detecta si el PDF tiene tablas usando solo metadata geometrica y posicion de texto.
    NO llama a find_tables() → no puede colgarse aunque el PDF sea muy denso.

    Detecta dos tipos:
      - 'bordes' : muchas lineas horizontales y verticales dibujadas (cuadricula)
      - 'texto'  : texto alineado en >=3 columnas consistentes durante >=4 filas
      - 'ninguno': no se detecta patron tabular

    Returns:
        {'tiene_tablas': bool, 'tipo': 'bordes'|'texto'|'ninguno'}
    """
    doc   = fitz.open(str(ruta_pdf))
    total = min(len(doc), max_paginas)

    tiene_bordes      = False
    tiene_texto_tabla = False

    for i in range(total):
        page = doc[i]

        # --- Deteccion por lineas geometricas (cuadricula visible) ---
        drawings = page.get_drawings()
        h_lines = v_lines = 0
        for d in drawings:
            for item in d.get('items', []):
                if item[0] == 'l':             # segmento de linea
                    p1, p2 = item[1], item[2]
                    dy = abs(p2[1] - p1[1])
                    dx = abs(p2[0] - p1[0])
                    if dy < 1.5 and dx > 20:   # horizontal
                        h_lines += 1
                    elif dx < 1.5 and dy > 10: # vertical
                        v_lines += 1
                elif item[0] == 're':          # rectangulo = 4 aristas de tabla
                    h_lines += 2
                    v_lines += 2
        if h_lines >= 4 and v_lines >= 1:
            tiene_bordes = True
            break

        # --- Deteccion por alineacion de texto (tabla sin bordes) ---
        words = page.get_text("words")  # (x0, y0, x1, y1, texto, bloque, linea, palabra)
        if words:
            filas = {}
            for w in words:
                y_key = round(w[1] / 4) * 4      # tolerancia ±4 pt
                filas.setdefault(y_key, []).append(w[0])  # guardar x0

            # Filas con 3 o mas palabras en columna
            filas_multicol = [xs for xs in filas.values() if len(xs) >= 3]
            if len(filas_multicol) >= 4:
                # Las posiciones x se agrupan en zonas consistentes (columnas)
                todos_x0 = sorted(set(round(x / 10) * 10
                                      for xs in filas_multicol for x in xs))
                if len(todos_x0) >= 3:
                    tiene_texto_tabla = True
                    break

    doc.close()
    tipo = 'bordes' if tiene_bordes else ('texto' if tiene_texto_tabla else 'ninguno')
    return {'tiene_tablas': tiene_bordes or tiene_texto_tabla, 'tipo': tipo}


# ---------------------------------------------------------------------------
# Endpoint sincrono de analisis
# ---------------------------------------------------------------------------

def analizar_tablas(archivo_id: str) -> Dict:
    """
    Analiza el PDF y devuelve informacion basica sobre sus tablas.
    Respuesta sincrona, sin riesgo de cuelgue (no usa find_tables()).

    Returns:
        {
            num_tablas       : int   (0 si no hay tablas, 1 como estimacion minima)
            tablas_iguales   : bool  (siempre False en analisis rapido)
            hay_continuaciones: bool (True si el doc tiene multiples paginas con tablas)
            mensaje          : str
            encoding         : str  ('utf-8-bom')
        }
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo fisico no encontrado")

    num_paginas = archivo.get('num_paginas', 0)

    logger.info(f"[to-csv] Analizando {archivo['nombre_original']} ({num_paginas} pags)")
    info     = _analizar_rapido_fitz(ruta_pdf, max_paginas=5)
    tiene    = info['tiene_tablas']
    tipo     = info['tipo']
    logger.info(f"[to-csv] Analisis rapido: tiene_tablas={tiene}, tipo={tipo}")

    if not tiene:
        return {
            'num_tablas':        0,
            'tablas_iguales':    False,
            'hay_continuaciones': False,
            'mensaje':           'No se detectaron tablas (PDF escaneado o solo texto)',
            'encoding':          'utf-8-bom',
        }

    if num_paginas > 5:
        desc_tipo = "con bordes" if tipo == 'bordes' else "sin bordes visibles (alineacion)"
        mensaje   = (f"Tablas {desc_tipo} detectadas. "
                     f"Se extraeran al ejecutar ({num_paginas} paginas).")
    else:
        mensaje = f"Tablas detectadas ({tipo})"

    return {
        'num_tablas':        1,            # estimacion; el conteo real ocurre al ejecutar
        'tablas_iguales':    False,
        'hay_continuaciones': num_paginas > 1,
        'mensaje':           mensaje,
        'encoding':          'utf-8-bom',
    }


# ---------------------------------------------------------------------------
# Procesador principal (asincrono, ejecutado por job_manager)
# ---------------------------------------------------------------------------

def procesar_to_csv(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Extrae todas las tablas del PDF y genera un ZIP con archivos CSV.
    Llamado por job_manager en el thread worker.

    parametros:
        unificar_iguales : bool   unifica tablas con mismas cabeceras (default False)
        separador        : str    ',' o ';'                           (default ';')
        saltos_linea     : str    'CRLF' o 'LF'                      (default 'CRLF')
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo fisico no encontrado")

    nombre_original     = archivo['nombre_original']
    nombre_base_sin_ext = Path(nombre_original).stem

    unificar_iguales = parametros.get('unificar_iguales', False)
    separador        = parametros.get('separador', ';')
    saltos_linea     = parametros.get('saltos_linea', 'CRLF')
    if separador   not in [',', ';']:    separador   = ';'
    if saltos_linea not in ['CRLF', 'LF']: saltos_linea = 'CRLF'

    # --- Paso 1: extraer tablas ---
    # PyMuPDF primero: implementacion en C, ~10x mas rapido que pdfplumber.
    # pdfplumber como fallback: mejor deteccion en tablas muy complejas.
    job_manager.actualizar_progreso(trabajo_id, 2, "Iniciando extraccion de tablas...")
    logger.info(f"[to-csv] Iniciando extraccion: {nombre_original}")

    tablas = _extraer_tablas_fitz(
        ruta_pdf,
        trabajo_id=trabajo_id,
        progreso_offset=2,
        progreso_rango=68,
    )
    logger.info(f"[to-csv] PyMuPDF encontro {len(tablas)} seccion(es)")

    if not tablas:
        logger.info("[to-csv] PyMuPDF no encontro tablas, probando pdfplumber...")
        job_manager.actualizar_progreso(trabajo_id, 2, "Probando extractor alternativo...")
        try:
            import pdfplumber  # noqa: F401
            tablas = _extraer_tablas_pdfplumber(
                ruta_pdf,
                trabajo_id=trabajo_id,
                progreso_offset=2,
                progreso_rango=68,
            )
            logger.info(f"[to-csv] pdfplumber encontro {len(tablas)} seccion(es)")
        except ImportError:
            logger.warning("[to-csv] pdfplumber no disponible")

    if not tablas:
        raise ValueError(
            "No se encontraron tablas en el documento. "
            "El PDF puede ser escaneado (solo imagen) o no contener tablas detectables."
        )

    # --- Paso 2: consolidar continuaciones ---
    job_manager.actualizar_progreso(trabajo_id, 75, "Consolidando tablas multi-pagina...")
    n_antes = len(tablas)
    tablas  = _consolidar_continuaciones(tablas)
    logger.info(f"[to-csv] Consolidacion: {n_antes} secciones → {len(tablas)} tabla(s)")

    # --- Paso 3: generar CSVs ---
    job_manager.actualizar_progreso(trabajo_id, 80, f"Generando CSV para {len(tablas)} tabla(s)...")
    archivos_temp     = []
    archivos_para_zip = []

    if unificar_iguales:
        grupos      = _agrupar_tablas_iguales(tablas)
        total_items = len(grupos)
        for i, grupo in enumerate(grupos):
            pct = 80 + int((i / total_items) * 15)
            job_manager.actualizar_progreso(trabajo_id, pct,
                                            f"Generando CSV {i+1}/{total_items}...")
            ref = grupo[0]
            if len(grupo) == 1:
                nombre_csv = (f"tabla_pag{ref['pagina']}_{ref['tabla_num']}"
                              f"_{ref['titulo']}.csv")
                datos = ref['datos']
            else:
                nombre_csv = (f"tabla_pag{ref['pagina']}_{ref['tabla_num']}"
                              f"_unificada.csv")
                # Cabecera de la primera tabla + filas de datos de todas
                datos = [ref['datos'][0]]
                for t in grupo:
                    datos.extend(t['datos'][1:])
            _escribir_csv_temp(trabajo_id, nombre_csv, datos, separador, saltos_linea,
                               archivos_temp, archivos_para_zip)
    else:
        total_items = len(tablas)
        for i, tabla in enumerate(tablas):
            pct = 80 + int((i / total_items) * 15)
            job_manager.actualizar_progreso(trabajo_id, pct,
                                            f"Generando CSV {i+1}/{total_items}...")
            nombre_csv = (f"tabla_pag{tabla['pagina']}_{tabla['tabla_num']}"
                          f"_{tabla['titulo']}.csv")
            _escribir_csv_temp(trabajo_id, nombre_csv, tabla['datos'],
                               separador, saltos_linea, archivos_temp, archivos_para_zip)

    # --- Paso 4: comprimir ---
    job_manager.actualizar_progreso(trabajo_id, 95, "Comprimiendo archivos CSV...")
    nombre_zip = f"{trabajo_id}_{nombre_base_sin_ext}_csv.zip"
    ruta_zip   = file_manager.crear_zip(archivos_para_zip, nombre_zip)

    # Limpiar CSVs temporales
    for ruta_temp in archivos_temp:
        if ruta_temp.exists():
            ruta_temp.unlink()

    n_csv = len(archivos_para_zip)
    logger.info(f"[to-csv] Finalizado: {n_csv} CSV en {nombre_zip}")
    return {
        'ruta_resultado': str(ruta_zip),
        'mensaje':        f'{n_csv} archivo(s) CSV generado(s)',
    }


def _escribir_csv_temp(
    trabajo_id: str,
    nombre_csv: str,
    datos: List[List[str]],
    separador: str,
    saltos_linea: str,
    archivos_temp: list,
    archivos_para_zip: list,
) -> None:
    """Escribe un CSV temporal y lo agrega a las listas de control."""
    csv_bytes  = _generar_csv_bytes(datos, separador, saltos_linea)
    ruta_temp  = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_csv}"
    ruta_temp.write_bytes(csv_bytes)
    archivos_temp.append(ruta_temp)
    archivos_para_zip.append((str(ruta_temp), nombre_csv))
    logger.info(f"[to-csv] CSV creado: {nombre_csv} ({len(datos)} filas)")


# ---------------------------------------------------------------------------
# Registro del procesador en job_manager
# ---------------------------------------------------------------------------
job_manager.registrar_procesador('to-csv', procesar_to_csv)
