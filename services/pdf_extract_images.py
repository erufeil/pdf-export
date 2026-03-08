# -*- coding: utf-8 -*-
"""
Servicio de extraccion de imagenes de PDF para PDFexport.
Extrae las imagenes incrustadas en un documento PDF.

Metodo de deteccion doble:
  A) page.get_images(full=True)  -> imagenes directas en recursos de pagina
  B) Escaneo de tabla xref       -> imagenes en XObjects Form y otros contenedores
     que el metodo A pierde en PDFs generados por Acrobat, InDesign, LibreOffice, etc.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple
from io import BytesIO

import fitz  # PyMuPDF
from PIL import Image

import config
import models
from utils import file_manager, job_manager

logger = logging.getLogger(__name__)


def _recolectar_xrefs_imagenes(doc: fitz.Document) -> set:
    """
    Recolecta todos los xrefs de objetos imagen del documento usando dos metodos:
      A) Iteracion por paginas con get_images(full=True)
      B) Escaneo directo de la tabla xref del PDF

    El metodo B captura imagenes embebidas en Form XObjects y otros contenedores
    que el metodo A no ve en muchos PDFs del mundo real.

    Los xrefs de SMask (mascaras de transparencia/alpha) se excluyen porque
    son canales alpha de otras imagenes, no imagenes independientes.

    Returns:
        Set de xrefs enteros que corresponden a streams de imagen real.
    """
    xrefs = set()
    smask_xrefs = set()   # xrefs que son mascaras alpha — NO extraer

    # Metodo A: por paginas (rapido, cubre la mayoria de casos basicos)
    # img_info tuple: (xref, smask, width, height, bpc, colorspace, alt_cs, name, filter, ref)
    for pagina in doc:
        for img_info in pagina.get_images(full=True):
            xrefs.add(img_info[0])
            if img_info[1] != 0:          # smask xref != 0 significa que tiene mascara
                smask_xrefs.add(img_info[1])

    # Metodo B: escaneo de tabla xref usando xref_object (sin extract_image)
    # xref_object() lee solo el diccionario del objeto PDF (rapido, sin descomprimir)
    # y es seguro llamarlo en cualquier xref sin afectar el estado del documento.
    try:
        num_xrefs = doc.xref_length()
    except Exception:
        num_xrefs = 0

    for xref in range(1, num_xrefs):
        if xref in xrefs or xref in smask_xrefs:
            continue
        try:
            if not doc.xref_is_stream(xref):
                continue
            # Verificar /Subtype /Image en el diccionario del objeto
            obj_str = doc.xref_object(xref)
            if '/Subtype /Image' not in obj_str and '/Subtype/Image' not in obj_str:
                continue
            xrefs.add(xref)
            # Extraer xref del SMask si existe: "/SMask 25 0 R"
            m = re.search(r'/SMask\s+(\d+)\s+0\s+R', obj_str)
            if m:
                smask_xrefs.add(int(m.group(1)))
        except Exception:
            continue

    # Quitar smasks que pudieron haberse colado antes de identificarlos
    xrefs -= smask_xrefs

    logger.debug(f"xrefs imagen: {len(xrefs)} reales, {len(smask_xrefs)} SMasks excluidos")
    return xrefs


def _extraer_imagen_xref(doc: fitz.Document, xref: int) -> dict | None:
    """
    Extrae una imagen de un xref con dos intentos:
      1) extract_image (preserva formato original: jpeg, png, jp2, etc.)
         Si reporta dimensiones 0x0, las corrige con PIL.
      2) Pixmap (fallback): convierte al vuelo a PNG cualquier formato que
         extract_image no puede manejar (JBIG2, CCITT, 1-bit, etc.).

    Returns dict con keys: image(bytes), ext(str), width(int), height(int)
            o None si ambos metodos fallan.
    """
    # Intento 1: extract_image — preserva formato original
    try:
        imagen = doc.extract_image(xref)
        if imagen and imagen.get('image'):
            ancho = imagen.get('width', 0)
            alto = imagen.get('height', 0)
            # Dimensiones invalidas (0x0): corregir con PIL
            if ancho == 0 or alto == 0:
                try:
                    pil_img = Image.open(BytesIO(imagen['image']))
                    imagen['width'], imagen['height'] = pil_img.size
                except Exception:
                    pass
            return imagen
    except Exception:
        pass

    # Intento 2: Pixmap — funciona con JBIG2, CCITT, 1-bit y otros formatos exoticos
    try:
        pix = fitz.Pixmap(doc, xref)
        if pix.width > 0 and pix.height > 0:
            return {
                'image': pix.tobytes('png'),
                'ext': 'png',
                'width': pix.width,
                'height': pix.height
            }
    except Exception:
        pass

    return None


def contar_imagenes_pdf(ruta_pdf: Path) -> int:
    """Cuenta el numero de imagenes en un PDF usando deteccion doble."""
    doc = fitz.open(str(ruta_pdf))
    xrefs = _recolectar_xrefs_imagenes(doc)
    doc.close()
    return len(xrefs)


def extraer_imagenes_pdf(
    ruta_pdf: Path,
    opciones: Dict,
    trabajo_id: str,
    nombre_original: str = None
) -> List[Tuple[Path, str]]:
    """
    Extrae todas las imagenes de un PDF usando deteccion doble (paginas + xref scan).

    Args:
        ruta_pdf: Ruta al archivo PDF
        opciones: {formato_salida, tamano_minimo_px, imagenes_seleccionadas}
        trabajo_id: ID del trabajo para actualizar progreso
        nombre_original: Nombre original del archivo (con extension)

    Returns:
        Lista de tuplas (ruta_imagen_guardada, nombre_para_el_zip)
    """
    formato_salida = opciones.get('formato_salida', 'original')
    tamano_minimo = opciones.get('tamano_minimo_px', 50)

    doc = fitz.open(str(ruta_pdf))
    nombre_base = nombre_original if nombre_original else ruta_pdf.name

    job_manager.actualizar_progreso(trabajo_id, 5, "Buscando imagenes en el documento")

    # Recolectar xrefs por ambos metodos
    xrefs_imagenes = _recolectar_xrefs_imagenes(doc)
    total_candidatos = len(xrefs_imagenes)

    logger.info(f"Imagenes detectadas en '{nombre_base}': {total_candidatos} candidatos")

    if total_candidatos == 0:
        doc.close()
        return []

    imagenes_extraidas = []
    contador_imagen = 0   # imagenes que pasan el filtro de tamano

    for i, xref in enumerate(sorted(xrefs_imagenes)):
        progreso = 10 + int((i / total_candidatos) * 80)
        job_manager.actualizar_progreso(
            trabajo_id, progreso,
            f"Procesando imagen {i + 1} de {total_candidatos}"
        )

        try:
            imagen_base = _extraer_imagen_xref(doc, xref)

            if not imagen_base:
                logger.warning(f"xref {xref}: no se pudo extraer (extract_image ni Pixmap)")
                continue

            img_bytes = imagen_base['image']
            ext_original = imagen_base['ext']
            ancho = imagen_base.get('width', 0)
            alto = imagen_base.get('height', 0)

            # Filtrar por tamano minimo (solo si el filtro esta activo)
            if tamano_minimo > 0 and (ancho < tamano_minimo or alto < tamano_minimo):
                logger.debug(f"xref {xref}: imagen demasiado pequena ({ancho}x{alto}px), omitida")
                continue

            contador_imagen += 1

            # Determinar extension de salida
            if formato_salida == 'png':
                ext = 'png'
            elif formato_salida == 'jpg':
                ext = 'jpg'
            else:
                ext = ext_original  # 'original': conservar formato

            # Nombre del archivo segun convencion del proyecto
            padding = len(str(total_candidatos))
            nombre_imagen = str(contador_imagen).zfill(padding)
            nombre_archivo = f"{nombre_base} - imagen {nombre_imagen}.{ext}"
            ruta_imagen = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_archivo}"

            # Guardar imagen, convirtiendo formato si se solicita
            if formato_salida != 'original' and ext != ext_original:
                img_pil = Image.open(BytesIO(img_bytes))
                if ext == 'jpg' and img_pil.mode in ('RGBA', 'LA', 'P'):
                    img_pil = img_pil.convert('RGB')
                if ext == 'jpg':
                    img_pil.save(str(ruta_imagen), 'JPEG', quality=85)
                else:
                    img_pil.save(str(ruta_imagen), 'PNG')
            else:
                with open(ruta_imagen, 'wb') as f:
                    f.write(img_bytes)

            imagenes_extraidas.append((ruta_imagen, nombre_archivo))
            logger.info(f"Imagen extraida: {nombre_archivo} ({ancho}x{alto}px, {ext_original})")

        except Exception as e:
            logger.warning(f"Error extrayendo xref {xref}: {e}")
            continue

    doc.close()
    logger.info(f"Total extraidas: {len(imagenes_extraidas)} de {total_candidatos} candidatos")
    return imagenes_extraidas


def procesar_extract_images(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal de extraccion de imagenes.
    Registrado en job_manager como 'extract-images'.
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo fisico no encontrado")

    nombre_original = archivo['nombre_original']
    job_manager.actualizar_progreso(trabajo_id, 2, "Iniciando extraccion de imagenes")

    imagenes = extraer_imagenes_pdf(ruta_pdf, parametros, trabajo_id, nombre_original)

    if not imagenes:
        raise ValueError("No se encontraron imagenes en el documento (o todas son demasiado pequenas)")

    job_manager.actualizar_progreso(trabajo_id, 92, "Comprimiendo archivos")

    nombre_base = Path(archivo['nombre_original']).stem
    nombre_zip = f"{trabajo_id}_{nombre_base}_imagenes.zip"

    archivos_para_zip = [(str(ruta), nombre) for ruta, nombre in imagenes]
    ruta_zip = file_manager.crear_zip(archivos_para_zip, nombre_zip)

    # Limpiar temporales
    for ruta, _ in imagenes:
        if ruta.exists():
            ruta.unlink()

    return {
        'ruta_resultado': str(ruta_zip),
        'mensaje': f'{len(imagenes)} imagenes extraidas'
    }


def obtener_conteo_imagenes(archivo_id: str) -> dict:
    """
    Obtiene conteo y detalles de imagenes en un PDF.
    Usa deteccion doble para el mismo resultado que la extraccion real.
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])
    if not ruta_pdf.exists():
        raise ValueError("Archivo fisico no encontrado")

    doc = fitz.open(str(ruta_pdf))
    xrefs_imagenes = _recolectar_xrefs_imagenes(doc)

    imagenes = []
    contador = 0

    for xref in sorted(xrefs_imagenes):
        try:
            imagen_base = _extraer_imagen_xref(doc, xref)
            if not imagen_base:
                logger.warning(f"xref {xref}: no se pudo extraer para conteo")
                continue
            contador += 1
            imagenes.append({
                'id': str(contador),
                'xref': xref,
                'ancho': imagen_base.get('width', 0),
                'alto': imagen_base.get('height', 0),
                'formato': imagen_base.get('ext', 'unknown'),
                'tamano': len(imagen_base.get('image', b''))
            })
            logger.debug(f"xref {xref}: {imagen_base.get('width')}x{imagen_base.get('height')} {imagen_base.get('ext')} ({len(imagen_base['image'])} bytes)")
        except Exception as e:
            logger.warning(f"xref {xref}: excepcion en conteo: {e}")

    doc.close()

    return {
        'total_imagenes': len(imagenes),
        'imagenes': imagenes
    }


# Registrar el procesador en el job_manager
job_manager.registrar_procesador('extract-images', procesar_extract_images)
