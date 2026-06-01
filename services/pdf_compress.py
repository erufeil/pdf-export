# -*- coding: utf-8 -*-
import hashlib
import logging
from io import BytesIO
from pathlib import Path
from typing import Dict, Tuple

import fitz  # PyMuPDF
from PIL import Image

import config
import models
from utils import file_manager, job_manager

logger = logging.getLogger(__name__)

# Presets: definen el valor por defecto de cada opción booleana/numérica
PRESETS: Dict[str, dict] = {
    'ligero': {
        'reimagenes': False, 'dpi': 150, 'calidad_jpeg': 85,
        'grises': False, 'dedup_imagenes': False,
        'subset_fuentes': False, 'dedup_fuentes': False,
        'eliminar_xmp': True, 'limpiar_basicos': False, 'eliminar_thumbnails': True,
        'garbage': True, 'comprimir_streams': True, 'dedup_objetos': True,
        'bajar_version': False, 'eliminar_tags': False,
        'eliminar_anotaciones': False, 'aplanar_formularios': False,
        'eliminar_js': True, 'eliminar_firmas': False, 'eliminar_adjuntos': False,
        'eliminar_marcadores': False, 'eliminar_ocg': False,
        'linearizar': False,
    },
    'estandar': {
        'reimagenes': True, 'dpi': 150, 'calidad_jpeg': 85,
        'grises': False, 'dedup_imagenes': False,
        'subset_fuentes': False, 'dedup_fuentes': False,
        'eliminar_xmp': True, 'limpiar_basicos': False, 'eliminar_thumbnails': True,
        'garbage': True, 'comprimir_streams': True, 'dedup_objetos': True,
        'bajar_version': False, 'eliminar_tags': False,
        'eliminar_anotaciones': False, 'aplanar_formularios': False,
        'eliminar_js': True, 'eliminar_firmas': False, 'eliminar_adjuntos': False,
        'eliminar_marcadores': False, 'eliminar_ocg': False,
        'linearizar': False,
    },
    'agresivo': {
        'reimagenes': True, 'dpi': 96, 'calidad_jpeg': 60,
        'grises': False, 'dedup_imagenes': True,
        'subset_fuentes': True, 'dedup_fuentes': True,
        'eliminar_xmp': True, 'limpiar_basicos': False, 'eliminar_thumbnails': True,
        'garbage': True, 'comprimir_streams': True, 'dedup_objetos': True,
        'bajar_version': False, 'eliminar_tags': False,
        'eliminar_anotaciones': True, 'aplanar_formularios': False,
        'eliminar_js': True, 'eliminar_firmas': False, 'eliminar_adjuntos': True,
        'eliminar_marcadores': False, 'eliminar_ocg': True,
        'linearizar': False,
    },
    'maximo': {
        'reimagenes': True, 'dpi': 72, 'calidad_jpeg': 60,
        'grises': True, 'dedup_imagenes': True,
        'subset_fuentes': True, 'dedup_fuentes': True,
        'eliminar_xmp': True, 'limpiar_basicos': False, 'eliminar_thumbnails': True,
        'garbage': True, 'comprimir_streams': True, 'dedup_objetos': True,
        'bajar_version': False, 'eliminar_tags': False,
        'eliminar_anotaciones': True, 'aplanar_formularios': False,
        'eliminar_js': True, 'eliminar_firmas': False, 'eliminar_adjuntos': True,
        'eliminar_marcadores': False, 'eliminar_ocg': True,
        'linearizar': True,
    },
}


# ─── Helpers internos ───────────────────────────────────────────────────────

