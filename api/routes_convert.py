# -*- coding: utf-8 -*-
"""
Endpoints de la API para conversiones de PDF.
Maneja todas las operaciones de conversion y transformacion.
"""

from flask import Blueprint, request, jsonify
import logging

import models
from utils import job_manager

logger = logging.getLogger(__name__)

# Blueprint para rutas de conversion
bp = Blueprint('convert', __name__, url_prefix='/api/v1/convert')


def respuesta_exitosa(data=None, mensaje="Operacion completada"):
    """Genera respuesta JSON exitosa estandarizada."""
    return jsonify({
        'success': True,
        'data': data,
        'message': mensaje
    })


def respuesta_error(codigo: str, mensaje: str, status_code: int = 400):
    """Genera respuesta JSON de error estandarizada."""
    return jsonify({
        'success': False,
        'error': {
            'code': codigo,
            'message': mensaje
        }
    }), status_code


def validar_archivo(archivo_id: str):
    """
    Valida que el archivo existe y retorna su info.
    Lanza excepcion si no existe.
    """
    if not archivo_id:
        return None, respuesta_error('MISSING_FILE_ID', 'Se requiere file_id')

    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        return None, respuesta_error('FILE_NOT_FOUND', 'Archivo no encontrado', 404)

    return archivo, None


@bp.route('/split', methods=['POST'])
def convertir_split():
    """
    Corta un PDF en multiples partes.

    Espera JSON:
    - file_id: ID del archivo a cortar
    - opciones:
        - cortes: Lista de rangos [{inicio, fin, nombre}, ...]
        - num_partes: Alternativa - numero de partes iguales

    Retorna:
    - Info del trabajo creado
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')
    opciones = datos.get('opciones', {})

    # Validar archivo
    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    # Validar que hay cortes o num_partes
    if not opciones.get('cortes') and not opciones.get('num_partes'):
        return respuesta_error(
            'MISSING_PARAMS',
            'Debe especificar cortes o num_partes'
        )

    # Crear trabajo
    try:
        trabajo_id = job_manager.encolar_trabajo(
            archivo_id=archivo_id,
            tipo_conversion='split',
            parametros=opciones
        )

        trabajo = models.obtener_trabajo(trabajo_id)

        return respuesta_exitosa({
            'job_id': trabajo_id,
            'estado': trabajo['estado'],
            'mensaje': 'Trabajo de corte iniciado'
        }, 'Trabajo encolado correctamente')

    except Exception as e:
        logger.error(f"Error creando trabajo de corte: {e}")
        return respuesta_error('JOB_ERROR', str(e), 500)


@bp.route('/to-txt', methods=['POST'])
def convertir_to_txt():
    """
    Convierte PDF a texto plano.

    Espera JSON:
    - file_id: ID del archivo
    - opciones:
        - remover_numeros_pagina: bool
        - remover_encabezados: bool
        - remover_pies_pagina: bool
        - preservar_parrafos: bool
        - detectar_columnas: bool

    Retorna:
    - Info del trabajo creado
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')
    opciones = datos.get('opciones', {})

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    # Crear trabajo
    try:
        trabajo_id = job_manager.encolar_trabajo(
            archivo_id=archivo_id,
            tipo_conversion='to-txt',
            parametros=opciones
        )

        trabajo = models.obtener_trabajo(trabajo_id)

        return respuesta_exitosa({
            'job_id': trabajo_id,
            'estado': trabajo['estado'],
            'mensaje': 'Extraccion de texto iniciada'
        }, 'Trabajo encolado correctamente')

    except Exception as e:
        logger.error(f"Error creando trabajo to-txt: {e}")
        return respuesta_error('JOB_ERROR', str(e), 500)


@bp.route('/to-txt/preview', methods=['POST'])
def preview_to_txt():
    """
    Genera vista previa del texto extraido (primeras 500 lineas).

    Espera JSON:
    - file_id: ID del archivo
    - opciones: Opciones de extraccion

    Retorna:
    - Vista previa del texto
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')
    opciones = datos.get('opciones', {})

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    try:
        from services.pdf_to_txt import obtener_preview_texto
        preview = obtener_preview_texto(archivo_id, opciones)

        return respuesta_exitosa({
            'preview': preview,
            'lineas': preview.count('\n') + 1
        }, 'Vista previa generada')

    except Exception as e:
        logger.error(f"Error generando preview: {e}")
        return respuesta_error('PREVIEW_ERROR', str(e), 500)


@bp.route('/to-docx', methods=['POST'])
def convertir_to_docx():
    """
    Convierte PDF a DOCX (documento Word).

    Espera JSON:
    - file_id: ID del archivo
    - opciones:
        - preservar_imagenes: bool
        - preservar_tablas: bool
        - preservar_estilos: bool
        - calidad_imagenes: 'baja' | 'media' | 'alta' | 'original'

    Retorna:
    - Info del trabajo creado
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')
    opciones = datos.get('opciones', {})

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    # Crear trabajo
    try:
        trabajo_id = job_manager.encolar_trabajo(
            archivo_id=archivo_id,
            tipo_conversion='to-docx',
            parametros=opciones
        )

        trabajo = models.obtener_trabajo(trabajo_id)

        return respuesta_exitosa({
            'job_id': trabajo_id,
            'estado': trabajo['estado'],
            'mensaje': 'Conversion a DOCX iniciada'
        }, 'Trabajo encolado correctamente')

    except Exception as e:
        logger.error(f"Error creando trabajo to-docx: {e}")
        return respuesta_error('JOB_ERROR', str(e), 500)


