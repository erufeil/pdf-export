# -*- coding: utf-8 -*-
"""
Endpoints de la API para gestion de archivos.
Maneja subida, listado, eliminacion y miniaturas.
"""

from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename
import logging
from pathlib import Path
from io import BytesIO

import config
import models
from utils import file_manager

logger = logging.getLogger(__name__)

# Blueprint para rutas de archivos
bp = Blueprint('files', __name__, url_prefix='/api/v1')


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


@bp.route('/upload', methods=['POST'])
def subir_archivo():
    """
    Sube un archivo PDF al servidor.

    Espera:
    - archivo: Archivo PDF (multipart/form-data)
    - nombre: Nombre original del archivo (opcional)
    - fecha_modificacion: Fecha de modificacion ISO (opcional)

    Retorna:
    - Informacion del archivo subido o existente
    """
    # Verificar que hay archivo
    if 'archivo' not in request.files:
        return respuesta_error('NO_FILE', 'No se envio ningun archivo')

    archivo = request.files['archivo']

    if archivo.filename == '':
        return respuesta_error('EMPTY_FILENAME', 'Nombre de archivo vacio')

    # Obtener nombre y fecha del form o del archivo
    nombre_original = request.form.get('nombre', archivo.filename)
    fecha_modificacion = request.form.get('fecha_modificacion')
    tamano_declarado = request.form.get('tamano', type=int)

    # Verificar extension
    if not file_manager.extension_permitida(nombre_original):
        return respuesta_error('INVALID_EXTENSION', 'Solo se permiten archivos PDF')

    # Buscar si ya existe un archivo identico
    if tamano_declarado and fecha_modificacion:
        existente = file_manager.buscar_archivo_duplicado(
            nombre_original, tamano_declarado, fecha_modificacion
        )
        if existente:
            logger.info(f"Archivo duplicado detectado: {nombre_original}")
            return respuesta_exitosa({
                'id': existente['id'],
                'nombre_original': existente['nombre_original'],
                'tamano_bytes': existente['tamano_bytes'],
                'num_paginas': existente['num_paginas'],
                'ya_existia': True
            }, 'Archivo ya existente en el servidor')

    # Guardar archivo
    resultado = file_manager.guardar_archivo(
        archivo, nombre_original, fecha_modificacion
    )

    if not resultado:
        return respuesta_error('SAVE_ERROR', 'Error al guardar el archivo', 500)

    resultado['ya_existia'] = False
    return respuesta_exitosa(resultado, 'Archivo subido correctamente')


@bp.route('/files', methods=['GET'])
def listar_archivos():
    """
    Lista todos los archivos disponibles (dentro del periodo de retencion).

    Retorna:
    - Lista de archivos con su informacion
    """
    archivos = models.listar_archivos()

    # Formatear respuesta
    lista = [{
        'id': a['id'],
        'nombre_original': a['nombre_original'],
        'tamano_bytes': a['tamano_bytes'],
        'num_paginas': a['num_paginas'],
        'fecha_subida': a['fecha_subida']
    } for a in archivos]

    return respuesta_exitosa(lista, f'{len(lista)} archivos disponibles')


@bp.route('/files/<archivo_id>', methods=['GET'])
def obtener_archivo(archivo_id):
    """
    Obtiene informacion de un archivo especifico.

    Retorna:
    - Informacion detallada del archivo
    """
    archivo = models.obtener_archivo(archivo_id)

    if not archivo:
        return respuesta_error('NOT_FOUND', 'Archivo no encontrado', 404)

    return respuesta_exitosa({
        'id': archivo['id'],
        'nombre_original': archivo['nombre_original'],
        'tamano_bytes': archivo['tamano_bytes'],
        'num_paginas': archivo['num_paginas'],
        'fecha_subida': archivo['fecha_subida'],
        'fecha_modificacion': archivo['fecha_modificacion']
    })


@bp.route('/files/<archivo_id>', methods=['DELETE'])
def eliminar_archivo(archivo_id):
    """
    Elimina un archivo del servidor.

    Retorna:
    - Confirmacion de eliminacion
    """
    if file_manager.eliminar_archivo_fisico(archivo_id):
        return respuesta_exitosa(mensaje='Archivo eliminado correctamente')
    else:
        return respuesta_error('NOT_FOUND', 'Archivo no encontrado', 404)


@bp.route('/files', methods=['DELETE'])
def eliminar_todos_archivos():
    """
    Elimina todos los archivos del usuario.

    Retorna:
    - Cantidad de archivos eliminados
    """
    archivos = models.listar_archivos()
    eliminados = 0

    for archivo in archivos:
        if file_manager.eliminar_archivo_fisico(archivo['id']):
            eliminados += 1

    return respuesta_exitosa(
        {'eliminados': eliminados},
        f'{eliminados} archivos eliminados'
    )


@bp.route('/files/<archivo_id>/thumbnail/<int:pagina>', methods=['GET'])
def obtener_miniatura(archivo_id, pagina):
    """
    Genera y retorna una miniatura de una pagina del PDF.

    Args:
    - archivo_id: ID del archivo
    - pagina: Numero de pagina (0-indexed)

    Retorna:
    - Imagen PNG de la miniatura
    """
    archivo = models.obtener_archivo(archivo_id)

    if not archivo:
        return respuesta_error('NOT_FOUND', 'Archivo no encontrado', 404)

    ruta = Path(archivo['ruta_archivo'])

    if not ruta.exists():
        return respuesta_error('FILE_MISSING', 'Archivo fisico no encontrado', 404)

    # Validar numero de pagina
    if pagina < 0 or pagina >= archivo['num_paginas']:
        return respuesta_error('INVALID_PAGE', f'Pagina invalida. El documento tiene {archivo["num_paginas"]} paginas')

    # Generar miniatura
    png_bytes = file_manager.generar_miniatura(ruta, pagina)

    if not png_bytes:
        return respuesta_error('THUMBNAIL_ERROR', 'Error al generar miniatura', 500)

    return send_file(
        BytesIO(png_bytes),
        mimetype='image/png',
        download_name=f'thumbnail_p{pagina}.png'
    )


@bp.route('/check-duplicate', methods=['POST'])
def verificar_duplicado():
    """
    Verifica si un archivo ya existe en el servidor sin subirlo.
    Usado para evitar subidas innecesarias.

    Espera JSON:
    - nombre: Nombre del archivo
    - tamano: Tamanio en bytes
    - fecha_modificacion: Fecha de modificacion ISO

    Retorna:
    - exists: true/false
    - file: Informacion del archivo si existe
    """
    datos = request.get_json()

    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    nombre = datos.get('nombre')
    tamano = datos.get('tamano')
    fecha_mod = datos.get('fecha_modificacion')

    if not all([nombre, tamano, fecha_mod]):
        return respuesta_error('MISSING_PARAMS', 'Faltan parametros requeridos')

    existente = file_manager.buscar_archivo_duplicado(nombre, tamano, fecha_mod)

    if existente:
        return respuesta_exitosa({
            'exists': True,
            'file': {
                'id': existente['id'],
                'nombre_original': existente['nombre_original'],
                'tamano_bytes': existente['tamano_bytes'],
                'num_paginas': existente['num_paginas']
            }
        }, 'Archivo encontrado en el servidor')
    else:
        return respuesta_exitosa({'exists': False}, 'Archivo no encontrado')