def _recomprimir_imagenes(doc: fitz.Document, dpi: int, calidad: int,
                          grises: bool, dedup: bool) -> None:
    """Recomprime todas las imágenes únicas del documento."""
    xrefs_vistos: set = set()
    xrefs: list = []
    for pag in doc:
        for info in pag.get_images(full=True):
            xref = info[0]
            if xref not in xrefs_vistos:
                xrefs_vistos.add(xref)
                xrefs.append(xref)

    # Detectar duplicados si se solicita
    hash_a_xref: dict = {}
    xrefs_duplicados: set = set()
    if dedup:
        for xref in xrefs:
            try:
                img_data = doc.extract_image(xref)
                if img_data:
                    h = hashlib.sha256(img_data['image']).hexdigest()
                    if h in hash_a_xref:
                        xrefs_duplicados.add(xref)
                    else:
                        hash_a_xref[h] = xref
            except Exception:
                pass

    factor = dpi / 150.0

    for xref in xrefs:
        if xref in xrefs_duplicados:
            continue
        try:
            img_data = doc.extract_image(xref)
            if not img_data:
                continue
            orig = img_data['image']
            ancho = img_data.get('width', 0)
            alto  = img_data.get('height', 0)

            img = Image.open(BytesIO(orig))
            if grises:
                img = img.convert('L')
            elif img.mode == 'RGBA':
                img = img.convert('RGB')
            elif img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')

            if factor < 1.0:
                nw = max(50, int(ancho * factor))
                nh = max(50, int(alto  * factor))
                img = img.resize((nw, nh), Image.LANCZOS)

            buf = BytesIO()
            img.save(buf, format='JPEG', quality=calidad, optimize=True)
            nuevos = buf.getvalue()

            if len(nuevos) < len(orig):
                pix = fitz.Pixmap(nuevos)
                for pag in doc:
                    if xref in [i[0] for i in pag.get_images(full=True)]:
                        pag.replace_image(xref, pixmap=pix)
                        break

        except Exception as e:
            logger.warning(f"Error imagen xref={xref}: {e}")


def _eliminar_thumbnails(doc: fitz.Document) -> None:
    """Elimina thumbnails embebidos en las páginas del PDF."""
    for pag in doc:
        try:
            tipo, _ = doc.xref_get_key(pag.xref, 'Thumb')
            if tipo != 'null':
                doc.xref_set_key(pag.xref, 'Thumb', 'null')
        except Exception:
            pass


def _eliminar_javascript(doc: fitz.Document) -> None:
    """Elimina objetos JavaScript del PDF iterando el xref."""
    try:
        for xref in range(1, doc.xref_length()):
            for key in ('JS', 'JavaScript'):
                try:
                    tipo, _ = doc.xref_get_key(xref, key)
                    if tipo != 'null':
                        doc.xref_set_key(xref, key, 'null')
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Error eliminando JS: {e}")


def _eliminar_adjuntos(doc: fitz.Document) -> None:
    """Elimina archivos adjuntos embebidos (EmbeddedFiles)."""
    try:
        count = doc.embfile_count()
        for i in range(count - 1, -1, -1):
            try:
                doc.embfile_del(i)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Error eliminando adjuntos: {e}")


def _aplanar_formularios(doc: fitz.Document) -> None:
    """Elimina campos de formulario (los borra, no los aplana a texto)."""
    for pag in doc:
        for w in list(pag.widgets() or []):
            try:
                pag.delete_widget(w)
            except Exception:
                pass


def _eliminar_ocg(doc: fitz.Document) -> None:
    """Elimina capas opcionales (OCG) del catálogo."""
    try:
        cat = doc.pdf_catalog()
        tipo, _ = doc.xref_get_key(cat, 'OCProperties')
        if tipo != 'null':
            doc.xref_set_key(cat, 'OCProperties', 'null')
    except Exception as e:
        logger.warning(f"Error eliminando OCG: {e}")


# ─── Análisis ────────────────────────────────────────────────────────────────

