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
    (Placeholder para Etapa 3)
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')
    opciones = datos.get('opciones', {})

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    # TODO: Implementar en Etapa 3
    return respuesta_error('NOT_IMPLEMENTED', 'Servicio en desarrollo', 501)


@bp.route('/to-docx', methods=['POST'])
def convertir_to_docx():
    """
    Convierte PDF a DOCX.
    (Placeholder para Etapa 4)
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    # TODO: Implementar en Etapa 4
    return respuesta_error('NOT_IMPLEMENTED', 'Servicio en desarrollo', 501)


@bp.route('/to-png', methods=['POST'])
def convertir_to_png():
    """
    Convierte PDF a imagenes PNG.
    (Placeholder para Etapa 5)
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    # TODO: Implementar en Etapa 5
    return respuesta_error('NOT_IMPLEMENTED', 'Servicio en desarrollo', 501)


@bp.route('/to-jpg', methods=['POST'])
def convertir_to_jpg():
    """
    Convierte PDF a imagenes JPG.
    (Placeholder para Etapa 6)
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    # TODO: Implementar en Etapa 6
    return respuesta_error('NOT_IMPLEMENTED', 'Servicio en desarrollo', 501)


@bp.route('/compress', methods=['POST'])
def convertir_compress():
    """
    Comprime un PDF.
    (Placeholder para Etapa 7)
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    # TODO: Implementar en Etapa 7
    return respuesta_error('NOT_IMPLEMENTED', 'Servicio en desarrollo', 501)


@bp.route('/extract-images', methods=['POST'])
def convertir_extract_images():
    """
    Extrae imagenes de un PDF.
    (Placeholder para Etapa 8)
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')

    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    # TODO: Implementar en Etapa 8
    return respuesta_error('NOT_IMPLEMENTED', 'Servicio en desarrollo', 501)


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
