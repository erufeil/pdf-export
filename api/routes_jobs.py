# -*- coding: utf-8 -*-
"""
Endpoints de la API para gestion de trabajos.
Maneja creacion, listado, estado y descarga de resultados.
"""

from flask import Blueprint, request, jsonify, send_file, Response
import logging
from pathlib import Path
import json
import time

import config
import models
from utils import job_manager

logger = logging.getLogger(__name__)

# Blueprint para rutas de trabajos
bp = Blueprint('jobs', __name__, url_prefix='/api/v1')


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


@bp.route('/jobs', methods=['GET'])
def listar_trabajos():
    """
    Lista todos los trabajos del usuario.

    Query params:
    - estado: Filtrar por estado (pendiente, procesando, completado, error, cancelado)

    Retorna:
    - Lista de trabajos con su informacion
    """
    estado = request.args.get('estado')

    if estado:
        trabajos = models.listar_trabajos(estado=estado)
    else:
        trabajos = models.listar_trabajos()

    # Formatear respuesta
    lista = [{
        'id': t['id'],
        'archivo_id': t['archivo_id'],
        'nombre_archivo': t['nombre_archivo'],
        'tipo_conversion': t['tipo_conversion'],
        'estado': t['estado'],
        'progreso': t['progreso'],
        'mensaje': t['mensaje'],
        'fecha_creacion': t['fecha_creacion'],
        'fecha_fin': t['fecha_fin']
    } for t in trabajos]

    return respuesta_exitosa(lista, f'{len(lista)} trabajos encontrados')


@bp.route('/jobs/<trabajo_id>', methods=['GET'])
def obtener_trabajo(trabajo_id):
    """
    Obtiene informacion detallada de un trabajo.

    Retorna:
    - Informacion completa del trabajo
    """
    trabajo = models.obtener_trabajo(trabajo_id)

    if not trabajo:
        return respuesta_error('NOT_FOUND', 'Trabajo no encontrado', 404)

    return respuesta_exitosa({
        'id': trabajo['id'],
        'archivo_id': trabajo['archivo_id'],
        'nombre_archivo': trabajo['nombre_archivo'],
        'tipo_conversion': trabajo['tipo_conversion'],
        'estado': trabajo['estado'],
        'progreso': trabajo['progreso'],
        'mensaje': trabajo['mensaje'],
        'fecha_creacion': trabajo['fecha_creacion'],
        'fecha_inicio': trabajo['fecha_inicio'],
        'fecha_fin': trabajo['fecha_fin'],
        'tiene_resultado': trabajo['ruta_resultado'] is not None
    })