def analizar_pdf(archivo_id: str) -> dict:
    """
    Analiza un PDF y devuelve estadísticas detalladas por categoría
    junto con estimaciones de ahorro para mostrar en la UI.
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")
    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo físico no encontrado")

    tamano_bytes = ruta_pdf.stat().st_size
    doc = fitz.open(str(ruta_pdf))
    try:
        # ── A. Imágenes ──────────────────────────────────────────────────
        xrefs_vistos: set = set()
        imagenes: list = []
        total_bytes_img = 0
        for pag in doc:
            for info in pag.get_images(full=True):
                xref = info[0]
                if xref in xrefs_vistos:
                    continue
                xrefs_vistos.add(xref)
                try:
                    img_data = doc.extract_image(xref)
                    if img_data:
                        nb = len(img_data.get('image', b''))
                        imagenes.append({'xref': xref, 'bytes': nb})
                        total_bytes_img += nb
                except Exception:
                    pass

        # Duplicadas
        hashes: dict = {}
        duplicadas = 0
        for img in imagenes:
            try:
                img_data = doc.extract_image(img['xref'])
                if img_data:
                    h = hashlib.sha256(img_data['image']).hexdigest()
                    if h in hashes:
                        duplicadas += 1
                    else:
                        hashes[h] = img['xref']
            except Exception:
                pass

        pct_img = int(total_bytes_img / tamano_bytes * 100) if tamano_bytes > 0 else 0
        pct_img = min(pct_img, 95)
        # Ahorro estimado: compresión a 85% JPEG reduce ~45% del peso de imágenes
        ahorro_img = int(pct_img * 0.45)

        # ── B. Fuentes ───────────────────────────────────────────────────
        fuentes_nombres: set = set()
        fuentes_embebidas = 0
        fuentes_subseteadas = 0
        for pag in doc:
            for f in pag.get_fonts(full=True):
                nombre = f[3] or f[4] or ''
                if nombre and nombre not in fuentes_nombres:
                    fuentes_nombres.add(nombre)
                    if f[2]:  # tipo de fuente (no vacío → embebida probable)
                        fuentes_embebidas += 1
                    if '+' in nombre:  # nombre subseteado: "ABCDEF+FontName"
                        fuentes_subseteadas += 1
        ahorro_fuentes = 5 if fuentes_embebidas > 2 else (2 if fuentes_embebidas > 0 else 0)

        # ── C. Metadatos ─────────────────────────────────────────────────
        meta = doc.metadata or {}
        tiene_xmp = bool(doc.get_xml_metadata())
        tiene_thumbnails = False
        for pag in doc:
            try:
                tipo, _ = doc.xref_get_key(pag.xref, 'Thumb')
                if tipo != 'null':
                    tiene_thumbnails = True
                    break
            except Exception:
                pass
        campos_basicos = [k for k, v in {
            'Título': meta.get('title'), 'Autor': meta.get('author'),
            'Asunto': meta.get('subject'), 'Palabras clave': meta.get('keywords'),
            'Creador': meta.get('creator'), 'Productor': meta.get('producer'),
        }.items() if v]
        ahorro_meta = 1 if (tiene_xmp or tiene_thumbnails) else 0

        # ── D. Estructura ────────────────────────────────────────────────
        version_pdf = (meta.get('format') or 'PDF 1.4').replace('PDF ', '')
        tiene_tags = False
        try:
            cat = doc.pdf_catalog()
            tipo, _ = doc.xref_get_key(cat, 'MarkInfo')
            if tipo not in ('null', ''):
                tiene_tags = True
        except Exception:
            pass
        ahorro_estructura = 3  # garbage + deflate siempre ayudan

        # ── E. Elementos interactivos ────────────────────────────────────
        total_anot = sum(len(list(pag.annots() or [])) for pag in doc)
        total_form = sum(len(list(pag.widgets() or [])) for pag in doc)
        total_adj = 0
        try:
            total_adj = doc.embfile_count()
        except Exception:
            pass
        ahorro_interactivo = 2 if (total_anot + total_adj) > 0 else 0

        # ── F. Navegación ────────────────────────────────────────────────
        toc = doc.get_toc()
        total_marcadores = len(toc)
        tiene_ocg = False
        try:
            cat = doc.pdf_catalog()
            tipo, _ = doc.xref_get_key(cat, 'OCProperties')
            if tipo != 'null':
                tiene_ocg = True
        except Exception:
            pass
        ahorro_navegacion = 1 if (total_marcadores > 5 or tiene_ocg) else 0

        # ── G. Optimización ──────────────────────────────────────────────
        esta_linearizado = False
        try:
            tipo, _ = doc.xref_get_key(-1, 'Linearized')
            esta_linearizado = tipo != 'null'
        except Exception:
            pass

        return {
            'tamanio_bytes': tamano_bytes,
            'tamanio_texto': file_manager.formatear_tamano(tamano_bytes),
            'paginas': len(doc),
            'imagenes': {
                'total': len(imagenes),
                'tamanio_estimado_bytes': total_bytes_img,
                'tamanio_estimado_texto': file_manager.formatear_tamano(total_bytes_img),
                'porcentaje_del_pdf': pct_img,
                'tiene_duplicadas': duplicadas > 0,
                'duplicadas': duplicadas,
                'ahorro_estimado_pct': ahorro_img,
            },
            'fuentes': {
                'total': len(fuentes_nombres),
                'embebidas': fuentes_embebidas,
                'subseteadas': fuentes_subseteadas,
                'ahorro_estimado_pct': ahorro_fuentes,
            },
            'metadatos': {
                'tiene_xmp': tiene_xmp,
                'tiene_thumbnails': tiene_thumbnails,
                'campos_basicos': campos_basicos,
                'ahorro_estimado_pct': ahorro_meta,
            },
            'estructura': {
                'tiene_tags_accesibilidad': tiene_tags,
                'version_pdf': version_pdf,
                'objetos_total': doc.xref_length(),
                'ahorro_estimado_pct': ahorro_estructura,
            },
            'interactivo': {
                'anotaciones': total_anot,
                'formularios': total_form,
                'firmas': 0,
                'adjuntos': total_adj,
                'ahorro_estimado_pct': ahorro_interactivo,
            },
            'navegacion': {
                'marcadores': total_marcadores,
                'tiene_ocg': tiene_ocg,
                'ahorro_estimado_pct': ahorro_navegacion,
            },
            'optimizacion': {
                'esta_linearizado': esta_linearizado,
                'ahorro_estimado_pct': 1,
            },
        }
    finally:
        doc.close()


# ─── Compresión ──────────────────────────────────────────────────────────────

def _resolver_opts(parametros: dict) -> dict:
    """
    Mezcla el preset base con las opciones explícitas del request.
    Las claves explícitas (distintas de 'preset') sobreescriben el preset.
    Soporta también la API antigua (nivel/dpi_maximo/calidad_jpg/...).
    """
    # ── Compatibilidad con API antigua ──────────────────────────────────
    if 'nivel' in parametros:
        mapa = {'baja': 'ligero', 'media': 'estandar', 'alta': 'agresivo'}
        nombre_preset = mapa.get(parametros['nivel'], 'estandar')
        opts = dict(PRESETS[nombre_preset])
        if 'dpi_maximo' in parametros:
            opts['dpi'] = int(parametros['dpi_maximo'])
        if 'calidad_jpg' in parametros:
            opts['calidad_jpeg'] = int(parametros['calidad_jpg'])
        if parametros.get('eliminar_metadatos'):
            opts['eliminar_xmp'] = True
            opts['limpiar_basicos'] = True
        if 'eliminar_anotaciones' in parametros:
            opts['eliminar_anotaciones'] = bool(parametros['eliminar_anotaciones'])
        if 'eliminar_bookmarks' in parametros:
            opts['eliminar_marcadores'] = bool(parametros['eliminar_bookmarks'])
        if 'escala_grises' in parametros:
            opts['grises'] = bool(parametros['escala_grises'])
        return opts

    # ── API nueva ────────────────────────────────────────────────────────
    preset_nombre = parametros.get('preset', 'estandar')
    base = dict(PRESETS.get(preset_nombre, PRESETS['estandar']))
    # Sobreescribir con valores explícitos (excepto 'preset')
    for k, v in parametros.items():
        if k != 'preset':
            base[k] = v
    return base


def comprimir_pdf(ruta_pdf: Path, parametros: dict, trabajo_id: str,
                  nombre_original: str) -> Tuple[Path, int, int]:
    """
    Comprime el PDF aplicando las opciones indicadas.
    Devuelve (ruta_comprimido, tamano_original, tamano_final).
    """
    opts = _resolver_opts(parametros)
    tamano_original = ruta_pdf.stat().st_size

    job_manager.actualizar_progreso(trabajo_id, 5, "Abriendo documento")
    doc = fitz.open(str(ruta_pdf))

    try:
        # A — Imágenes ─────────────────────────────────────────────────
        if opts.get('reimagenes', True) or opts.get('grises', False):
            job_manager.actualizar_progreso(trabajo_id, 15, "Recomprimiendo imágenes")
            _recomprimir_imagenes(
                doc,
                dpi=int(opts.get('dpi', 150)),
                calidad=int(opts.get('calidad_jpeg', 85)),
                grises=bool(opts.get('grises', False)),
                dedup=bool(opts.get('dedup_imagenes', False)),
            )

        job_manager.actualizar_progreso(trabajo_id, 55, "Procesando metadatos y estructura")

        # C — Metadatos ────────────────────────────────────────────────
        if opts.get('eliminar_xmp', True):
            try:
                doc.set_xml_metadata('')
            except Exception as e:
                logger.warning(f"Error eliminando XMP: {e}")

        if opts.get('limpiar_basicos', False):
            doc.set_metadata({})

        if opts.get('eliminar_thumbnails', True):
            _eliminar_thumbnails(doc)

        # E — Elementos interactivos ────────────────────────────────────
        if opts.get('eliminar_anotaciones', False):
            job_manager.actualizar_progreso(trabajo_id, 65, "Eliminando anotaciones")
            for pag in doc:
                for annot in list(pag.annots() or []):
                    try:
                        pag.delete_annot(annot)
                    except Exception:
                        pass

        if opts.get('eliminar_js', True):
            _eliminar_javascript(doc)

        if opts.get('eliminar_adjuntos', False):
            _eliminar_adjuntos(doc)

        if opts.get('aplanar_formularios', False):
            _aplanar_formularios(doc)

        # F — Navegación ────────────────────────────────────────────────
        if opts.get('eliminar_marcadores', False):
            doc.set_toc([])

        if opts.get('eliminar_ocg', False):
            _eliminar_ocg(doc)

        job_manager.actualizar_progreso(trabajo_id, 85, "Guardando y optimizando")

        stem = Path(nombre_original).stem
        nombre_salida = f"{trabajo_id}_{stem} - Comprimido.pdf"
        ruta_salida = config.OUTPUT_FOLDER / nombre_salida

        # D + B + G — flags de save PyMuPDF
        doc.save(
            str(ruta_salida),
            garbage=4 if opts.get('garbage', True) else 0,
            compress=opts.get('comprimir_streams', True),
            deflate=opts.get('comprimir_streams', True),
            deflate_images=opts.get('comprimir_streams', True),
            clean=True,
            linear=opts.get('linearizar', False),
        )

        tamano_final = ruta_salida.stat().st_size
        return ruta_salida, tamano_original, tamano_final

    finally:
        doc.close()


# ─── Info (compat. GET /compress/info antiguo) ───────────────────────────────

def obtener_info_compresion(archivo_id: str) -> dict:
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")
    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo físico no encontrado")

    tamano_actual = ruta_pdf.stat().st_size
    doc = fitz.open(str(ruta_pdf))
    num_paginas = len(doc)
    total_imagenes = 0
    tamano_imagenes = 0
    xrefs_vistos: set = set()
    for pag in doc:
        for info in pag.get_images(full=True):
            xref = info[0]
            if xref in xrefs_vistos:
                continue
            xrefs_vistos.add(xref)
            try:
                img_data = doc.extract_image(xref)
                if img_data:
                    total_imagenes += 1
                    tamano_imagenes += len(img_data.get('image', b''))
            except Exception:
                pass
    doc.close()

    pct = round(tamano_imagenes / tamano_actual * 100, 1) if tamano_actual > 0 else 0
    return {
        'tamano_actual': tamano_actual,
        'tamano_actual_texto': file_manager.formatear_tamano(tamano_actual),
        'num_paginas': num_paginas,
        'total_imagenes': total_imagenes,
        'porcentaje_imagenes': pct,
        'estimaciones': {
            'baja':  {'tamano': int(tamano_actual * 0.7), 'tamano_texto': file_manager.formatear_tamano(int(tamano_actual * 0.7)), 'reduccion': 30},
            'media': {'tamano': int(tamano_actual * 0.5), 'tamano_texto': file_manager.formatear_tamano(int(tamano_actual * 0.5)), 'reduccion': 50},
            'alta':  {'tamano': int(tamano_actual * 0.3), 'tamano_texto': file_manager.formatear_tamano(int(tamano_actual * 0.3)), 'reduccion': 70},
        }
    }


# ─── Procesador principal ────────────────────────────────────────────────────

def procesar_compress(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")
    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo físico no encontrado")

    nombre_original = archivo['nombre_original']
    job_manager.actualizar_progreso(trabajo_id, 2, "Iniciando compresión")

    ruta_comp, tam_orig, tam_final = comprimir_pdf(ruta_pdf, parametros, trabajo_id, nombre_original)

    reduccion = (tam_orig - tam_final) / tam_orig * 100 if tam_orig > 0 else 0

    return {
        'ruta_resultado': str(ruta_comp),
        'mensaje': f'{file_manager.formatear_tamano(tam_orig)} → {file_manager.formatear_tamano(tam_final)} ({reduccion:.1f}% reducción)',
        'tamano_original': tam_orig,
        'tamano_final': tam_final,
        'reduccion_pct': round(reduccion, 1),
    }


job_manager.registrar_procesador('compress', procesar_compress)