@bp.route('/to-docx/preview', methods=['POST'])
def preview_to_docx():
    """
    Obtiene informacion del documento para preview.
    Detecta si tiene imagenes, tablas, etc.

    Espera JSON:
    - file_id: ID del archivo

    Retorna:
    - Info del documento (num_paginas, tiene_imagenes, tiene_tablas, etc.)
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    try:
        from services.pdf_to_docx import obtener_preview_docx
        info = obtener_preview_docx(archivo_id)

        return respuesta_exitosa(info, 'Informacion del documento obtenida')

    except Exception as e:
        logger.error(f"Error obteniendo info docx: {e}")
        return respuesta_error('PREVIEW_ERROR', str(e), 500)


@bp.route('/to-png', methods=['POST'])
def convertir_to_png():
    """
    Convierte PDF a imagenes PNG.

    Espera JSON:
    - file_id: ID del archivo
    - opciones:
        - dpi: 72 | 150 | 300 | 600
        - paginas: 'all' | '1-10' | '1,3,5-10'

    Retorna:
    - Info del trabajo creado
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')
    opciones = datos.get('opciones', {})

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    # Crear trabajo
    try:
        trabajo_id = job_manager.encolar_trabajo(
            archivo_id=archivo_id,
            tipo_conversion='to-png',
            parametros=opciones
        )

        trabajo = models.obtener_trabajo(trabajo_id)

        return respuesta_exitosa({
            'job_id': trabajo_id,
            'estado': trabajo['estado'],
            'mensaje': 'Conversion a PNG iniciada'
        }, 'Trabajo encolado correctamente')

    except Exception as e:
        logger.error(f"Error creando trabajo to-png: {e}")
        return respuesta_error('JOB_ERROR', str(e), 500)


@bp.route('/to-png/info', methods=['POST'])
def info_to_png():
    """
    Obtiene informacion para estimar el resultado de la conversion.

    Espera JSON:
    - file_id: ID del archivo
    - opciones: Opciones de conversion

    Retorna:
    - Info del documento y estimacion de tamano
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')
    opciones = datos.get('opciones', {})

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    try:
        from services.pdf_to_images import obtener_info_conversion
        info = obtener_info_conversion(archivo_id, opciones)

        return respuesta_exitosa(info, 'Informacion obtenida')

    except Exception as e:
        logger.error(f"Error obteniendo info png: {e}")
        return respuesta_error('INFO_ERROR', str(e), 500)


@bp.route('/to-jpg', methods=['POST'])
def convertir_to_jpg():
    """
    Convierte PDF a imagenes JPG.

    Espera JSON:
    - file_id: ID del archivo
    - opciones:
        - dpi: 72 | 150 | 300 | 600
        - calidad: 60-95 (porcentaje de calidad JPG)
        - paginas: 'all' | '1-10' | '1,3,5-10'

    Retorna:
    - Info del trabajo creado
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')
    opciones = datos.get('opciones', {})

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    # Crear trabajo
    try:
        trabajo_id = job_manager.encolar_trabajo(
            archivo_id=archivo_id,
            tipo_conversion='to-jpg',
            parametros=opciones
        )

        trabajo = models.obtener_trabajo(trabajo_id)

        return respuesta_exitosa({
            'job_id': trabajo_id,
            'estado': trabajo['estado'],
            'mensaje': 'Conversion a JPG iniciada'
        }, 'Trabajo encolado correctamente')

    except Exception as e:
        logger.error(f"Error creando trabajo to-jpg: {e}")
        return respuesta_error('JOB_ERROR', str(e), 500)


