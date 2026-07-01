# -*- coding: utf-8 -*-
"""
Servicio de conversion PDF a Markdown para PDFexport.
Estrategia hibrida: pdfplumber detecta tablas, pdfminer extrae prosa.
"""

import re
import logging
from pathlib import Path

import pdfplumber
from pdfminer.high_level import extract_text

import config
import models
from utils import job_manager

logger = logging.getLogger(__name__)

# Tabla valida: minimo 3 columnas y 20% de filas con contenido
_MIN_COLS = 3
_MIN_FILAS_PCT = 0.20


def _es_tabla_valida(tabla: list) -> bool:
    if not tabla or len(tabla) < 2:
        return False
    num_cols = max((len(f) for f in tabla if f), default=0)
    if num_cols < _MIN_COLS:
        return False
    filas_con_datos = sum(
        1 for f in tabla
        if any(c for c in f if c and str(c).strip())
    )
    return filas_con_datos / len(tabla) >= _MIN_FILAS_PCT


def _tabla_a_md(tabla: list) -> str:
    """Convierte lista de listas (pdfplumber) a pipe table Markdown."""
    if not tabla:
        return ''
    filas = []
    for fila in tabla:
        celdas = [str(c or '').replace('\n', ' ').replace('|', '\\|').strip() for c in fila]
        filas.append(celdas)
    if not filas:
        return ''
    num_cols = max(len(f) for f in filas)
    filas = [f + [''] * (num_cols - len(f)) for f in filas]
    anchos = [max(max(len(f[i]) for f in filas), 3) for i in range(num_cols)]
    lineas = []
    lineas.append('| ' + ' | '.join(filas[0][i].ljust(anchos[i]) for i in range(num_cols)) + ' |')
    lineas.append('| ' + ' | '.join('-' * anchos[i] for i in range(num_cols)) + ' |')
    for fila in filas[1:]:
        lineas.append('| ' + ' | '.join(fila[i].ljust(anchos[i]) for i in range(num_cols)) + ' |')
    return '\n'.join(lineas)


def _es_numero_pagina(linea: str) -> bool:
    """Detecta si una linea es solo un numero de pagina."""
    return bool(re.fullmatch(r'\s*-?\s*\d{1,4}\s*-?\s*', linea) and len(linea.strip()) <= 6)


def _aplicar_opciones_texto(texto: str, opciones: dict) -> str:
    """Limpia texto plano y aplica heuristicas de encabezados Markdown."""
    detectar = opciones.get('detectar_encabezados', True)
    limpiar_nums = opciones.get('limpiar_numeros_pagina', True)

    lineas = texto.split('\n')
    resultado = []
    for linea in lineas:
        if limpiar_nums and _es_numero_pagina(linea):
            continue
        stripped = linea.strip()
        if detectar and stripped:
            # Toda caps, 3-80 chars, sin puntuacion final → H2
            if (stripped.isupper() and 3 <= len(stripped) <= 80
                    and not stripped[-1] in '.,:;'):
                resultado.append(f'## {stripped}')
                continue
            # Titulo corto: primera mayuscula, ≤7 palabras, sin puntuacion final → H3
            if (stripped[0].isupper()
                    and not stripped[-1] in '.,:;'
                    and 3 <= len(stripped) <= 60
                    and len(stripped.split()) <= 7):
                resultado.append(f'### {stripped}')
                continue
        resultado.append(linea)

    out = '\n'.join(resultado)
    out = re.sub(r'\n{3,}', '\n\n', out)
    return out.strip()


def _texto_fuera_tablas(pagina, bboxes_tablas: list) -> str:
    """
    Extrae el texto de una pagina pdfplumber excluyendo las regiones de tabla.
    bbox = (x0, top, x1, bottom) donde top y bottom se miden desde arriba.
    """
    ancho = float(pagina.width)
    altura = float(pagina.height)
    bboxes = sorted(bboxes_tablas, key=lambda b: b[1])  # ordenar por top (desde arriba)

    partes = []
    prev_bottom = 0.0

    for (x0, top, x1, bottom) in bboxes:
        if top > prev_bottom + 2:
            try:
                crop = pagina.crop((0, prev_bottom, ancho, top))
                t = crop.extract_text() or ''
                if t.strip():
                    partes.append(t)
            except Exception:
                pass
        prev_bottom = max(prev_bottom, bottom)

    if prev_bottom < altura - 2:
        try:
            crop = pagina.crop((0, prev_bottom, ancho, altura))
            t = crop.extract_text() or ''
            if t.strip():
                partes.append(t)
        except Exception:
            pass

    return '\n'.join(partes)


