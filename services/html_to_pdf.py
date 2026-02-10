# -*- coding: utf-8 -*-
"""
Servicio de conversion de HTML/URL a PDF para PDFexport.
Utiliza WeasyPrint para renderizar paginas web como PDF.
"""

import logging
import re
import hashlib
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

import config
from utils import job_manager

logger = logging.getLogger(__name__)

# En Windows, agregar ruta de MSYS2/GTK3 al PATH antes de importar WeasyPrint
import os
import sys
if sys.platform == 'win32':
    # Rutas comunes de MSYS2 donde se instalan las DLLs de GTK3
    rutas_gtk = [
        r'C:\msys64\ucrt64\bin',
        r'C:\msys64\mingw64\bin',
        r'C:\msys64\mingw32\bin',
    ]
    for ruta in rutas_gtk:
        if os.path.isdir(ruta):
            os.environ['PATH'] = ruta + os.pathsep + os.environ.get('PATH', '')
            # add_dll_directory disponible en Python 3.8+
            try:
                os.add_dll_directory(ruta)
            except (OSError, AttributeError):
                pass
            logger.info(f"Ruta GTK3 agregada: {ruta}")
            break

# Importar WeasyPrint y requests de forma condicional
try:
    import requests
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    WEASYPRINT_DISPONIBLE = True
    logger.info("WeasyPrint cargado correctamente")
except (ImportError, OSError) as e:
    WEASYPRINT_DISPONIBLE = False
    logger.warning(f"WeasyPrint no disponible: {e}. El servicio HTML a PDF no funcionara.")

# Timeout para descargar la pagina principal (segundos)
TIMEOUT_PAGINA = 60

# Timeout para cada recurso individual (imagenes, CSS, fonts)
TIMEOUT_RECURSO = 15

# User-Agent para simular navegador
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# Tamanos de pagina en mm
TAMANOS_PAGINA = {
    'A4': {'width': '210mm', 'height': '297mm'},
    'A3': {'width': '297mm', 'height': '420mm'},
    'Letter': {'width': '216mm', 'height': '279mm'},
    'Legal': {'width': '216mm', 'height': '356mm'}
}

# Margenes predefinidos
MARGENES = {
    'sin_margenes': '0',
    'normales': '20mm',
    'amplios': '30mm'
}

# CSS para remover elementos no deseados en modo "solo contenido"
CSS_SOLO_CONTENIDO = """
    nav, header, footer, aside, .nav, .navbar, .header, .footer, .sidebar,
    .advertisement, .ad, .ads, .banner, .cookie-banner, .popup, .modal,
    #nav, #navbar, #header, #footer, #sidebar, #advertisement,
    [role="navigation"], [role="banner"], [role="contentinfo"] {
        display: none !important;
    }
"""


def generar_css_pagina(opciones: Dict) -> str:
    """
    Genera el CSS para configurar el tamano y margenes de la pagina.

    Args:
        opciones: Diccionario con opciones de conversion

    Returns:
        String con CSS para @page
    """
    tamano = opciones.get('tamano_pagina', 'A4')
    orientacion = opciones.get('orientacion', 'vertical')
    margenes = opciones.get('margenes', 'normales')
    incluir_fondo = opciones.get('incluir_fondo', True)

    # Obtener dimensiones
    dims = TAMANOS_PAGINA.get(tamano, TAMANOS_PAGINA['A4'])

    # Intercambiar dimensiones si es horizontal
    if orientacion == 'horizontal':
        width = dims['height']
        height = dims['width']
    else:
        width = dims['width']
        height = dims['height']

    # Obtener margen
    margen = MARGENES.get(margenes, MARGENES['normales'])

    # Construir CSS
    css = f"""
        @page {{
            size: {width} {height};
            margin: {margen};
        }}
    """

    # Si no incluir fondo, forzar fondo blanco
    if not incluir_fondo:
        css += """
            body {
                background: white !important;
                background-color: white !important;
            }
            * {
                background-image: none !important;
            }
        """

    return css


def _verificar_weasyprint():
    """Verifica que WeasyPrint esta disponible antes de usarlo."""
    if not WEASYPRINT_DISPONIBLE:
        raise ValueError(
            "WeasyPrint no esta disponible en este sistema. "
            "Este servicio requiere GTK3 (disponible en Docker/Linux)."
        )


def _crear_url_fetcher(url_principal: str):
    """
    Crea un URL fetcher personalizado para WeasyPrint.
    Usa requests con timeout y manejo de errores por recurso.
    Si un recurso (imagen, CSS, font) falla, lo omite en vez de abortar todo.

    Args:
        url_principal: URL de la pagina principal (para dar mas timeout)

    Returns:
        Funcion url_fetcher compatible con WeasyPrint
    """
    from weasyprint import urls as wp_urls

    def url_fetcher(url, timeout=TIMEOUT_RECURSO, **kwargs):
        # Determinar timeout segun si es la pagina principal o un recurso
        es_pagina_principal = url.rstrip('/') == url_principal.rstrip('/')
        timeout_actual = TIMEOUT_PAGINA if es_pagina_principal else timeout

        # Para URLs de datos (data:...) usar el fetcher por defecto
        if url.startswith('data:'):
            return wp_urls.default_url_fetcher(url)

        try:
            headers = {'User-Agent': USER_AGENT}
            respuesta = requests.get(
                url,
                timeout=timeout_actual,
                headers=headers,
                verify=False  # Algunos sitios tienen certificados problematicos
            )
            respuesta.raise_for_status()

            # Detectar tipo de contenido
            content_type = respuesta.headers.get('Content-Type', 'text/html')

            return {
                'string': respuesta.content,
                'mime_type': content_type.split(';')[0].strip(),
                'encoding': respuesta.encoding,
                'redirected_url': respuesta.url,
            }

        except requests.Timeout:
            if es_pagina_principal:
                raise ValueError(f"Timeout al descargar la pagina principal (limite: {TIMEOUT_PAGINA}s)")
            # Para recursos secundarios, devolver vacio para que no falle todo
            logger.warning(f"Timeout descargando recurso (omitido): {url[:100]}")
            return {'string': b'', 'mime_type': 'text/plain'}

        except requests.RequestException as e:
            if es_pagina_principal:
                raise ValueError(f"Error al descargar la pagina: {str(e)}")
            # Omitir recursos que fallan
            logger.warning(f"Error descargando recurso (omitido): {url[:100]} - {e}")
            return {'string': b'', 'mime_type': 'text/plain'}

    return url_fetcher


