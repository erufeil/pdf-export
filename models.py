# -*- coding: utf-8 -*-
"""
Modelos de base de datos SQLite para PDFexport.
Gestiona archivos subidos y trabajos de conversion.
"""

import sqlite3
import uuid
import binascii
from datetime import datetime, timedelta
from contextlib import contextmanager
import logging

import config

logger = logging.getLogger(__name__)


def _crc32(texto: str) -> int:
    """CRC32 del contenido como entero sin signo. Coincide con binascii.crc32 de Python."""
    return binascii.crc32(texto.encode('utf-8')) & 0xFFFFFFFF


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

        # Tabla de notepads compartidos (Etapa 45)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notepads (
                slug                TEXT PRIMARY KEY,
                contenido           TEXT NOT NULL DEFAULT '',
                version             INTEGER NOT NULL DEFAULT 1,
                fecha_creacion      TEXT NOT NULL,
                fecha_modificacion  TEXT NOT NULL,
                fecha_ultimo_acceso TEXT NOT NULL
            )
        ''')

        # Presencia: IPs activas por slug (ventana 45s)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notepad_presencia (
                slug        TEXT NOT NULL,
                ip          TEXT NOT NULL,
                ultimo_ping TEXT NOT NULL,
                PRIMARY KEY (slug, ip)
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notepads_acceso ON notepads(fecha_ultimo_acceso)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_presencia_slug ON notepad_presencia(slug)')

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


# =============================================================================
# Funciones para NOTEPADS (Etapa 45)
# =============================================================================

def _registrar_presencia(cursor, slug: str, ip: str):
    """Upsert de presencia del cliente. Requiere cursor dentro de una conexión activa."""
    cursor.execute('''
        INSERT INTO notepad_presencia (slug, ip, ultimo_ping) VALUES (?, ?, ?)
        ON CONFLICT(slug, ip) DO UPDATE SET ultimo_ping = excluded.ultimo_ping
    ''', (slug, ip, datetime.now().isoformat()))


def _leer_presencia(cursor, slug: str, ip_cliente: str) -> list:
    """IPs activas en los últimos 45s. Marca es_yo para la IP del cliente."""
    limite = (datetime.now() - timedelta(seconds=45)).isoformat()
    cursor.execute(
        'SELECT ip FROM notepad_presencia WHERE slug = ? AND ultimo_ping > ? ORDER BY ultimo_ping DESC',
        (slug, limite)
    )
    return [{'ip': row['ip'], 'es_yo': row['ip'] == ip_cliente} for row in cursor.fetchall()]


def obtener_o_crear_notepad(slug: str, ip: str) -> dict:
    """Obtiene el notepad o lo crea vacío. Registra presencia y retorna visitantes."""
    ahora = datetime.now().isoformat()
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM notepads WHERE slug = ?', (slug,))
        row = cursor.fetchone()
        if row:
            cursor.execute('UPDATE notepads SET fecha_ultimo_acceso = ? WHERE slug = ?', (ahora, slug))
            notepad = dict(row)
        else:
            cursor.execute('''
                INSERT INTO notepads (slug, contenido, version, fecha_creacion, fecha_modificacion, fecha_ultimo_acceso)
                VALUES (?, '', 1, ?, ?, ?)
            ''', (slug, ahora, ahora, ahora))
            notepad = {'slug': slug, 'contenido': '', 'version': 1,
                       'fecha_creacion': ahora, 'fecha_modificacion': ahora}
        _registrar_presencia(cursor, slug, ip)
        visitantes = _leer_presencia(cursor, slug, ip)
    return {**notepad, 'visitantes': visitantes, 'crc32': _crc32(notepad.get('contenido', ''))}


def guardar_notepad(slug: str, contenido: str, ip: str) -> dict:
    """Guarda contenido (last-write-wins). Retorna versión, fecha y visitantes."""
    ahora = datetime.now().isoformat()
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE notepads
            SET contenido = ?, version = version + 1, fecha_modificacion = ?, fecha_ultimo_acceso = ?
            WHERE slug = ?
        ''', (contenido, ahora, ahora, slug))
        if cursor.rowcount == 0:
            cursor.execute('''
                INSERT INTO notepads (slug, contenido, version, fecha_creacion, fecha_modificacion, fecha_ultimo_acceso)
                VALUES (?, ?, 1, ?, ?, ?)
            ''', (slug, contenido, ahora, ahora, ahora))
            version = 1
        else:
            cursor.execute('SELECT version FROM notepads WHERE slug = ?', (slug,))
            version = cursor.fetchone()['version']
        _registrar_presencia(cursor, slug, ip)
        visitantes = _leer_presencia(cursor, slug, ip)
    return {'version': version, 'fecha_modificacion': ahora, 'visitantes': visitantes, 'crc32': _crc32(contenido)}


