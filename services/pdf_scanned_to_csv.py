# -*- coding: utf-8 -*-
"""
Etapa 22 — PDF Escaneado a CSV usando Apache Tika.

Diferencia clave respecto a Etapa 15 (pdf_to_csv.py):
  - Envia el PDF a Apache Tika (apache/tika:latest-full) via HTTP
  - Tika aplica OCR con Tesseract sobre cada pagina escaneada
  - Retorna HTML con etiquetas <table><tr><td> que se parsean con BeautifulSoup
  - Funciona con PDFs que son imagenes (documentos fisicos escaneados)
  - La Etapa 15 requiere texto real incrustado; esta etapa no.

Flujo:
  PDF → PUT /tika (Accept: text/html, X-Tika-OCRLanguage) → HTML → BS4 → CSV(s) → ZIP
"""

import csv
import io
import logging
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Optional

import config
import models
from utils import file_manager, job_manager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers de texto
# ---------------------------------------------------------------------------

def _normalizar_nombre_archivo(texto: str) -> str:
    """Convierte texto a nombre de archivo valido (max 20 chars, sin tildes)."""
    sin_tildes = unicodedata.normalize('NFKD', str(texto))
    sin_tildes = ''.join(c for c in sin_tildes if not unicodedata.combining(c))
    limpio = re.sub(r'[\\/:*?"<>|\n\r\t]', '_', sin_tildes).strip()
    return limpio[:20] if limpio else 'sin_titulo'


def _normalizar_cabecera(texto: str) -> str:
    """Normaliza cabecera para comparacion: lowercase sin espacios."""
    return texto.strip().lower().replace(' ', '')


def _celda_texto(celda) -> str:
    """Extrae texto limpio de un tag BeautifulSoup de celda."""
    return ' '.join(celda.get_text(separator=' ').split())


# ---------------------------------------------------------------------------
# Comunicacion con Tika
# ---------------------------------------------------------------------------

def _url_tika() -> str:
    """Retorna la URL de Tika con esquema asegurado."""
    url = config.TIKA_URL.rstrip('/')
    if url and not url.startswith(('http://', 'https://')):
        url = f'http://{url}'
    return url


def verificar_tika() -> bool:
    """
    Verifica disponibilidad de Apache Tika haciendo GET al raiz.
    Tika responde con texto que contiene 'Welcome to the Apache Tika'.
    Retorna True si disponible, False si no.
    """
    import requests as _req
    url = _url_tika()
    if not url:
        return False
    try:
        r = _req.get(f'{url}/', timeout=5)
        return r.status_code == 200
    except Exception as exc:
        logger.warning(f'[scanned-csv] Tika no alcanzable ({url}): {exc}')
        return False


def _enviar_pdf_tika(ruta_pdf: Path, idioma_ocr: str = 'spa') -> Optional[str]:
    """
    Envia el PDF a Tika y obtiene el HTML resultante con OCR aplicado.

    Tika PUT /tika con:
      - Content-Type: application/pdf
      - Accept: text/html          → respuesta en HTML con <table>
      - X-Tika-OCRLanguage: spa    → idioma para Tesseract
      - X-Tika-Skip-Embedded: true → ignorar adjuntos incrustados

    Retorna el HTML como string, o None si falla.
    """
    import requests as _req

    url = f'{_url_tika()}/tika'
    headers = {
        'Content-Type': 'application/pdf',
        'Accept': 'text/html',
        'X-Tika-OCRLanguage': idioma_ocr,
        'X-Tika-Skip-Embedded': 'true',
    }

    logger.info(f'[scanned-csv] Enviando {ruta_pdf.name} a Tika ({url}), idioma={idioma_ocr}')
    try:
        with open(str(ruta_pdf), 'rb') as f_pdf:
            resp = _req.put(
                url,
                headers=headers,
                data=f_pdf,
                timeout=600,   # 10 min — OCR de muchas paginas puede tardar
            )
        logger.info(f'[scanned-csv] Tika respuesta: HTTP {resp.status_code}, '
                    f'{len(resp.content)} bytes')
        resp.raise_for_status()
        return resp.content.decode('utf-8')
    except Exception as exc:
        logger.warning(f'[scanned-csv] Error enviando PDF a Tika: {exc}')
        return None


# ---------------------------------------------------------------------------
# Parseo del HTML de Tika
# ---------------------------------------------------------------------------