def convertir_url_a_pdf(url: str, opciones: Dict, trabajo_id: str) -> Path:
    """
    Convierte una URL a PDF.

    Args:
        url: URL de la pagina web
        opciones: Opciones de conversion
        trabajo_id: ID del trabajo para progreso

    Returns:
        Ruta al archivo PDF generado
    """
    _verificar_weasyprint()

    job_manager.actualizar_progreso(trabajo_id, 5, "Descargando pagina web")

    # Generar nombre de archivo basado en URL
    parsed_url = urlparse(url)
    nombre_base = parsed_url.netloc.replace('.', '_')
    if parsed_url.path and parsed_url.path != '/':
        path_clean = re.sub(r'[^\w\-]', '_', parsed_url.path)
        nombre_base += path_clean[:50]  # Limitar longitud

    job_manager.actualizar_progreso(trabajo_id, 15, "Preparando conversion")

    # Configurar fuentes
    font_config = FontConfiguration()

    # Generar CSS de pagina
    css_pagina = generar_css_pagina(opciones)

    # Agregar CSS para solo contenido si esta activado
    if opciones.get('solo_contenido', False):
        css_pagina += CSS_SOLO_CONTENIDO

    job_manager.actualizar_progreso(trabajo_id, 30, "Renderizando HTML")

    try:
        # Crear objeto HTML desde URL
        html = HTML(url=url)

        # Crear hoja de estilo
        css = CSS(string=css_pagina, font_config=font_config)

        job_manager.actualizar_progreso(trabajo_id, 60, "Generando PDF")

        # Generar nombre de salida
        nombre_salida = f"{trabajo_id}_{nombre_base}.pdf"
        ruta_salida = config.OUTPUT_FOLDER / nombre_salida

        # Renderizar PDF
        html.write_pdf(
            str(ruta_salida),
            stylesheets=[css],
            font_config=font_config
        )

        job_manager.actualizar_progreso(trabajo_id, 95, "Finalizando")

        return ruta_salida

    except Exception as e:
        logger.error(f"Error al convertir HTML a PDF: {e}")
        raise ValueError(f"Error al generar PDF: {str(e)}")


def obtener_vista_previa(url: str, opciones: Dict) -> Optional[bytes]:
    """
    Genera una vista previa (primera pagina) del PDF.

    Args:
        url: URL de la pagina
        opciones: Opciones de conversion

    Returns:
        Bytes de la imagen PNG de la primera pagina, o None si falla
    """
    import fitz  # PyMuPDF

    _verificar_weasyprint()

    try:
        # Configurar fuentes
        font_config = FontConfiguration()

        # Generar CSS
        css_pagina = generar_css_pagina(opciones)
        if opciones.get('solo_contenido', False):
            css_pagina += CSS_SOLO_CONTENIDO

        # Crear HTML y CSS
        html = HTML(url=url)
        css = CSS(string=css_pagina, font_config=font_config)

        # Renderizar a bytes
        pdf_bytes = html.write_pdf(stylesheets=[css], font_config=font_config)

        # Abrir con PyMuPDF para extraer primera pagina como imagen
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if len(doc) > 0:
            pagina = doc[0]
            # Renderizar a imagen con DPI moderado para preview
            mat = fitz.Matrix(1.5, 1.5)  # ~108 DPI
            pix = pagina.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            doc.close()
            return img_bytes

        doc.close()
        return None

    except Exception as e:
        logger.error(f"Error generando vista previa: {e}")
        return None


def procesar_from_html(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal de conversion HTML a PDF.
    Esta funcion es llamada por el job_manager.

    Nota: archivo_id no se usa en este caso, la URL viene en parametros.

    Args:
        trabajo_id: ID del trabajo
        archivo_id: No usado (None)
        parametros: Parametros con URL y opciones
            - url: URL de la pagina web
            - opciones: Dict con opciones de conversion

    Returns:
        dict con ruta_resultado y mensaje
    """
    url = parametros.get('url')
    if not url:
        raise ValueError("No se especifico URL")

    opciones = parametros.get('opciones', {})

    job_manager.actualizar_progreso(trabajo_id, 2, "Iniciando conversion")

    # Convertir
    ruta_resultado = convertir_url_a_pdf(url, opciones, trabajo_id)

    return {
        'ruta_resultado': str(ruta_resultado),
        'mensaje': 'Pagina web convertida a PDF'
    }


# Registrar el procesador en el job_manager
job_manager.registrar_procesador('from_html', procesar_from_html)
