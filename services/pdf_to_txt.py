# -*- coding: utf-8 -*-
"""
Servicio de extraccion de texto de PDF para PDFexport.
Convierte PDF a texto plano con opciones de limpieza.
"""

import logging
import re
from pathlib import Path
from typing import List, Dict, Set
from collections import Counter
from io import StringIO

from pdfminer.high_level import extract_text_to_fp, extract_pages
from pdfminer.layout import LAParams, LTTextContainer, LTChar, LTPage
from pdfminer.pdfpage import PDFPage

import config
import models
from utils import file_manager, job_manager

logger = logging.getLogger(__name__)


def extraer_texto_pagina(pagina: LTPage) -> List[Dict]:
    """
    Extrae bloques de texto de una pagina con su posicion.

    Args:
        pagina: Objeto LTPage de pdfminer

    Returns:
        Lista de bloques con texto y coordenadas
    """
    bloques = []
    altura_pagina = pagina.height

    for elemento in pagina:
        if isinstance(elemento, LTTextContainer):
            texto = elemento.get_text().strip()
            if texto:
                # Coordenadas normalizadas (0-100% de la pagina)
                y_pos = ((altura_pagina - elemento.y1) / altura_pagina) * 100

                bloques.append({
                    'texto': texto,
                    'x0': elemento.x0,
                    'y0': elemento.y0,
                    'x1': elemento.x1,
                    'y1': elemento.y1,
                    'y_porcentaje': y_pos  # 0% = arriba, 100% = abajo
                })

    return bloques


def detectar_encabezados_pies(paginas_bloques: List[List[Dict]], umbral_repeticion: float = 0.8) -> Dict:
    """
    Detecta texto repetido en encabezados y pies de pagina.

    Args:
        paginas_bloques: Lista de bloques por pagina
        umbral_repeticion: Porcentaje minimo de paginas donde debe aparecer (0.8 = 80%)

    Returns:
        Dict con textos de encabezado y pie detectados
    """
    num_paginas = len(paginas_bloques)
    if num_paginas < 3:
        return {'encabezados': set(), 'pies': set()}

    # Recolectar textos en zona superior (0-5%) y zona inferior (95-100%)
    textos_superior = []
    textos_inferior = []

    for bloques in paginas_bloques:
        for bloque in bloques:
            texto_limpio = bloque['texto'].strip()
            if len(texto_limpio) < 100:  # Ignorar bloques muy largos
                if bloque['y_porcentaje'] < 8:  # Zona superior 8%
                    textos_superior.append(texto_limpio)
                elif bloque['y_porcentaje'] > 92:  # Zona inferior 8%
                    textos_inferior.append(texto_limpio)

    # Contar repeticiones
    contador_superior = Counter(textos_superior)
    contador_inferior = Counter(textos_inferior)

    minimo_apariciones = int(num_paginas * umbral_repeticion)

    encabezados = {texto for texto, count in contador_superior.items()
                   if count >= minimo_apariciones and len(texto) > 1}
    pies = {texto for texto, count in contador_inferior.items()
            if count >= minimo_apariciones and len(texto) > 1}

    return {'encabezados': encabezados, 'pies': pies}


def detectar_numeros_pagina(paginas_bloques: List[List[Dict]]) -> Set[str]:
    """
    Detecta patrones de numeros de pagina.

    Args:
        paginas_bloques: Lista de bloques por pagina

    Returns:
        Set de textos que son numeros de pagina
    """
    numeros_detectados = set()

    for i, bloques in enumerate(paginas_bloques):
        num_pagina_esperado = i + 1

        for bloque in bloques:
            texto = bloque['texto'].strip()

            # Solo en zonas de margen (superior/inferior)
            if bloque['y_porcentaje'] < 10 or bloque['y_porcentaje'] > 90:
                # Patron: solo numero
                if texto.isdigit() and int(texto) == num_pagina_esperado:
                    numeros_detectados.add(texto)

                # Patron: "Pagina X", "Pag. X", "- X -", etc.
                patrones = [
                    rf'^{num_pagina_esperado}$',
                    rf'^-\s*{num_pagina_esperado}\s*-$',
                    rf'^página\s+{num_pagina_esperado}$',
                    rf'^pág\.?\s*{num_pagina_esperado}$',
                    rf'^page\s+{num_pagina_esperado}$',
                ]

                for patron in patrones:
                    if re.match(patron, texto.lower()):
                        numeros_detectados.add(texto)

    return numeros_detectados


def limpiar_texto(texto: str, opciones: Dict) -> str:
    """
    Limpia el texto segun las opciones especificadas.

    Args:
        texto: Texto a limpiar
        opciones: Opciones de limpieza

    Returns:
        Texto limpiado
    """
    lineas = texto.split('\n')
    lineas_limpias = []

    for linea in lineas:
        linea_limpia = linea

        # Eliminar espacios multiples
        linea_limpia = re.sub(r' +', ' ', linea_limpia)

        # Eliminar lineas que solo tienen espacios
        if linea_limpia.strip():
            lineas_limpias.append(linea_limpia)
        elif opciones.get('preservar_parrafos', True):
            # Mantener linea vacia para separar parrafos
            if lineas_limpias and lineas_limpias[-1] != '':
                lineas_limpias.append('')

    # Unir lineas
    resultado = '\n'.join(lineas_limpias)

    # Eliminar multiples lineas vacias consecutivas
    resultado = re.sub(r'\n{3,}', '\n\n', resultado)

    return resultado.strip()


