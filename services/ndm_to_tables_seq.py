# -*- coding: utf-8 -*-
"""
Servicio de ordenamiento secuencial de tablas SQL para PDFexport.
Analiza archivos Navicat Data Modeler (.ndm2) y genera el orden
de migracion de tablas respetando dependencias de foreign keys.
"""

import json
import logging
from pathlib import Path

import config
import models
from utils import job_manager

logger = logging.getLogger(__name__)


def cargar_ndm(ruta_archivo: Path) -> dict:
    """
    Carga y parsea un archivo .ndm2 (formato JSON).

    Args:
        ruta_archivo: Ruta al archivo .ndm2

    Returns:
        dict con el contenido JSON parseado
    """
    with open(ruta_archivo, 'r', encoding='utf-8') as f:
        return json.load(f)


def extraer_tablas_y_fks(json_ndm: dict) -> tuple:
    """
    Extrae nombre de la base de datos, tablas y sus foreign keys del JSON.

    Args:
        json_ndm: Contenido del archivo .ndm2 parseado

    Returns:
        Tupla (nombre_db, lista_tablas) donde lista_tablas contiene
        dicts con 'nombre' y 'foreign_keys'
    """
    # Acceder al primer esquema
    esquema = json_ndm["server"]["schemas"][0]
    nombre_db = esquema["name"]
    tablas_json = esquema["tables"]

    lista_tablas = []
    for tabla in tablas_json:
        nombre_tabla = tabla["name"]
        fks = tabla.get("foreignKeys", [])

        # Extraer referencias de cada FK
        referencias = []
        for fk in fks:
            referencias.append({
                'db_referencia': fk.get("referenceSchema", ""),
                'tabla_referencia': fk.get("referenceTable", "")
            })

        lista_tablas.append({
            'nombre': nombre_tabla,
            'foreign_keys': referencias
        })

    return nombre_db, lista_tablas


def ordenar_tablas(nombre_db: str, lista_tablas: list) -> tuple:
    """
    Ordena las tablas segun dependencias de FK.
    Implementa el algoritmo de ordenamiento topologico manual.

    Args:
        nombre_db: Nombre de la base de datos principal
        lista_tablas: Lista de dicts con 'nombre' y 'foreign_keys'

    Returns:
        Tupla (orden_de_migracion, notas_al_pie)
    """
    notas_al_pie = []

    # Crear diccionario rapido: nombre_tabla -> foreign_keys
    mapa_fks = {}
    for tabla in lista_tablas:
        mapa_fks[tabla['nombre']] = tabla['foreign_keys']

    # --- Paso 1: Primer orden - tablas sin FK al inicio, con FK al final ---
    orden_de_migracion = []
    for tabla in lista_tablas:
        if len(tabla['foreign_keys']) == 0:
            orden_de_migracion.insert(0, tabla['nombre'])
        else:
            orden_de_migracion.append(tabla['nombre'])

    # Limite de iteraciones para detectar dependencias circulares
    max_iteraciones = len(orden_de_migracion)
    iteraciones = 0

    # --- Paso 2: Orden de prioridad por FK ---
    control_cambios = 1  # Iniciar en 1 para entrar al loop

    while control_cambios == 1:
        control_cambios = 0

        # Recorrer la lista de principio a fin
        i = 0
        while i < len(orden_de_migracion):
            nombre_tabla_lista = orden_de_migracion[i]
            posicion_tabla_lista = i
            fks_de_tabla = mapa_fks.get(nombre_tabla_lista, [])

            # Si no tiene FKs, pasar al siguiente
            if len(fks_de_tabla) == 0:
                i += 1
                continue

            # Recorrer cada FK de la tabla
            for fk in fks_de_tabla:
                db_tabla_fk = fk['db_referencia']
                tabla_fk = fk['tabla_referencia']

                # Verificar si la FK apunta a otra base de datos
                if db_tabla_fk != nombre_db:
                    nota = f'WARNING: {tabla_fk} pertenece a la base de datos {db_tabla_fk}'
                    if nota not in notas_al_pie:
                        notas_al_pie.append(nota)
                    continue

                # Buscar posicion de la tabla referenciada
                if tabla_fk not in orden_de_migracion:
                    nota = f'WARNING: {tabla_fk} referenciada por {nombre_tabla_lista} no encontrada en el esquema'
                    if nota not in notas_al_pie:
                        notas_al_pie.append(nota)
                    continue

                posicion_tabla_fk = orden_de_migracion.index(tabla_fk)

                # Si la tabla referenciada esta despues, mover la tabla actual
                if posicion_tabla_fk > posicion_tabla_lista:
                    orden_de_migracion.remove(nombre_tabla_lista)
                    orden_de_migracion.insert(posicion_tabla_fk, nombre_tabla_lista)
                    control_cambios = 1
                    break  # Reiniciar el recorrido de FKs porque la posicion cambio

            i += 1

        # Verificar limite de iteraciones (detectar dependencias circulares)
        if control_cambios == 1:
            iteraciones += 1
            if iteraciones >= max_iteraciones:
                notas_al_pie.append('WARNING: Posible dependencia circular detectada')
                break

    return orden_de_migracion, notas_al_pie


