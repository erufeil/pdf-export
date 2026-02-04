# -*- coding: utf-8 -*-
"""
Modelos de base de datos SQLite para PDFexport.
Gestiona archivos subidos y trabajos de conversion.
"""

import sqlite3
import uuid
from datetime import datetime, timedelta
from contextlib import contextmanager
import logging

import config

logger = logging.getLogger(__name__)


@contextmanager
def obtener_conexion():
    """Context manager para conexiones a la base de datos."""
    conexion = sqlite3.connect(str(config.DATABASE_PATH))
    conexion.row_factory = sqlite3.Row
    try:
        yield conexion
        conexion.commit()
    except Exception as e:
        conexion.rollback()
        logger.error(f"Error en base de datos: {e}")
        raise
    finally:
        conexion.close()


def inicializar_db():
    """Crea las tablas si no existen."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()

        # Tabla de archivos subidos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS archivos (
                id TEXT PRIMARY KEY,
                nombre_original TEXT NOT NULL,
                nombre_guardado TEXT NOT NULL,
                tamano_bytes INTEGER NOT NULL,
                fecha_modificacion TEXT,
                num_paginas INTEGER DEFAULT 0,
                hash_archivo TEXT,
                fecha_subida TEXT NOT NULL,
                ruta_archivo TEXT NOT NULL
            )
        ''')

        # Tabla de trabajos de conversion
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trabajos (
                id TEXT PRIMARY KEY,
                archivo_id TEXT,
                tipo_conversion TEXT NOT NULL,
                estado TEXT DEFAULT 'pendiente',
                progreso INTEGER DEFAULT 0,
                mensaje TEXT,
                parametros TEXT,
                ruta_resultado TEXT,
                fecha_creacion TEXT NOT NULL,
                fecha_inicio TEXT,
                fecha_fin TEXT,
                FOREIGN KEY (archivo_id) REFERENCES archivos(id)
            )
        ''')

        # Indices para mejorar rendimiento
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_archivos_hash ON archivos(hash_archivo)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_archivos_fecha ON archivos(fecha_subida)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trabajos_estado ON trabajos(estado)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trabajos_fecha ON trabajos(fecha_creacion)')

        logger.info("Base de datos inicializada correctamente")


# =============================================================================
# Funciones para ARCHIVOS
# =============================================================================

def crear_archivo(nombre_original: str, nombre_guardado: str, tamano_bytes: int,
                  fecha_modificacion: str, ruta_archivo: str, hash_archivo: str = None,
                  num_paginas: int = 0) -> str:
    """
    Registra un nuevo archivo en la base de datos.
    Retorna el ID del archivo creado.
    """
    archivo_id = str(uuid.uuid4())
    fecha_subida = datetime.now().isoformat()

    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO archivos
            (id, nombre_original, nombre_guardado, tamano_bytes, fecha_modificacion,
             num_paginas, hash_archivo, fecha_subida, ruta_archivo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (archivo_id, nombre_original, nombre_guardado, tamano_bytes,
              fecha_modificacion, num_paginas, hash_archivo, fecha_subida, ruta_archivo))

    logger.info(f"Archivo registrado: {nombre_original} -> {archivo_id}")
    return archivo_id


def obtener_archivo(archivo_id: str) -> dict:
    """Obtiene informacion de un archivo por su ID."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM archivos WHERE id = ?', (archivo_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def buscar_archivo_existente(nombre: str, tamano: int, fecha_mod: str) -> dict:
    """
    Busca si ya existe un archivo con el mismo nombre, tamanio y fecha.
    Usado para evitar subidas duplicadas.
    """
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM archivos
            WHERE nombre_original = ? AND tamano_bytes = ? AND fecha_modificacion = ?
            AND fecha_subida > ?
        ''', (nombre, tamano, fecha_mod,
              (datetime.now() - timedelta(hours=config.FILE_RETENTION_HOURS)).isoformat()))
        row = cursor.fetchone()
        return dict(row) if row else None


def listar_archivos() -> list:
    """Lista todos los archivos disponibles (dentro del periodo de retencion)."""
    fecha_limite = (datetime.now() - timedelta(hours=config.FILE_RETENTION_HOURS)).isoformat()

    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM archivos
            WHERE fecha_subida > ?
            ORDER BY fecha_subida DESC
        ''', (fecha_limite,))
        return [dict(row) for row in cursor.fetchall()]