@bp.route('/compress', methods=['POST'])
def convertir_compress():
    """
    Comprime un PDF reduciendo tamano de imagenes y optimizando estructura.

    Espera JSON:
    - file_id: ID del archivo
    - opciones:
        - nivel: 'baja' | 'media' | 'alta' | 'personalizada'
        - dpi_maximo: DPI maximo para imagenes (solo si nivel='personalizada')
        - calidad_jpg: Calidad de compresion (solo si nivel='personalizada')
        - eliminar_metadatos: bool
        - eliminar_anotaciones: bool
        - eliminar_bookmarks: bool
        - escala_grises: bool

    Retorna:
    - Job ID para monitorear progreso
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')
    opciones = datos.get('opciones', {})

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    try:
        # Crear trabajo de compresion
        trabajo_id = job_manager.crear_trabajo(
            tipo='compress',
            archivo_id=archivo_id,
            parametros=opciones
        )

        return respuesta_exitosa({
            'job_id': trabajo_id,
            'message': 'Compresion iniciada'
        }, 'Trabajo creado')

    except Exception as e:
        logger.error(f"Error creando trabajo compress: {e}")
        return respuesta_error('JOB_ERROR', str(e), 500)


@bp.route('/compress/info', methods=['GET'])
def obtener_info_compresion():
    """
    Obtiene informacion del archivo para estimar compresion.

    Parametros GET:
    - file_id: ID del archivo

    Retorna:
    - Tamano actual, numero de imagenes, estimaciones de reduccion
    """
    archivo_id = request.args.get('file_id')

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    try:
        from services.pdf_compress import obtener_info_compresion as get_info
        info = get_info(archivo_id)

        return respuesta_exitosa(info, 'Informacion obtenida')

    except Exception as e:
        logger.error(f"Error obteniendo info de compresion: {e}")
        return respuesta_error('INFO_ERROR', str(e), 500)


@bp.route('/extract-images', methods=['POST'])
def convertir_extract_images():
    """
    Extrae imagenes incrustadas de un PDF.

    Espera JSON:
    - file_id: ID del archivo
    - opciones:
        - formato_salida: 'original' | 'png' | 'jpg'
        - tamano_minimo_px: int (minimo en pixeles, default 50)

    Retorna:
    - Info del trabajo creado
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')
    opciones = datos.get('opciones', {})

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    # Crear trabajo
    try:
        trabajo_id = job_manager.encolar_trabajo(
            archivo_id=archivo_id,
            tipo_conversion='extract-images',
            parametros=opciones
        )

        trabajo = models.obtener_trabajo(trabajo_id)

        return respuesta_exitosa({
            'job_id': trabajo_id,
            'estado': trabajo['estado'],
            'mensaje': 'Extraccion de imagenes iniciada'
        }, 'Trabajo encolado correctamente')

    except Exception as e:
        logger.error(f"Error creando trabajo extract-images: {e}")
        return respuesta_error('JOB_ERROR', str(e), 500)


@bp.route('/extract-images/count', methods=['POST'])
def contar_imagenes():
    """
    Cuenta las imagenes en un PDF.

    Espera JSON:
    - file_id: ID del archivo

    Retorna:
    - Numero de imagenes encontradas
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    try:
        from services.pdf_extract_images import obtener_conteo_imagenes
        info = obtener_conteo_imagenes(archivo_id)

        return respuesta_exitosa(info, 'Conteo obtenido')

    except Exception as e:
        logger.error(f"Error contando imagenes: {e}")
        return respuesta_error('COUNT_ERROR', str(e), 500)


@bp.route('/rotate', methods=['POST'])
def convertir_rotate():
    """
    Rota paginas de un PDF.
    (Placeholder para Etapa 9)
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    # TODO: Implementar en Etapa 9
    return respuesta_error('NOT_IMPLEMENTED', 'Servicio en desarrollo', 501)


@bp.route('/from-html', methods=['POST'])
def convertir_from_html():
    """
    Convierte HTML/URL a PDF.
    (Placeholder para Etapa 10)
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    url = datos.get('url')

    if not url:
        return respuesta_error('MISSING_URL', 'Se requiere URL')

    # TODO: Implementar en Etapa 10
    return respuesta_error('NOT_IMPLEMENTED', 'Servicio en desarrollo', 501)


@bp.route('/merge', methods=['POST'])
def convertir_merge():
    """
    Une multiples PDFs en uno.
    (Placeholder para Etapa 11)
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivos = datos.get('archivos', [])

    if len(archivos) < 2:
        return respuesta_error('INSUFFICIENT_FILES', 'Se requieren al menos 2 archivos')

    # TODO: Implementar en Etapa 11
    return respuesta_error('NOT_IMPLEMENTED', 'Servicio en desarrollo', 501)


@bp.route('/extract-pages', methods=['POST'])
def convertir_extract_pages():
    """
    Extrae paginas especificas de un PDF.
    (Placeholder para Etapa 12)
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    # TODO: Implementar en Etapa 12
    return respuesta_error('NOT_IMPLEMENTED', 'Servicio en desarrollo', 501)


@bp.route('/reorder', methods=['POST'])
def convertir_reorder():
    """
    Reordena paginas de un PDF.
    (Placeholder para Etapa 13)
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    # TODO: Implementar en Etapa 13
    return respuesta_error('NOT_IMPLEMENTED', 'Servicio en desarrollo', 501)