@bp.route('/jobs/<trabajo_id>/progress', methods=['GET'])
def obtener_progreso_sse(trabajo_id):
    """
    Endpoint de Server-Sent Events para progreso en tiempo real.
    El cliente se conecta y recibe actualizaciones de progreso.

    Retorna:
    - Stream de eventos SSE con progreso del trabajo
    """
    def generar_eventos():
        ultimo_progreso = -1
        ultimo_estado = None

        while True:
            trabajo = models.obtener_trabajo(trabajo_id)

            if not trabajo:
                yield f"data: {json.dumps({'error': 'Trabajo no encontrado'})}\n\n"
                break

            # Solo enviar si hay cambios
            if trabajo['progreso'] != ultimo_progreso or trabajo['estado'] != ultimo_estado:
                ultimo_progreso = trabajo['progreso']
                ultimo_estado = trabajo['estado']

                evento = {
                    'estado': trabajo['estado'],
                    'progreso': trabajo['progreso'],
                    'mensaje': trabajo['mensaje']
                }

                yield f"data: {json.dumps(evento)}\n\n"

            # Si el trabajo termino, cerrar conexion
            if trabajo['estado'] in ('completado', 'error', 'cancelado'):
                break

            time.sleep(config.JOB_CHECK_INTERVAL)

    return Response(
        generar_eventos(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@bp.route('/jobs/<trabajo_id>', methods=['DELETE'])
def eliminar_trabajo(trabajo_id):
    """
    Elimina un trabajo (cancela si esta en proceso, o elimina si ya termino).
    Tambien elimina el archivo de resultado si existe.

    Retorna:
    - Confirmacion de eliminacion
    """
    trabajo = models.obtener_trabajo(trabajo_id)

    if not trabajo:
        return respuesta_error('NOT_FOUND', 'Trabajo no encontrado', 404)

    # Si tiene archivo de resultado, eliminarlo
    if trabajo['ruta_resultado']:
        ruta = Path(trabajo['ruta_resultado'])
        if ruta.exists():
            try:
                ruta.unlink()
                logger.info(f"Archivo de resultado eliminado: {ruta}")
            except Exception as e:
                logger.error(f"Error eliminando archivo de resultado: {e}")

    # Si esta pendiente o procesando, cancelar
    if trabajo['estado'] in ('pendiente', 'procesando'):
        models.cancelar_trabajo(trabajo_id)
        return respuesta_exitosa(mensaje='Trabajo cancelado')

    # Si ya termino (completado, error, cancelado), eliminar registro
    from utils import file_manager
    with models.obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM trabajos WHERE id = ?', (trabajo_id,))

    return respuesta_exitosa(mensaje='Trabajo eliminado')


@bp.route('/download/<trabajo_id>', methods=['GET'])
def descargar_resultado(trabajo_id):
    """
    Descarga el archivo resultante de un trabajo completado.

    Retorna:
    - Archivo ZIP con el resultado
    """
    trabajo = models.obtener_trabajo(trabajo_id)

    if not trabajo:
        return respuesta_error('NOT_FOUND', 'Trabajo no encontrado', 404)

    if trabajo['estado'] != 'completado':
        return respuesta_error(
            'NOT_READY',
            f'El trabajo no esta completado. Estado: {trabajo["estado"]}'
        )

    if not trabajo['ruta_resultado']:
        return respuesta_error('NO_RESULT', 'El trabajo no tiene archivo de resultado')

    ruta = Path(trabajo['ruta_resultado'])

    if not ruta.exists():
        return respuesta_error('FILE_MISSING', 'El archivo de resultado no existe', 404)

    # Detectar tipo de archivo y generar nombre descriptivo
    extension_real = ruta.suffix.lower()

    # Mimetypes segun extension
    mimetypes_map = {
        '.zip': 'application/zip',
        '.pdf': 'application/pdf',
        '.txt': 'text/plain',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
    }
    mimetype = mimetypes_map.get(extension_real, 'application/octet-stream')

    # Nombre de descarga con extension correcta
    nombre_base = trabajo['nombre_archivo'] or 'resultado'
    nombre_descarga = f"{trabajo['tipo_conversion']}_{nombre_base}{extension_real}"

    return send_file(
        str(ruta),
        mimetype=mimetype,
        as_attachment=True,
        download_name=nombre_descarga
    )


@bp.route('/downloads', methods=['GET'])
def listar_descargas():
    """
    Lista trabajos completados con descarga disponible.

    Retorna:
    - Lista de trabajos con resultado descargable
    """
    trabajos = models.listar_trabajos(estado='completado')

    # Filtrar solo los que tienen resultado
    disponibles = []
    for t in trabajos:
        if t['ruta_resultado']:
            ruta = Path(t['ruta_resultado'])
            if ruta.exists():
                disponibles.append({
                    'id': t['id'],
                    'nombre_archivo': t['nombre_archivo'],
                    'tipo_conversion': t['tipo_conversion'],
                    'fecha_fin': t['fecha_fin'],
                    'tamano_resultado': ruta.stat().st_size
                })

    return respuesta_exitosa(disponibles, f'{len(disponibles)} descargas disponibles')


@bp.route('/status', methods=['GET'])
def estado_servicio():
    """
    Retorna el estado general del servicio.

    Retorna:
    - Estadisticas de archivos, trabajos y cola
    """
    estado_cola = job_manager.obtener_estado_cola()
    archivos = models.listar_archivos()

    return respuesta_exitosa({
        'archivos_disponibles': len(archivos),
        'cola': estado_cola,
        'retencion_horas': config.FILE_RETENTION_HOURS,
        'tamano_maximo_mb': config.MAX_CONTENT_LENGTH / (1024 * 1024)
    }, 'Servicio operativo')