def eliminar_archivo(archivo_id: str) -> bool:
    """Elimina un archivo de la base de datos."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM archivos WHERE id = ?', (archivo_id,))
        eliminado = cursor.rowcount > 0

    if eliminado:
        logger.info(f"Archivo eliminado de BD: {archivo_id}")
    return eliminado


def eliminar_archivos_expirados() -> int:
    """
    Elimina registros de archivos mas antiguos que FILE_RETENTION_HOURS.
    Retorna la cantidad de registros eliminados.
    """
    fecha_limite = (datetime.now() - timedelta(hours=config.FILE_RETENTION_HOURS)).isoformat()

    with obtener_conexion() as conn:
        cursor = conn.cursor()

        # Primero obtenemos los IDs para logging
        cursor.execute('SELECT id FROM archivos WHERE fecha_subida < ?', (fecha_limite,))
        ids_expirados = [row['id'] for row in cursor.fetchall()]

        # Eliminamos los registros
        cursor.execute('DELETE FROM archivos WHERE fecha_subida < ?', (fecha_limite,))
        cantidad = cursor.rowcount

    if cantidad > 0:
        logger.info(f"Eliminados {cantidad} archivos expirados de BD")

    return cantidad


# =============================================================================
# Funciones para TRABAJOS
# =============================================================================

def crear_trabajo(archivo_id: str, tipo_conversion: str, parametros: str = None) -> str:
    """
    Crea un nuevo trabajo de conversion.
    Retorna el ID del trabajo.
    """
    trabajo_id = str(uuid.uuid4())
    fecha_creacion = datetime.now().isoformat()

    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trabajos
            (id, archivo_id, tipo_conversion, estado, progreso, parametros, fecha_creacion)
            VALUES (?, ?, ?, 'pendiente', 0, ?, ?)
        ''', (trabajo_id, archivo_id, tipo_conversion, parametros, fecha_creacion))

    logger.info(f"Trabajo creado: {tipo_conversion} -> {trabajo_id}")
    return trabajo_id


def obtener_trabajo(trabajo_id: str) -> dict:
    """Obtiene informacion de un trabajo por su ID."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.*, a.nombre_original as nombre_archivo
            FROM trabajos t
            LEFT JOIN archivos a ON t.archivo_id = a.id
            WHERE t.id = ?
        ''', (trabajo_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def actualizar_trabajo(trabajo_id: str, estado: str = None, progreso: int = None,
                       mensaje: str = None, ruta_resultado: str = None) -> bool:
    """Actualiza el estado de un trabajo."""
    campos = []
    valores = []

    if estado is not None:
        campos.append('estado = ?')
        valores.append(estado)
        if estado == 'procesando' and progreso is None:
            campos.append('fecha_inicio = ?')
            valores.append(datetime.now().isoformat())
        elif estado in ('completado', 'error'):
            campos.append('fecha_fin = ?')
            valores.append(datetime.now().isoformat())

    if progreso is not None:
        campos.append('progreso = ?')
        valores.append(progreso)

    if mensaje is not None:
        campos.append('mensaje = ?')
        valores.append(mensaje)

    if ruta_resultado is not None:
        campos.append('ruta_resultado = ?')
        valores.append(ruta_resultado)

    if not campos:
        return False

    valores.append(trabajo_id)

    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute(f'''
            UPDATE trabajos SET {', '.join(campos)} WHERE id = ?
        ''', valores)
        return cursor.rowcount > 0


def listar_trabajos(estado: str = None) -> list:
    """Lista trabajos, opcionalmente filtrados por estado."""
    fecha_limite = (datetime.now() - timedelta(hours=config.FILE_RETENTION_HOURS)).isoformat()

    with obtener_conexion() as conn:
        cursor = conn.cursor()

        if estado:
            cursor.execute('''
                SELECT t.*, a.nombre_original as nombre_archivo
                FROM trabajos t
                LEFT JOIN archivos a ON t.archivo_id = a.id
                WHERE t.estado = ? AND t.fecha_creacion > ?
                ORDER BY t.fecha_creacion DESC
            ''', (estado, fecha_limite))
        else:
            cursor.execute('''
                SELECT t.*, a.nombre_original as nombre_archivo
                FROM trabajos t
                LEFT JOIN archivos a ON t.archivo_id = a.id
                WHERE t.fecha_creacion > ?
                ORDER BY t.fecha_creacion DESC
            ''', (fecha_limite,))

        return [dict(row) for row in cursor.fetchall()]


def cancelar_trabajo(trabajo_id: str) -> bool:
    """Cancela un trabajo pendiente o en proceso."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE trabajos
            SET estado = 'cancelado', fecha_fin = ?
            WHERE id = ? AND estado IN ('pendiente', 'procesando')
        ''', (datetime.now().isoformat(), trabajo_id))
        return cursor.rowcount > 0


def eliminar_trabajos_expirados() -> int:
    """Elimina trabajos mas antiguos que FILE_RETENTION_HOURS."""
    fecha_limite = (datetime.now() - timedelta(hours=config.FILE_RETENTION_HOURS)).isoformat()

    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM trabajos WHERE fecha_creacion < ?', (fecha_limite,))
        cantidad = cursor.rowcount

    if cantidad > 0:
        logger.info(f"Eliminados {cantidad} trabajos expirados de BD")

    return cantidad