def procesar_to_md(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal: convierte PDF a Markdown.
    - Sin tablas validas: pdfminer (mejor para prosa)
    - Con tablas: pdfplumber texto fuera de tablas + pipe tables MD
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo fisico no encontrado")

    incluir_tablas = parametros.get('incluir_tablas', True)

    job_manager.actualizar_progreso(trabajo_id, 5, "Abriendo PDF")

    try:
        with pdfplumber.open(str(ruta_pdf)) as pdf:
            num_pags = len(pdf.pages)
            datos_paginas = []
            hay_tablas = False

            # Fase 1: escanear paginas con pdfplumber
            for i, pag in enumerate(pdf.pages):
                tablas_info = []
                if incluir_tablas:
                    for t_obj in pag.find_tables():
                        datos = t_obj.extract()
                        if datos and _es_tabla_valida(datos):
                            tablas_info.append({'bbox': t_obj.bbox, 'datos': datos})
                            hay_tablas = True
                datos_paginas.append({'pag': pag, 'tablas': tablas_info, 'num': i + 1})
                job_manager.actualizar_progreso(
                    trabajo_id,
                    5 + int((i + 1) / num_pags * 55),
                    f"Analizando pagina {i + 1}/{num_pags}"
                )

            job_manager.actualizar_progreso(trabajo_id, 60, "Generando Markdown")

            if not hay_tablas or not incluir_tablas:
                # Sin tablas: pdfminer da mejor calidad de prosa
                try:
                    texto = extract_text(str(ruta_pdf)) or ''
                except Exception as e:
                    raise ValueError(f"Error extrayendo texto: {e}")

                if not texto.strip():
                    raise ValueError(
                        'No se pudo extraer texto: el PDF parece estar escaneado. '
                        'Proba con "PDF escaneado → CSV" (OCR).'
                    )
                contenido_md = _aplicar_opciones_texto(texto, parametros)

            else:
                # Con tablas: combinar texto + tablas por pagina
                partes_doc = []
                for pag_data in datos_paginas:
                    pag = pag_data['pag']
                    tablas = pag_data['tablas']

                    if not tablas:
                        texto_pag = pag.extract_text() or ''
                        if texto_pag.strip():
                            partes_doc.append(_aplicar_opciones_texto(texto_pag, parametros))
                        continue

                    # Ordenar tablas por posicion vertical (top desde arriba)
                    tablas_ord = sorted(tablas, key=lambda t: t['bbox'][1])
                    bboxes = [t['bbox'] for t in tablas_ord]

                    # Texto fuera de regiones de tabla
                    texto_fuera = _texto_fuera_tablas(pag, bboxes)

                    bloques = []
                    if texto_fuera.strip():
                        bloques.append(_aplicar_opciones_texto(texto_fuera, parametros))
                    for tabla_info in tablas_ord:
                        md_tabla = _tabla_a_md(tabla_info['datos'])
                        if md_tabla:
                            bloques.append(md_tabla)

                    if bloques:
                        partes_doc.append('\n\n'.join(bloques))

                if not partes_doc:
                    raise ValueError('No se pudo extraer contenido del PDF.')

                contenido_md = '\n\n---\n\n'.join(partes_doc)

    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Error procesando PDF: {e}")

    job_manager.actualizar_progreso(trabajo_id, 85, "Guardando archivo")

    nombre_base = Path(archivo['nombre_original']).stem
    ruta_md = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_base}.md"

    with open(ruta_md, 'w', encoding='utf-8') as f:
        f.write(contenido_md)

    num_chars = len(contenido_md)
    num_lineas = contenido_md.count('\n') + 1

    return {
        'ruta_resultado': str(ruta_md),
        'mensaje': f'Markdown generado: {num_lineas} lineas, {num_chars} caracteres'
    }


job_manager.registrar_procesador('to-md', procesar_to_md)
