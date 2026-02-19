# -*- coding: utf-8 -*-
"""
Servicio de conversion de HTML/URL a PDF para PDFexport.
Utiliza WeasyPrint para renderizar paginas web como PDF.
"""

import logging
import re
import hashlib
import concurrent.futures
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
# NOTA: WeasyPrint 60+ elimino FontConfiguration y cambio la API:
#   - font_config ya no se pasa a HTML(), CSS() ni write_pdf()
#   - stylesheets se pasa a render(), no a write_pdf()
#   - Flujo correcto: html.render(stylesheets=[css]).write_pdf(target)
try:
    import requests
    from weasyprint import HTML, CSS
    WEASYPRINT_DISPONIBLE = True
    logger.info("WeasyPrint cargado correctamente")
except (ImportError, OSError) as e:
    WEASYPRINT_DISPONIBLE = False
    logger.warning(f"WeasyPrint no disponible: {e}. El servicio HTML a PDF no funcionara.")

# Timeout para descargar la pagina principal (segundos)
TIMEOUT_PAGINA = 30

# Timeout para cada recurso individual (imagenes, CSS, fonts)
TIMEOUT_RECURSO = 8

# Timeout total para toda la conversion incluyendo renderizado (segundos)
TIMEOUT_TOTAL = 90

# User-Agent para simular navegador
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# Dominios de publicidad, tracking y analytics a bloquear
DOMINIOS_BLOQUEADOS = {
    'doubleclick.net', 'googlesyndication.com', 'googletagmanager.com',
    'google-analytics.com', 'analytics.google.com', 'googleadservices.com',
    'pagead2.googlesyndication.com', 'adservice.google.com',
    'facebook.net', 'connect.facebook.net', 'staticxx.facebook.com',
    'platform.twitter.com', 'syndication.twitter.com',
    'scorecardresearch.com', 'quantserve.com', 'quantcast.com',
    'outbrain.com', 'taboola.com', 'criteo.com', 'criteo.net',
    'adsafeprotected.com', 'moatads.com', 'amazon-adsystem.com',
    'media.net', 'contextweb.com', 'openx.net', 'openx.com',
    'rubiconproject.com', 'pubmatic.com', 'appnexus.com', 'adnxs.com',
    'casalemedia.com', 'advertising.com', 'omtrdc.net',
    'hotjar.com', 'mouseflow.com', 'fullstory.com', 'clarity.ms',
    'newrelic.com', 'nr-data.net', 'bugsnag.com',
    'sentry.io', 'segment.com', 'segment.io',
    'intercom.io', 'intercomcdn.com', 'cdn.ampproject.org',
    'chartbeat.com', 'chartbeat.net', 'parsely.com',
    'optimizely.com', 'mixpanel.com', 'amplitude.com',
}

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
        # Determinar si es la pagina principal o un recurso secundario
        es_pagina_principal = url.rstrip('/') == url_principal.rstrip('/')
        timeout_actual = TIMEOUT_PAGINA if es_pagina_principal else timeout

        # Para URLs de datos (data:...) usar el fetcher por defecto
        if url.startswith('data:'):
            return wp_urls.default_url_fetcher(url)

        # Bloquear dominios de publicidad y tracking
        try:
            dominio = urlparse(url).netloc.lower()
            if dominio.startswith('www.'):
                dominio = dominio[4:]
            for bloqueado in DOMINIOS_BLOQUEADOS:
                if dominio == bloqueado or dominio.endswith('.' + bloqueado):
                    logger.debug(f"Recurso bloqueado (pub/tracking): {url[:80]}")
                    return {'string': b'', 'mime_type': 'text/plain'}
        except Exception:
            pass

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

    # Generar CSS de pagina
    css_pagina = generar_css_pagina(opciones)

    # Agregar CSS para solo contenido si esta activado
    if opciones.get('solo_contenido', False):
        css_pagina += CSS_SOLO_CONTENIDO

    job_manager.actualizar_progreso(trabajo_id, 30, "Descargando y renderizando HTML")

    # Crear URL fetcher con timeout y bloqueo de dominios de publicidad
    url_fetcher = _crear_url_fetcher(url)

    # Generar nombre de salida
    nombre_salida = f"{trabajo_id}_{nombre_base}.pdf"
    ruta_salida = config.OUTPUT_FOLDER / nombre_salida

    def _renderizar():
        """Funcion interna que ejecuta la conversion en un hilo con timeout."""
        # Crear objeto HTML con fetcher personalizado (aplicado a pagina + recursos)
        html = HTML(url=url, url_fetcher=url_fetcher)

        # Crear hoja de estilo (WeasyPrint 60+: sin font_config)
        css = CSS(string=css_pagina)

        job_manager.actualizar_progreso(trabajo_id, 60, "Generando PDF")

        # WeasyPrint 60+ API: stylesheets van a render(), no a write_pdf()
        html.render(stylesheets=[css]).write_pdf(str(ruta_salida))

    # Ejecutar WeasyPrint en un hilo separado con timeout total.
    # IMPORTANTE: NO usar "with executor:" porque su __exit__ llama shutdown(wait=True),
    # que bloquea esperando al thread aunque el timeout ya haya expirado.
    # En su lugar, llamar shutdown(wait=False) manualmente para liberar el control.
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    futuro = executor.submit(_renderizar)

    try:
        futuro.result(timeout=TIMEOUT_TOTAL)
    except concurrent.futures.TimeoutError:
        executor.shutdown(wait=False)  # No bloquear esperando al thread colgado
        logger.warning(f"Timeout WeasyPrint ({TIMEOUT_TOTAL}s): {url[:80]}")
        raise ValueError(
            f"Timeout: la conversion supero {TIMEOUT_TOTAL} segundos. "
            "El sitio puede tener recursos externos que no responden."
        )
    except Exception as e:
        executor.shutdown(wait=False)
        logger.error(f"Error al convertir HTML a PDF: {e}")
        raise ValueError(f"Error al generar PDF: {str(e)}")
    else:
        executor.shutdown(wait=False)

    job_manager.actualizar_progreso(trabajo_id, 95, "Finalizando")

    return ruta_salida


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
        # Generar CSS
        css_pagina = generar_css_pagina(opciones)
        if opciones.get('solo_contenido', False):
            css_pagina += CSS_SOLO_CONTENIDO

        # Crear HTML con fetcher personalizado (mismo que en conversion)
        url_fetcher = _crear_url_fetcher(url)
        html = HTML(url=url, url_fetcher=url_fetcher)
        css = CSS(string=css_pagina)

        # WeasyPrint 60+ API: render() recibe stylesheets, write_pdf() el target
        pdf_bytes = html.render(stylesheets=[css]).write_pdf()

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