def aplicar_deltas_notepad(slug: str, deltas: list, ip: str) -> dict | None:
    """Aplica deltas de líneas al notepad. Retorna {version, crc32, visitantes} o None si no existe."""
    ahora = datetime.now().isoformat()
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT contenido FROM notepads WHERE slug = ?', (slug,))
        row = cursor.fetchone()
        if not row:
            return None
        lineas = row['contenido'].split('\n') if row['contenido'] else ['']

        edits   = [d for d in deltas if 'op' not in d]
        inserts = sorted([d for d in deltas if d.get('op') == 'insert'], key=lambda x: x['n'])
        deletes = sorted([d for d in deltas if d.get('op') == 'delete'], key=lambda x: x['n'], reverse=True)

        for d in edits:
            n = d['n']
            while len(lineas) <= n:
                lineas.append('')
            lineas[n] = d.get('texto', '')

        for d in inserts:
            n = d['n']
            if n <= len(lineas):
                lineas.insert(n, d.get('texto', ''))
            else:
                lineas.append(d.get('texto', ''))

        for d in deletes:
            n = d['n']
            if 0 <= n < len(lineas):
                lineas.pop(n)

        nuevo_contenido = '\n'.join(lineas)
        crc = _crc32(nuevo_contenido)
        cursor.execute('''
            UPDATE notepads
            SET contenido = ?, version = version + 1,
                fecha_modificacion = ?, fecha_ultimo_acceso = ?
            WHERE slug = ?
        ''', (nuevo_contenido, ahora, ahora, slug))
        cursor.execute('SELECT version FROM notepads WHERE slug = ?', (slug,))
        version = cursor.fetchone()['version']
        _registrar_presencia(cursor, slug, ip)
        visitantes = _leer_presencia(cursor, slug, ip)
    return {'version': version, 'crc32': crc, 'visitantes': visitantes}


def eliminar_notepad(slug: str) -> bool:
    """Elimina el notepad y su presencia. Retorna True si existía."""
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM notepad_presencia WHERE slug = ?', (slug,))
        cursor.execute('DELETE FROM notepads WHERE slug = ?', (slug,))
        return cursor.rowcount > 0


def eliminar_notepads_expirados() -> int:
    """Elimina notepads sin acceso en 30 días. Retorna cantidad eliminada."""
    limite = (datetime.now() - timedelta(days=30)).isoformat()
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT slug FROM notepads WHERE fecha_ultimo_acceso < ?', (limite,))
        slugs = [row['slug'] for row in cursor.fetchall()]
        if slugs:
            placeholders = ','.join('?' * len(slugs))
            cursor.execute(f'DELETE FROM notepad_presencia WHERE slug IN ({placeholders})', slugs)
            cursor.execute(f'DELETE FROM notepads WHERE slug IN ({placeholders})', slugs)
    if slugs:
        logger.info(f"Notepads expirados eliminados: {len(slugs)}")
    return len(slugs)
