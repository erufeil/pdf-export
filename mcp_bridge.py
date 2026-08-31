# -*- coding: utf-8 -*-
"""
MCP bridge de PDFexport — expone la conversión PDF → Markdown como tool MCP.

Reutiliza las funciones puras de services/pdf_to_md.py (sin Flask, sin DB, sin
job_manager) para que Hermes / cualquier cliente MCP pueda convertir PDFs
directamente desde el sistema de archivos.

Ejecución: <venv>\\Scripts\\python.exe mcp_bridge.py   (protocolo stdio)
"""
import sys
from pathlib import Path

PROYECTO = Path(__file__).parent
if str(PROYECTO) not in sys.path:
    sys.path.insert(0, str(PROYECTO))

# Importa services/pdf_to_md.py: sus imports (config, models, job_manager) son
# livianos y no requieren Flask ni base de datos viva. Solo usamos sus helpers.
from services.pdf_to_md import (
    _es_tabla_valida,
    _tabla_a_md,
    _aplicar_opciones_texto,
    _texto_fuera_tablas,
)

import pdfplumber
from pdfminer.high_level import extract_text
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("pdfexport")


def _convertir(pdf_path: Path, incluir_tablas: bool = True,
               detectar_encabezados: bool = True,
               limpiar_numeros_pagina: bool = True) -> str:
    """Nucleo de conversion: PDF -> Markdown (misma logica que procesar_to_md)."""
    if not pdf_path.exists():
        raise ValueError(f"Archivo no encontrado: {pdf_path}")

    parametros = {
        'incluir_tablas': incluir_tablas,
        'detectar_encabezados': detectar_encabezados,
        'limpiar_numeros_pagina': limpiar_numeros_pagina,
    }

    with pdfplumber.open(str(pdf_path)) as pdf:
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
            datos_paginas.append({'pag': pag, 'tablas': tablas_info})

        if not hay_tablas:
            # Sin tablas: pdfminer da mejor calidad de prosa
            try:
                texto = extract_text(str(pdf_path)) or ''
            except Exception as e:
                raise ValueError(f"Error extrayendo texto: {e}")

            if not texto.strip():
                raise ValueError(
                    'No se pudo extraer texto: el PDF parece estar escaneado '
                    '(requiere OCR).'
                )
            return _aplicar_opciones_texto(texto, parametros)

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

            tablas_ord = sorted(tablas, key=lambda t: t['bbox'][1])
            bboxes = [t['bbox'] for t in tablas_ord]
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

        return '\n\n---\n\n'.join(partes_doc)


@mcp.tool()
def convert_pdf_to_md(pdf_path: str, output_path: str = "",
                      incluir_tablas: bool = True) -> str:
    """Convierte un PDF local a Markdown (.md) reutilizando el motor de PDFexport.

    Args:
        pdf_path: Ruta absoluta del PDF a convertir.
        output_path: Ruta del .md de salida (si va vacia, se crea junto al PDF
            con el mismo nombre y extension .md).
        incluir_tablas: Si es True detecta tablas y las emite como pipe tables.

    Returns:
        Ruta del archivo .md generado + estadisticas (lineas, caracteres).
    """
    origen = Path(pdf_path)
    destino = Path(output_path) if output_path else origen.with_suffix('.md')

    contenido = _convertir(origen, incluir_tablas=incluir_tablas)

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding='utf-8')

    num_chars = len(contenido)
    num_lineas = contenido.count('\n') + 1
    return (f"Markdown generado en: {destino} "
            f"({num_lineas} lineas, {num_chars} caracteres)")


if __name__ == "__main__":
    mcp.run()