def extraer_texto_pdf(ruta_pdf: Path, opciones: Dict, trabajo_id: str) -> str:
    """
    Extrae texto de un PDF con las opciones especificadas.

    Args:
        ruta_pdf: Ruta al archivo PDF
        opciones: Opciones de extraccion
        trabajo_id: ID del trabajo para progreso

    Returns:
        Texto extraido
    """
    remover_encabezados = opciones.get('remover_encabezados', True)
    remover_pies = opciones.get('remover_pies_pagina', True)
    remover_numeros = opciones.get('remover_numeros_pagina', True)
    preservar_parrafos = opciones.get('preservar_parrafos', True)
    detectar_columnas = opciones.get('detectar_columnas', False)

    # Configurar parametros de layout
    laparams = LAParams(
        line_margin=0.5,
        word_margin=0.1,
        char_margin=2.0,
        boxes_flow=0.5 if not detectar_columnas else None,  # None para detectar columnas
        detect_vertical=False
    )

    job_manager.actualizar_progreso(trabajo_id, 10, "Analizando estructura del PDF")

    # Primera pasada: analizar estructura para detectar encabezados/pies
    paginas_bloques = []
    textos_a_remover = set()

    if remover_encabezados or remover_pies or remover_numeros:
        try:
            for pagina in extract_pages(str(ruta_pdf), laparams=laparams):
                bloques = extraer_texto_pagina(pagina)
                paginas_bloques.append(bloques)
        except Exception as e:
            logger.warning(f"Error analizando estructura: {e}")

        if paginas_bloques:
            # Detectar encabezados y pies
            if remover_encabezados or remover_pies:
                detectados = detectar_encabezados_pies(paginas_bloques)
                if remover_encabezados:
                    textos_a_remover.update(detectados['encabezados'])
                if remover_pies:
                    textos_a_remover.update(detectados['pies'])

            # Detectar numeros de pagina
            if remover_numeros:
                numeros = detectar_numeros_pagina(paginas_bloques)
                textos_a_remover.update(numeros)

    job_manager.actualizar_progreso(trabajo_id, 30, "Extrayendo texto")

    # Segunda pasada: extraer texto completo
    output = StringIO()
    with open(str(ruta_pdf), 'rb') as f:
        extract_text_to_fp(f, output, laparams=laparams)

    texto_completo = output.getvalue()

    job_manager.actualizar_progreso(trabajo_id, 70, "Limpiando texto")

    # Remover textos detectados
    for texto_remover in textos_a_remover:
        # Escapar caracteres especiales de regex
        patron = re.escape(texto_remover)
        texto_completo = re.sub(rf'^{patron}\s*$', '', texto_completo, flags=re.MULTILINE)

    # Limpiar texto final
    texto_limpio = limpiar_texto(texto_completo, opciones)

    return texto_limpio


def procesar_to_txt(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal de conversion PDF a TXT.
    Esta funcion es llamada por el job_manager.

    Args:
        trabajo_id: ID del trabajo
        archivo_id: ID del archivo a procesar
        parametros: Opciones de extraccion

    Returns:
        dict con ruta_resultado y mensaje
    """
    # Obtener archivo
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo fisico no encontrado")

    job_manager.actualizar_progreso(trabajo_id, 5, "Iniciando extraccion de texto")

    # Extraer texto
    texto = extraer_texto_pdf(ruta_pdf, parametros, trabajo_id)

    job_manager.actualizar_progreso(trabajo_id, 85, "Guardando archivo")

    # Guardar archivo TXT
    nombre_base = Path(archivo['nombre_original']).stem
    nombre_txt = f"{nombre_base}.txt"
    ruta_txt = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_txt}"

    with open(ruta_txt, 'w', encoding='utf-8') as f:
        f.write(texto)

    # Crear ZIP
    job_manager.actualizar_progreso(trabajo_id, 95, "Comprimiendo archivo")

    nombre_zip = f"{trabajo_id}_{nombre_base}_texto.zip"
    archivos_para_zip = [(str(ruta_txt), nombre_txt)]
    ruta_zip = file_manager.crear_zip(archivos_para_zip, nombre_zip)

    # Limpiar archivo temporal
    if ruta_txt.exists():
        ruta_txt.unlink()

    # Contar lineas y caracteres para el mensaje
    num_lineas = texto.count('\n') + 1
    num_caracteres = len(texto)

    return {
        'ruta_resultado': str(ruta_zip),
        'mensaje': f'Texto extraido: {num_lineas} lineas, {num_caracteres} caracteres'
    }


def obtener_preview_texto(archivo_id: str, opciones: dict, max_lineas: int = 500) -> str:
    """
    Genera una vista previa del texto extraido.

    Args:
        archivo_id: ID del archivo
        opciones: Opciones de extraccion
        max_lineas: Maximo de lineas a retornar

    Returns:
        Preview del texto
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo fisico no encontrado")

    # Extraer texto (sin trabajo_id, sin progreso)
    laparams = LAParams()
    output = StringIO()

    with open(str(ruta_pdf), 'rb') as f:
        extract_text_to_fp(f, output, laparams=laparams, maxpages=5)  # Solo primeras 5 paginas

    texto = output.getvalue()
    texto_limpio = limpiar_texto(texto, opciones)

    # Limitar lineas
    lineas = texto_limpio.split('\n')[:max_lineas]
    return '\n'.join(lineas)


# Registrar el procesador en el job_manager
job_manager.registrar_procesador('to-txt', procesar_to_txt)
