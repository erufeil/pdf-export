# -*- coding: utf-8 -*-
"""
Gestor de trabajos de conversion para PDFexport.
Maneja la cola de trabajos y ejecucion en segundo plano.
"""

import threading
import queue
import json
import logging
from datetime import datetime
from typing import Callable, Dict, Any

import models
import config

logger = logging.getLogger(__name__)

# Cola global de trabajos
cola_trabajos = queue.Queue()

# Diccionario de procesadores por tipo de conversion
procesadores: Dict[str, Callable] = {}

# Flag para detener el worker
detener_worker = threading.Event()


def registrar_procesador(tipo: str, funcion: Callable):
    """
    Registra una funcion procesadora para un tipo de conversion.

    Args:
        tipo: Tipo de conversion (ej: 'to-txt', 'to-png')
        funcion: Funcion que procesa el trabajo
    """
    procesadores[tipo] = funcion
    logger.info(f"Procesador registrado: {tipo}")


def encolar_trabajo(archivo_id: str, tipo_conversion: str, parametros: dict = None) -> str:
    """
    Crea un trabajo y lo agrega a la cola de procesamiento.

    Args:
        archivo_id: ID del archivo a procesar
        tipo_conversion: Tipo de conversion a realizar
        parametros: Parametros adicionales para la conversion

    Returns:
        ID del trabajo creado
    """
    # Serializar parametros
    parametros_json = json.dumps(parametros) if parametros else None

    # Crear registro en BD
    trabajo_id = models.crear_trabajo(
        archivo_id=archivo_id,
        tipo_conversion=tipo_conversion,
        parametros=parametros_json
    )

    # Agregar a la cola
    cola_trabajos.put(trabajo_id)
    logger.info(f"Trabajo encolado: {trabajo_id} ({tipo_conversion})")

    return trabajo_id


def procesar_trabajo(trabajo_id: str):
    """
    Procesa un trabajo individual.

    Args:
        trabajo_id: ID del trabajo a procesar
    """
    trabajo = models.obtener_trabajo(trabajo_id)

    if not trabajo:
        logger.error(f"Trabajo no encontrado: {trabajo_id}")
        return

    if trabajo['estado'] == 'cancelado':
        logger.info(f"Trabajo cancelado, omitiendo: {trabajo_id}")
        return

    tipo = trabajo['tipo_conversion']

    if tipo not in procesadores:
        models.actualizar_trabajo(
            trabajo_id,
            estado='error',
            mensaje=f"Tipo de conversion no soportado: {tipo}"
        )
        logger.error(f"Procesador no encontrado: {tipo}")
        return

    # Marcar como procesando
    models.actualizar_trabajo(trabajo_id, estado='procesando', progreso=0)
    logger.info(f"Iniciando trabajo: {trabajo_id} ({tipo})")

    try:
        # Parsear parametros
        parametros = json.loads(trabajo['parametros']) if trabajo['parametros'] else {}

        # Ejecutar procesador
        procesador = procesadores[tipo]
        resultado = procesador(
            trabajo_id=trabajo_id,
            archivo_id=trabajo['archivo_id'],
            parametros=parametros
        )

        # Marcar como completado
        models.actualizar_trabajo(
            trabajo_id,
            estado='completado',
            progreso=100,
            ruta_resultado=resultado.get('ruta_resultado'),
            mensaje=resultado.get('mensaje', 'Conversion completada')
        )
        logger.info(f"Trabajo completado: {trabajo_id}")

    except Exception as e:
        # Marcar como error
        models.actualizar_trabajo(
            trabajo_id,
            estado='error',
            mensaje=str(e)
        )
        logger.error(f"Error en trabajo {trabajo_id}: {e}")


def actualizar_progreso(trabajo_id: str, progreso: int, mensaje: str = None):
    """
    Actualiza el progreso de un trabajo en ejecucion.
    Llamado por los procesadores durante la conversion.

    Args:
        trabajo_id: ID del trabajo
        progreso: Porcentaje de progreso (0-100)
        mensaje: Mensaje de estado opcional
    """
    models.actualizar_trabajo(trabajo_id, progreso=progreso, mensaje=mensaje)


def worker_procesador():
    """
    Worker que procesa trabajos de la cola en segundo plano.
    Se ejecuta en un thread separado.
    """
    logger.info("Worker de trabajos iniciado")

    while not detener_worker.is_set():
        try:
            # Esperar trabajo con timeout para poder verificar flag de detencion
            trabajo_id = cola_trabajos.get(timeout=1)
            procesar_trabajo(trabajo_id)
            cola_trabajos.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"Error en worker: {e}")

    logger.info("Worker de trabajos detenido")


def iniciar_worker():
    """Inicia el thread worker para procesar trabajos."""
    detener_worker.clear()
    thread = threading.Thread(target=worker_procesador, daemon=True)
    thread.start()
    logger.info("Thread worker iniciado")
    return thread


def detener_worker_graceful():
    """Detiene el worker de forma graceful."""
    detener_worker.set()
    logger.info("Senial de detencion enviada al worker")


def obtener_estado_cola() -> dict:
    """
    Obtiene el estado actual de la cola de trabajos.

    Returns:
        dict con estadisticas de la cola
    """
    pendientes = models.listar_trabajos(estado='pendiente')
    procesando = models.listar_trabajos(estado='procesando')
    completados = models.listar_trabajos(estado='completado')
    errores = models.listar_trabajos(estado='error')

    return {
        'en_cola': cola_trabajos.qsize(),
        'pendientes': len(pendientes),
        'procesando': len(procesando),
        'completados': len(completados),
        'errores': len(errores),
        'procesadores_registrados': list(procesadores.keys())
    }


def reencolar_trabajos_pendientes():
    """
    Reencola trabajos que quedaron pendientes o procesando
    (por ejemplo, despues de un reinicio del servidor).
    """
    pendientes = models.listar_trabajos(estado='pendiente')
    procesando = models.listar_trabajos(estado='procesando')

    # Los que estaban procesando los marcamos como pendientes
    for trabajo in procesando:
        models.actualizar_trabajo(trabajo['id'], estado='pendiente', progreso=0)

    # Encolar todos los pendientes
    for trabajo in pendientes + procesando:
        cola_trabajos.put(trabajo['id'])

    total = len(pendientes) + len(procesando)
    if total > 0:
        logger.info(f"Reencolados {total} trabajos pendientes")

    return total
