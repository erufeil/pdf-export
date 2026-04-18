# -*- coding: utf-8 -*-
"""
Servicio Etapa 25: Extraer y editar metadatos profundos de PDF.
Extrae huella digital completa: metadatos estandar, IDs de documento,
permisos, estructura interna, fuentes, JavaScript, firmas digitales, XMP.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF

import config
import models
from utils import job_manager

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────────────────────

def _parse_pdf_date(raw: str) -> str:
    """
    Convierte una fecha PDF (D:YYYYMMDDHHmmSSOHH'mm') a formato legible.
    Retorna la cadena original si no puede parsear.
    """
    if not raw:
        return ''
    # Limpiar prefijo 'D:' y sufijo de zona horaria
    s = raw.strip()
    if s.startswith('D:'):
        s = s[2:]
    # Solo tomar los primeros 14 dígitos
    digitos = re.sub(r'[^\d]', '', s)[:14]
    try:
        if len(digitos) >= 8:
            anio  = int(digitos[0:4])
            mes   = int(digitos[4:6])
            dia   = int(digitos[6:8])
            hora  = int(digitos[8:10]) if len(digitos) >= 10 else 0
            minuto = int(digitos[10:12]) if len(digitos) >= 12 else 0
            seg   = int(digitos[12:14]) if len(digitos) >= 14 else 0
            return f"{anio:04d}-{mes:02d}-{dia:02d} {hora:02d}:{minuto:02d}:{seg:02d}"
    except (ValueError, IndexError):
        pass
    return raw


def _bits_permisos(perm: int) -> dict:
    """
    Decodifica el entero de permisos de PyMuPDF en flags legibles.
    El valor -1 significa 'sin restricciones' (no encriptado).
    """
    if perm == -1:
        return {
            'imprimir':          True,
            'imprimir_alta_cal': True,
            'modificar':         True,
            'copiar':            True,
            'anotar':            True,
            'rellenar_formulario': True,
            'accesibilidad':     True,
            'ensamblar':         True,
            'sin_restricciones': True,
        }
    return {
        'imprimir':          bool(perm & fitz.PDF_PERM_PRINT),
        'imprimir_alta_cal': bool(perm & fitz.PDF_PERM_PRINT_HQ),
        'modificar':         bool(perm & fitz.PDF_PERM_MODIFY),
        'copiar':            bool(perm & fitz.PDF_PERM_COPY),
        'anotar':            bool(perm & fitz.PDF_PERM_ANNOTATE),
        'rellenar_formulario': bool(perm & fitz.PDF_PERM_FORM),
        'accesibilidad':     bool(perm & fitz.PDF_PERM_ACCESSIBILITY),
        'ensamblar':         bool(perm & fitz.PDF_PERM_ASSEMBLE),
        'sin_restricciones': False,
    }


def _tamanio_pagina_str(ancho_pts: float, alto_pts: float) -> str:
    """Convierte puntos a mm y detecta nombre de formato (A4, Letter, etc.)."""
    mm_w = round(ancho_pts * 0.352778, 1)
    mm_h = round(alto_pts * 0.352778, 1)
    # Detectar formato estandar (+-3mm)
    formatos = {
        'A3':      (297, 420),
        'A4':      (210, 297),
        'A5':      (148, 210),
        'Letter':  (216, 279),
        'Legal':   (216, 356),
        'Tabloid': (279, 432),
    }
    for nombre, (fw, fh) in formatos.items():
        if abs(mm_w - fw) <= 3 and abs(mm_h - fh) <= 3:
            return f"{nombre} ({mm_w}×{mm_h} mm)"
        if abs(mm_w - fh) <= 3 and abs(mm_h - fw) <= 3:
            return f"{nombre} Horizontal ({mm_w}×{mm_h} mm)"
    return f"{mm_w}×{mm_h} mm"


def _recolectar_fuentes(doc: fitz.Document) -> list:
    """Extrae lista única de fuentes del documento con flag de incrustada."""
    fuentes_vistas = set()
    fuentes = []
    for num_pag in range(len(doc)):
        for f in doc[num_pag].get_fonts(full=True):
            # f = (xref, ext, type, basefont, name, encoding, referencer)
            nombre = f[3] or f[4] or 'desconocida'
            tipo   = f[2] or ''
            incrustada = bool(f[0])  # xref > 0 significa incrustada
            clave = nombre + tipo
            if clave not in fuentes_vistas:
                fuentes_vistas.add(clave)
                fuentes.append({
                    'nombre':     nombre,
                    'tipo':       tipo,
                    'incrustada': incrustada,
                })
    return fuentes


def _detectar_javascript(doc: fitz.Document) -> bool:
    """Busca acciones JavaScript en el catálogo y páginas del PDF."""
    try:
        # Buscar en todos los xrefs
        for xref in range(1, doc.xref_length()):
            try:
                tipo = doc.xref_get_key(xref, 'S')
                if tipo and 'JavaScript' in str(tipo):
                    return True
            except Exception:
                pass
        # Buscar en el catálogo
        try:
            catalog = doc.pdf_catalog()
            if 'JavaScript' in str(catalog) or 'JS' in str(catalog):
                return True
        except Exception:
            pass
    except Exception:
        pass
    return False


def _detectar_firmas(doc: fitz.Document) -> int:
    """Cuenta campos de firma digital en el PDF."""
    try:
        campos = doc.get_fields()
        if not campos:
            return 0
        return sum(1 for f in campos if f.get('field_type') == 4)  # 4 = firma
    except Exception:
        return 0


def _calcular_hashes(ruta: Path) -> dict:
    """Calcula MD5 y SHA-256 del archivo en disco."""
    md5    = hashlib.md5()
    sha256 = hashlib.sha256()
    with open(ruta, 'rb') as f:
        for bloque in iter(lambda: f.read(65536), b''):
            md5.update(bloque)
            sha256.update(bloque)
    return {
        'sha256': sha256.hexdigest().upper(),
        'md5':    md5.hexdigest().upper(),
    }


def _detectar_capas(doc: fitz.Document) -> list:
    """Retorna lista de nombres de capas OCG (Optional Content Groups)."""
    try:
        ocgs = doc.layer_ui_configs()
        if not ocgs:
            return []
        return [ocg.get('text', '') for ocg in ocgs if ocg.get('text')]
    except Exception:
        return []


def _obtener_id_documento(doc: fitz.Document) -> dict:
    """
    Extrae los IDs del trailer del PDF:
    - id_original: ID asignado al crear el documento
    - id_actual: ID del estado actual (cambia si fue modificado)
    Si ambos son iguales, el PDF nunca fue modificado externamente.
    """
    try:
        id_array = doc.xref_get_key(-1, 'ID')
        if id_array and id_array.strip('[]').strip():
            # Formato: [(hex1)(hex2)] o [<hex1><hex2>]
            partes = re.findall(r'[(<]([0-9a-fA-F]+)[)>]', id_array)
            if len(partes) >= 2:
                return {
                    'id_original': partes[0].upper(),
                    'id_actual':   partes[1].upper(),
                    'fue_modificado': partes[0].upper() != partes[1].upper(),
                }
            elif len(partes) == 1:
                return {
                    'id_original': partes[0].upper(),
                    'id_actual':   partes[0].upper(),
                    'fue_modificado': False,
                }
    except Exception as e:
        logger.debug(f"No se pudo leer ID del documento: {e}")
    return {
        'id_original': '',
        'id_actual':   '',
        'fue_modificado': None,
    }


def _contar_anotaciones(doc: fitz.Document) -> int:
    """Cuenta el total de anotaciones en todas las páginas."""
    total = 0
    for pag in doc:
        try:
            total += len(list(pag.annots()))
        except Exception:
            pass
    return total


def _contar_marcadores(doc: fitz.Document) -> int:
    """Cuenta los marcadores (bookmarks / tabla de contenidos)."""
    try:
        toc = doc.get_toc()
        return len(toc)
    except Exception:
        return 0


def _contar_formularios(doc: fitz.Document) -> int:
    """Cuenta los campos de formulario en el documento."""
    try:
        campos = doc.get_fields()
        return len(campos) if campos else 0
    except Exception:
        return 0


def _contar_adjuntos(doc: fitz.Document) -> int:
    """Cuenta archivos adjuntos (EmbeddedFiles)."""
    try:
        return doc.embfile_count()
    except Exception:
        return 0


def _detectar_linealizacion(doc: fitz.Document) -> bool:
    """Detecta si el PDF está linealizado (optimizado para web)."""
    try:
        val = doc.xref_get_key(1, 'Linearized')
        return bool(val and val.strip() not in ('', 'null', 'false'))
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Función principal de extracción (SINCRONA — sin job)
# ──────────────────────────────────────────────────────────────────────────────

def extraer_metadatos(archivo_id: str) -> dict:
    """
    Extrae todos los metadatos forenses de un PDF.
    Retorna dict estructurado con 6 bloques de información.
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])

    doc = fitz.open(str(ruta_pdf))
    try:
        meta = doc.metadata  # dict con: format, title, author, subject, keywords,
                              # creator, producer, creationDate, modDate, trapped

        # ── Bloque 1: Básicos (editables) ─────────────────────────────────────
        basicos = {
            'titulo':     meta.get('title', ''),
            'autor':      meta.get('author', ''),
            'tema':       meta.get('subject', ''),
            'palabras_clave': meta.get('keywords', ''),
            'creador':    meta.get('creator', ''),     # app que creó el PDF
            'productor':  meta.get('producer', ''),    # librería que generó el PDF
            'trapped':    meta.get('trapped', ''),
        }

        # ── Bloque 2: Fechas ──────────────────────────────────────────────────
        fechas = {
            'creacion':    _parse_pdf_date(meta.get('creationDate', '')),
            'modificacion': _parse_pdf_date(meta.get('modDate', '')),
            'formato_pdf': meta.get('format', ''),
        }

        # ── Bloque 3: Identidad del documento (forense) ───────────────────────
        id_doc = _obtener_id_documento(doc)
        encriptado = doc.is_encrypted
        cifrado_info = ''
        if encriptado:
            try:
                cifrado_info = doc.xref_get_key(-1, 'Encrypt') or 'Sí'
            except Exception:
                cifrado_info = 'Sí'

        identidad = {
            'version_pdf':    meta.get('format', '').replace('PDF ', '').strip(),
            'id_original':    id_doc['id_original'],
            'id_actual':      id_doc['id_actual'],
            'fue_modificado': id_doc['fue_modificado'],
            'encriptado':     encriptado,
            'cifrado_detalle': cifrado_info,
            'linealizado':    _detectar_linealizacion(doc),
            'num_revisiones': doc.xref_length(),   # tamaño de la tabla de xrefs
        }

        # ── Bloque 4: Estructura ──────────────────────────────────────────────
        num_paginas = len(doc)

        # Tamaños de páginas (detectar si son uniformes)
        tamanios_paginas = []
        for i in range(min(num_paginas, 5)):  # muestreo de primeras 5 páginas
            rect = doc[i].rect
            tamanios_paginas.append(_tamanio_pagina_str(rect.width, rect.height))
        tamanio_unico = list(set(tamanios_paginas))

        fuentes = _recolectar_fuentes(doc)
        num_imagenes = sum(len(doc[i].get_images(full=False)) for i in range(num_paginas))

        estructura = {
            'num_paginas':     num_paginas,
            'tamano_pagina':   tamanio_unico[0] if len(tamanio_unico) == 1 else 'Variable',
            'tamanos_muestra': tamanio_unico,
            'num_fuentes':     len(fuentes),
            'fuentes':         fuentes,
            'num_imagenes':    num_imagenes,
            'num_anotaciones': _contar_anotaciones(doc),
            'num_marcadores':  _contar_marcadores(doc),
            'num_formularios': _contar_formularios(doc),
            'num_adjuntos':    _contar_adjuntos(doc),
            'tiene_javascript': _detectar_javascript(doc),
            'num_firmas':      _detectar_firmas(doc),
            'capas':           _detectar_capas(doc),
        }

        # ── Bloque 5: Permisos ────────────────────────────────────────────────
        permisos_raw = doc.permissions
        permisos = _bits_permisos(permisos_raw)
        permisos['valor_raw'] = permisos_raw

        # ── Bloque 6: XMP completo ────────────────────────────────────────────
        try:
            xmp_xml = doc.get_xml_metadata() or ''
        except Exception:
            xmp_xml = ''

        # ── Hashes del archivo ────────────────────────────────────────────────
        hashes = _calcular_hashes(ruta_pdf)

        return {
            'basicos':    basicos,
            'fechas':     fechas,
            'identidad':  identidad,
            'estructura': estructura,
            'permisos':   permisos,
            'xmp_xml':    xmp_xml,
            'hashes':     hashes,
            'nombre_archivo': archivo['nombre_original'],
            'tamano_bytes':   archivo['tamano_bytes'],
        }

    finally:
        doc.close()


