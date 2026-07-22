# -*- coding: utf-8 -*-
"""
Endpoints de la API para gestion de archivos.
Maneja subida, listado, eliminacion y miniaturas.
"""

import re
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
        extensiones = ', '.join(config.ALLOWED_EXTENSIONS)
        return respuesta_error('INVALID_EXTENSION', f'Extensiones permitidas: {extensiones}')

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


_REGEX_SLUG = re.compile(r'^[a-z0-9_-]{3,50}$')


def _ip_cliente() -> str:
    """Extrae la IP real del cliente respetando X-Forwarded-For de Nginx."""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or '0.0.0.0'


@bp.route('/notepad/<slug>', methods=['GET'])
def obtener_notepad(slug):
    """Obtiene (o crea) un notepad compartido por slug. Registra presencia."""
    if not _REGEX_SLUG.match(slug):
        return respuesta_error('SLUG_INVALIDO', 'El slug solo puede tener letras minúsculas, números, guión y guión bajo (3–50 caracteres)')
    ip = _ip_cliente()
    notepad = models.obtener_o_crear_notepad(slug, ip)
    return respuesta_exitosa({
        'slug': notepad['slug'],
        'contenido': notepad['contenido'],
        'version': notepad['version'],
        'crc32': notepad['crc32'],
        'fecha_modificacion': notepad['fecha_modificacion'],
        'visitantes': notepad['visitantes'],
    })


@bp.route('/notepad/<slug>', methods=['PUT'])
def guardar_notepad(slug):
    """Guarda el contenido del notepad (last-write-wins). Registra presencia."""
    if not _REGEX_SLUG.match(slug):
        return respuesta_error('SLUG_INVALIDO', 'Slug inválido')
    datos = request.get_json(silent=True) or {}
    contenido = datos.get('contenido', '')
    if not isinstance(contenido, str):
        return respuesta_error('CONTENIDO_INVALIDO', 'El contenido debe ser texto')
    ip = _ip_cliente()
    resultado = models.guardar_notepad(slug, contenido, ip)
    return respuesta_exitosa({
        'ok': True,
        'version': resultado['version'],
        'crc32': resultado['crc32'],
        'fecha_modificacion': resultado['fecha_modificacion'],
        'visitantes': resultado['visitantes'],
    })


@bp.route('/notepad/<slug>/lines', methods=['PUT'])
def guardar_lineas_notepad(slug):
    """Aplica deltas de líneas (last-write-wins por línea). Retorna version y crc32."""
    if not _REGEX_SLUG.match(slug):
        return respuesta_error('SLUG_INVALIDO', 'Slug inválido')
    datos = request.get_json(silent=True) or {}
    deltas = datos.get('deltas', [])
    if not isinstance(deltas, list):
        return respuesta_error('DELTAS_INVALIDOS', 'deltas debe ser una lista')
    ip = _ip_cliente()
    resultado = models.aplicar_deltas_notepad(slug, deltas, ip)
    if resultado is None:
        return respuesta_error('NOT_FOUND', 'Notepad no encontrado', 404)
    return respuesta_exitosa({
        'version': resultado['version'],
        'crc32': resultado['crc32'],
        'visitantes': resultado['visitantes'],
    })


@bp.route('/notepad/<slug>', methods=['DELETE'])
def eliminar_notepad(slug):
    """Elimina el notepad permanentemente."""
    if not _REGEX_SLUG.match(slug):
        return respuesta_error('SLUG_INVALIDO', 'Slug inválido')
    eliminado = models.eliminar_notepad(slug)
    if not eliminado:
        return respuesta_error('NOT_FOUND', 'Notepad no encontrado', 404)
    return respuesta_exitosa({'ok': True}, 'Notepad eliminado')


@bp.route('/api-ref', methods=['GET'])
def obtener_api_ref():
    """Retorna el contenido de README-API-Ref.md como texto plano para la página de referencia API."""
    ruta_md = Path(__file__).parent.parent / 'README-API-Ref.md'
    try:
        contenido = ruta_md.read_text(encoding='utf-8')
        return respuesta_exitosa({'contenido': contenido}, 'API Reference cargado')
    except FileNotFoundError:
        return respuesta_exitosa({'contenido': '# API Reference\n\nDocumentación no disponible.'}, 'Sin documentación')


@bp.route('/token-count', methods=['POST'])
def contar_tokens_endpoint():
    """
    Cuenta tokens (cl100k_base), palabras, caracteres y bytes de un texto.
    Síncrono — retorna inmediatamente sin crear un job.
    Body JSON: { "texto": "..." }
    """
    from services.token_counter import contar_tokens

    datos = request.get_json(silent=True) or {}
    texto = datos.get('texto', '')

    if not isinstance(texto, str):
        return respuesta_error('TEXTO_INVALIDO', 'El campo texto debe ser un string')

    try:
        resultado = contar_tokens(texto)
    except RuntimeError as e:
        return respuesta_error('TIKTOKEN_ERROR', str(e), 503)

    return respuesta_exitosa(resultado, 'Conteo completado')


@bp.route('/help', methods=['GET'])
def obtener_ayuda():
    """
    Retorna el contenido del archivo NOTAS-USUARIO.md como texto plano.
    Usado por la página de ayuda para renderizar la documentación.
    """
    ruta_md = Path(__file__).parent.parent / 'NOTAS-USUARIO.md'
    try:
        contenido = ruta_md.read_text(encoding='utf-8')
        return respuesta_exitosa({'contenido': contenido}, 'Ayuda cargada')
    except FileNotFoundError:
        return respuesta_exitosa({'contenido': '# Ayuda\n\nDocumentación no disponible.'}, 'Sin documentación')