def _parsear_tablas_html(html: str) -> List[Dict]:
    """
    Parsea el HTML retornado por Tika y extrae todas las tablas.

    Tika devuelve HTML con <div class="page"> por pagina y <table> dentro.
    Cada <table> se convierte a List[List[str]].

    Retorna lista de dicts: pagina, tabla_num, datos, titulo, cabeceras
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, 'lxml')
    tablas_resultado = []
    tabla_num_por_pagina: Dict[int, int] = {}

    # Tika envuelve cada pagina en <div class="page">
    paginas = soup.find_all('div', class_='page')

    # Si Tika no usa divs de pagina, tomar el body completo como pagina 1
    if not paginas:
        body = soup.find('body')
        paginas = [body] if body else []

    for num_pagina, div_pagina in enumerate(paginas, start=1):
        tablas_html = div_pagina.find_all('table') if div_pagina else []

        for tabla_tag in tablas_html:
            filas = _tabla_a_filas(tabla_tag)
            if not filas or len(filas) < 1:
                continue

            # Ignorar tablas de 1 celda (probablemente layout, no datos)
            total_celdas = sum(len(f) for f in filas)
            if total_celdas <= 1:
                continue

            tabla_num_por_pagina[num_pagina] = tabla_num_por_pagina.get(num_pagina, 0) + 1
            tabla_num = tabla_num_por_pagina[num_pagina]

            # Buscar titulo: texto inmediatamente antes de la tabla en el div
            titulo = _buscar_titulo_antes(tabla_tag)

            cabeceras = [_normalizar_cabecera(c) for c in filas[0]]

            tablas_resultado.append({
                'pagina':    num_pagina,
                'tabla_num': tabla_num,
                'datos':     filas,
                'titulo':    titulo,
                'cabeceras': cabeceras,
            })

    logger.info(f'[scanned-csv] Tablas encontradas en HTML Tika: {len(tablas_resultado)}')
    return tablas_resultado


def _tabla_a_filas(tabla_tag) -> List[List[str]]:
    """Convierte un tag <table> de BS4 a List[List[str]]."""
    filas = []
    for tr in tabla_tag.find_all('tr'):
        celdas = tr.find_all(['td', 'th'])
        if not celdas:
            continue
        fila = [_celda_texto(c) for c in celdas]
        # Ignorar filas completamente vacias
        if any(c.strip() for c in fila):
            filas.append(fila)
    return filas


def _buscar_titulo_antes(tabla_tag) -> str:
    """
    Busca titulo buscando hacia atras hasta 10 elementos hermanos anteriores.
    Prioriza texto en negrita, encabezados (h1-h6) o parrafos con letra grande.
    """
    candidatos = []
    elemento = tabla_tag.previous_sibling
    intentos = 0

    while elemento and intentos < 10:
        if hasattr(elemento, 'get_text'):
            texto = ' '.join(elemento.get_text(separator=' ').split())
            if texto and len(texto) > 2:
                # Dar mas peso a encabezados
                tag = getattr(elemento, 'name', '')
                peso = 2 if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6') else 1
                candidatos.append((peso, texto))
        elemento = elemento.previous_sibling
        intentos += 1

    if not candidatos:
        return 'sin_titulo'

    # El candidato con mayor peso (o el mas reciente si empatan)
    candidatos.sort(key=lambda x: -x[0])
    return _normalizar_nombre_archivo(candidatos[0][1])


# ---------------------------------------------------------------------------
# Generacion de CSVs
# ---------------------------------------------------------------------------

def _unificar_tablas(tablas: List[Dict]) -> List[Dict]:
    """
    Agrupa tablas con las mismas cabeceras (en el mismo orden) en una sola.
    Solo unifica si las cabeceras son identicas y en el mismo orden.
    """
    grupos: Dict[tuple, Dict] = {}

    for tabla in tablas:
        clave = tuple(tabla['cabeceras'])
        if clave not in grupos:
            grupos[clave] = {
                'pagina':    tabla['pagina'],
                'tabla_num': tabla['tabla_num'],
                'datos':     list(tabla['datos']),   # incluye cabecera
                'titulo':    tabla['titulo'],
                'cabeceras': tabla['cabeceras'],
                'unificada': False,
            }
        else:
            # Agregar filas sin repetir cabecera
            grupos[clave]['datos'].extend(tabla['datos'][1:])
            grupos[clave]['unificada'] = True

    return list(grupos.values())


def _generar_csvs(
    tablas: List[Dict],
    trabajo_id: str,
    nombre_base: str,
    separador: str = ';',
    saltos_linea: str = 'CRLF',
    unificar: bool = False,
) -> List[tuple]:
    """
    Genera archivos CSV en OUTPUT_FOLDER para cada tabla.

    Retorna lista de tuplas (ruta_absoluta, nombre_para_zip).
    """
    if unificar:
        tablas = _unificar_tablas(tablas)

    line_terminator = '\r\n' if saltos_linea == 'CRLF' else '\n'
    archivos = []

    # Padding para numeracion
    total = len(tablas)
    padding = len(str(total))

    for idx, tabla in enumerate(tablas, start=1):
        num_str = str(idx).zfill(padding)
        sufijo = '_unificada' if tabla.get('unificada') else ''
        nombre_archivo = (
            f'tabla_pag{tabla["pagina"]}_{tabla["tabla_num"]}'
            f'_{tabla["titulo"]}{sufijo}.csv'
        )
        nombre_en_zip = nombre_archivo
        ruta_salida = config.OUTPUT_FOLDER / f'{trabajo_id}_{num_str}_{nombre_archivo}'

        buf = io.StringIO()
        # utf-8-bom para compatibilidad con Excel en Windows
        writer = csv.writer(buf, delimiter=separador, lineterminator=line_terminator)
        for fila in tabla['datos']:
            writer.writerow(fila)

        contenido = '\ufeff' + buf.getvalue()   # BOM UTF-8
        with open(str(ruta_salida), 'w', encoding='utf-8', newline='') as f:
            f.write(contenido)

        archivos.append((ruta_salida, nombre_en_zip))
        logger.info(f'[scanned-csv] CSV generado: {nombre_archivo} '
                    f'({len(tabla["datos"])} filas)')

    return archivos


# ---------------------------------------------------------------------------
# Analisis sincrono (para mostrar estado en UI antes de procesar)
# ---------------------------------------------------------------------------

def analizar_pdf_escaneado(archivo_id: str) -> dict:
    """
    Verificacion rapida sincrona: comprueba si Tika esta disponible
    y retorna estado para mostrar en la UI antes de iniciar el job.

    No envia el PDF — solo hace health check de Tika.
    """
    tika_ok = verificar_tika()

    return {
        'tika_disponible': tika_ok,
        'tika_url': _url_tika() if tika_ok else '',
        'mensaje': (
            'Tika disponible — listo para procesar PDF escaneado'
            if tika_ok else
            'Tika no disponible. Verificar contenedor apache/tika:latest-full'
        ),
    }


# ---------------------------------------------------------------------------
# Procesador principal (asincrono, registrado en job_manager)
# ---------------------------------------------------------------------------

def procesar_scanned_to_csv(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal para PDF escaneado a CSV.
    Registrado en job_manager como 'to-csv-ocr'.

    parametros esperados:
      separador   : ';' o ','
      saltos_linea: 'CRLF' o 'LF'
      idioma_ocr  : 'spa', 'eng', 'spa+eng', etc. (Tesseract lang)
      unificar    : bool — unificar tablas con mismas cabeceras
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError('Archivo no encontrado')

    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError('Archivo fisico no encontrado')

    nombre_original = archivo['nombre_original']
    nombre_base = Path(nombre_original).stem

    separador    = parametros.get('separador', ';')
    saltos_linea = parametros.get('saltos_linea', 'CRLF')
    idioma_ocr   = parametros.get('idioma_ocr', 'spa')
    unificar     = parametros.get('unificar', False)

    # Paso 1: verificar Tika
    job_manager.actualizar_progreso(trabajo_id, 2, 'Verificando servicio Tika...')
    if not verificar_tika():
        raise ValueError(
            f'Tika no disponible en {_url_tika()}. '
            'Verificar que el contenedor apache/tika:latest-full este corriendo.'
        )

    # Paso 2: enviar PDF a Tika con OCR
    job_manager.actualizar_progreso(
        trabajo_id, 5,
        f'Enviando PDF a Tika para OCR (idioma: {idioma_ocr})...'
    )
    html = _enviar_pdf_tika(ruta_pdf, idioma_ocr=idioma_ocr)
    if not html:
        raise ValueError(
            'Tika no pudo procesar el PDF. '
            'Verificar logs del contenedor Tika para mas detalles.'
        )

    # Paso 3: parsear HTML y extraer tablas
    job_manager.actualizar_progreso(trabajo_id, 75, 'Extrayendo tablas del resultado OCR...')
    tablas = _parsear_tablas_html(html)

    if not tablas:
        raise ValueError(
            'No se encontraron tablas en el documento. '
            'El PDF puede no contener tablas, o el OCR no pudo reconocerlas.'
        )

    # Paso 4: generar CSVs
    job_manager.actualizar_progreso(trabajo_id, 85, f'Generando {len(tablas)} archivo(s) CSV...')
    archivos_csv = _generar_csvs(
        tablas,
        trabajo_id=trabajo_id,
        nombre_base=nombre_base,
        separador=separador,
        saltos_linea=saltos_linea,
        unificar=unificar,
    )

    # Paso 5: comprimir en ZIP
    job_manager.actualizar_progreso(trabajo_id, 92, 'Comprimiendo archivos CSV...')
    nombre_zip = f'{trabajo_id}_{nombre_base}_csv_ocr.zip'
    archivos_para_zip = [(str(r), n) for r, n in archivos_csv]
    ruta_zip = file_manager.crear_zip(archivos_para_zip, nombre_zip)

    # Limpiar temporales
    for ruta, _ in archivos_csv:
        if ruta.exists():
            ruta.unlink()

    return {
        'ruta_resultado': str(ruta_zip),
        'mensaje': f'{len(archivos_csv)} tabla(s) extraida(s) via OCR',
    }


# Registrar procesador
job_manager.registrar_procesador('to-csv-ocr', procesar_scanned_to_csv)