# ──────────────────────────────────────────────────────────────────────────────
# Función de edición (ASINCRONA — usa job_manager)
# ──────────────────────────────────────────────────────────────────────────────

def procesar_edicion_metadatos(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Edita los metadatos básicos de un PDF y lo retorna como PDF directo (sin ZIP).
    Solo modifica los campos básicos: title, author, subject, keywords, creator, producer.
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf    = Path(archivo['ruta_archivo'])
    nombre_orig = archivo['nombre_original']

    job_manager.actualizar_progreso(trabajo_id, 10, "Abriendo PDF")

    doc = fitz.open(str(ruta_pdf))
    try:
        meta_actual = doc.metadata.copy()

        job_manager.actualizar_progreso(trabajo_id, 30, "Aplicando nuevos metadatos")

        # Combinar metadatos actuales con los nuevos proporcionados
        nuevos = {
            'title':     parametros.get('titulo',   meta_actual.get('title', '')),
            'author':    parametros.get('autor',    meta_actual.get('author', '')),
            'subject':   parametros.get('tema',     meta_actual.get('subject', '')),
            'keywords':  parametros.get('palabras_clave', meta_actual.get('keywords', '')),
            'creator':   parametros.get('creador',  meta_actual.get('creator', '')),
            'producer':  parametros.get('productor', meta_actual.get('producer', '')),
        }
        # Actualizar fecha de modificación al momento actual
        ahora = datetime.now(timezone.utc)
        nuevos['modDate'] = ahora.strftime("D:%Y%m%d%H%M%SZ")

        doc.set_metadata(nuevos)

        job_manager.actualizar_progreso(trabajo_id, 70, "Guardando PDF")

        nombre_salida = f"{trabajo_id}_{Path(nombre_orig).stem}_metadatos_editados.pdf"
        ruta_salida = config.OUTPUT_FOLDER / nombre_salida

        doc.save(str(ruta_salida), garbage=4, deflate=True)

    finally:
        doc.close()

    job_manager.actualizar_progreso(trabajo_id, 100, "Completado")

    return {
        'ruta_resultado': str(ruta_salida),
        'mensaje': 'Metadatos editados correctamente',
    }


# Registrar procesador de edición en el job_manager
job_manager.registrar_procesador('metadata-edit', procesar_edicion_metadatos)