def generar_txt(nombre_db: str, orden_de_migracion: list, notas_al_pie: list) -> str:
    """
    Genera el contenido del archivo TXT con el orden de migracion.
    Formato compatible con Notepad de Windows (CRLF).

    Args:
        nombre_db: Nombre de la base de datos
        orden_de_migracion: Lista ordenada de nombres de tablas
        notas_al_pie: Lista de advertencias

    Returns:
        Contenido del archivo TXT
    """
    lineas = []

    # Titulo
    lineas.append(f'Orden de migracion de {nombre_db}')
    lineas.append('=' * 50)
    lineas.append('')

    # Cuerpo: lista numerada
    for i, tabla in enumerate(orden_de_migracion, 1):
        lineas.append(f'{i}. {tabla}')

    # Pie del documento
    if notas_al_pie:
        lineas.append('')
        lineas.append('-' * 50)
        lineas.append('Notas:')
        for nota in notas_al_pie:
            lineas.append(f'  * {nota}')

    lineas.append('')
    lineas.append(f'Total: {len(orden_de_migracion)} tablas')

    # Unir con CRLF para compatibilidad con Notepad de Windows
    return '\r\n'.join(lineas)


def procesar_ndm_to_tables_seq(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal de ordenamiento de tablas SQL.
    Esta funcion es llamada por el job_manager.

    Args:
        trabajo_id: ID del trabajo
        archivo_id: ID del archivo a procesar
        parametros: Opciones (sin_comprimir, formato_salida)

    Returns:
        dict con ruta_resultado y mensaje
    """
    # Obtener archivo
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_archivo = Path(archivo['ruta_archivo'])
    if not ruta_archivo.exists():
        raise ValueError("Archivo fisico no encontrado")

    job_manager.actualizar_progreso(trabajo_id, 10, "Cargando archivo NDM")

    # Cargar y parsear el JSON
    try:
        json_ndm = cargar_ndm(ruta_archivo)
    except json.JSONDecodeError as e:
        raise ValueError(f"El archivo no es un JSON valido: {e}")
    except Exception as e:
        raise ValueError(f"Error al leer el archivo: {e}")

    job_manager.actualizar_progreso(trabajo_id, 25, "Extrayendo tablas y foreign keys")

    # Extraer tablas y FKs
    try:
        nombre_db, lista_tablas = extraer_tablas_y_fks(json_ndm)
    except (KeyError, IndexError) as e:
        raise ValueError(f"Estructura del archivo NDM no valida: {e}")

    job_manager.actualizar_progreso(trabajo_id, 40, f"Ordenando {len(lista_tablas)} tablas")

    # Ejecutar algoritmo de ordenamiento
    orden_de_migracion, notas_al_pie = ordenar_tablas(nombre_db, lista_tablas)

    job_manager.actualizar_progreso(trabajo_id, 75, "Generando archivo de salida")

    # Generar contenido TXT
    contenido_txt = generar_txt(nombre_db, orden_de_migracion, notas_al_pie)

    # Guardar archivo TXT directamente (sin comprimir)
    nombre_txt = 'Orden_secuencial_migracion_SQL_ERF.txt'
    ruta_txt = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_txt}"

    with open(ruta_txt, 'w', encoding='utf-8') as f:
        f.write(contenido_txt)

    job_manager.actualizar_progreso(trabajo_id, 95, "Finalizando")

    # Contar warnings
    num_warnings = len(notas_al_pie)
    mensaje_warnings = f' ({num_warnings} advertencias)' if num_warnings > 0 else ''

    return {
        'ruta_resultado': str(ruta_txt),
        'mensaje': f'Orden generado: {len(orden_de_migracion)} tablas{mensaje_warnings}'
    }


# Registrar el procesador en el job_manager
job_manager.registrar_procesador('ndm-to-tables-seq', procesar_ndm_to_tables_seq)
