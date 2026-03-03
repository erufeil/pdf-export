# -*- coding: utf-8 -*-
"""
Servicio IMG a PDF para PDFexport.
Convierte multiples imagenes de cualquier formato en un unico archivo PDF.
Cada imagen ocupa una pagina del PDF resultante.
"""

import io
import logging
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image as PILImage

import config
import models
from utils import job_manager

logger = logging.getLogger(__name__)

# Extensiones de imagen soportadas
EXTENSIONES_IMAGEN = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'tif', 'webp'}

# Tamanos de pagina en puntos PDF (1pt = 1/72 pulgada)
TAMANOS_PAGINA = {
    'A4':      (595, 842),
    'A4H':     (842, 595),    # A4 apaisado
    'A3':      (842, 1191),
    'A3H':     (1191, 842),   # A3 apaisado
    'letter':  (612, 792),
    'letterH': (792, 612),    # Letter apaisado
}


def imagen_a_pagina(doc_resultado: fitz.Document, ruta_img: Path, tamano_pagina: str, margen: int) -> None:
    """
    Abre una imagen y la agrega como nueva pagina al documento PDF.

    Args:
        doc_resultado: Documento fitz destino (se modifica en lugar)
        ruta_img: Ruta al archivo de imagen
        tamano_pagina: 'natural' o clave de TAMANOS_PAGINA ('A4', 'A3', 'letter', etc.)
        margen: Margen en puntos PDF (0, 15 o 30)
    """
    # Abrir imagen con Pillow para normalizar formato y modo de color
    with PILImage.open(str(ruta_img)) as img_pil:
        # Convertir paleta a RGBA para preservar transparencia si la tiene
        if img_pil.mode == 'P':
            img_pil = img_pil.convert('RGBA')

        # Compositar transparencia sobre fondo blanco
        if img_pil.mode in ('RGBA', 'LA'):
            fondo = PILImage.new('RGB', img_pil.size, (255, 255, 255))
            fondo.paste(img_pil, mask=img_pil.split()[-1])
            img_pil = fondo
        elif img_pil.mode != 'RGB':
            img_pil = img_pil.convert('RGB')

        ancho_img = img_pil.width
        alto_img = img_pil.height

        # Serializar imagen normalizada a bytes PNG para insertar en fitz
        buf = io.BytesIO()
        img_pil.save(buf, format='PNG')
        buf.seek(0)
        img_bytes = buf.read()

    # Determinar tamano y posicion de la pagina PDF
    if tamano_pagina == 'natural':
        # La pagina tiene exactamente las dimensiones de la imagen en puntos
        pag = doc_resultado.new_page(width=ancho_img, height=alto_img)
        rect_imagen = fitz.Rect(0, 0, ancho_img, alto_img)
    else:
        ancho_pt, alto_pt = TAMANOS_PAGINA.get(tamano_pagina, (595, 842))
        pag = doc_resultado.new_page(width=ancho_pt, height=alto_pt)

        # Escalar imagen para que quepa en el area util manteniendo proporcion
        area_w = ancho_pt - 2 * margen
        area_h = alto_pt - 2 * margen
        escala = min(area_w / ancho_img, area_h / alto_img)

        img_w = ancho_img * escala
        img_h = alto_img * escala

        # Centrar imagen en la pagina
        x0 = (ancho_pt - img_w) / 2
        y0 = (alto_pt - img_h) / 2
        rect_imagen = fitz.Rect(x0, y0, x0 + img_w, y0 + img_h)

    pag.insert_image(rect_imagen, stream=img_bytes)


def procesar_img_to_1pdf(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal registrado en job_manager como 'img-to-1pdf'.
    Toma una lista de imagenes ya subidas y las combina en un unico PDF.

    Args:
        trabajo_id: ID del trabajo en curso
        archivo_id: No se usa (el servicio trabaja con lista de imagenes)
        parametros: {
            'archivos': [{'file_id': str, 'orden': int}, ...],
            'opciones': {
                'tamano_pagina': str,   # 'natural'|'A4'|'A4H'|'A3'|'letter'
                'margen': int           # 0, 15 o 30 puntos
            }
        }

    Returns:
        Dict con 'ruta_resultado' y 'mensaje'
    """
    lista_archivos = parametros.get('archivos', [])
    opciones = parametros.get('opciones', {})
    tamano_pagina = opciones.get('tamano_pagina', 'A4')
    margen = int(opciones.get('margen', 0))

    if not lista_archivos:
        raise ValueError("Se requiere al menos una imagen para crear el PDF")

    # Ordenar por el campo 'orden'
    lista_ordenada = sorted(lista_archivos, key=lambda x: x.get('orden', 0))
    total = len(lista_ordenada)

    job_manager.actualizar_progreso(trabajo_id, 5, "Verificando imagenes")

    # Resolver info de cada archivo desde la BD
    archivos_info = []
    for item in lista_ordenada:
        archivo = models.obtener_archivo(item['file_id'])
        if not archivo:
            raise ValueError(f"Archivo no encontrado: {item['file_id']}")
        archivos_info.append(archivo)

    logger.info(f"Convirtiendo {total} imagen(es) a PDF | tamano={tamano_pagina} margen={margen}pt")

    # Crear documento PDF resultado
    doc_resultado = fitz.open()

    for i, archivo in enumerate(archivos_info):
        progreso = int(10 + (i / total) * 80)
        job_manager.actualizar_progreso(
            trabajo_id, progreso,
            f"Procesando imagen {i + 1} de {total}: {archivo['nombre_original']}"
        )

        ruta_img = Path(archivo['ruta_archivo'])
        if not ruta_img.exists():
            raise FileNotFoundError(f"Imagen no encontrada en disco: {ruta_img.name}")

        try:
            imagen_a_pagina(doc_resultado, ruta_img, tamano_pagina, margen)
            logger.info(f"Imagen agregada [{i + 1}/{total}]: {archivo['nombre_original']}")
        except Exception as e:
            logger.error(f"Error procesando '{archivo['nombre_original']}': {e}")
            raise ValueError(f"No se pudo procesar la imagen '{archivo['nombre_original']}': {e}")

    job_manager.actualizar_progreso(trabajo_id, 90, "Guardando PDF")

    # Guardar PDF directamente en outputs (sin comprimir ni empaquetar en ZIP)
    nombre_pdf = f"{trabajo_id}_imagenes.pdf"
    ruta_pdf = config.OUTPUT_FOLDER / nombre_pdf
    doc_resultado.save(str(ruta_pdf))
    doc_resultado.close()

    logger.info(f"PDF guardado: {ruta_pdf}")

    return {
        'ruta_resultado': str(ruta_pdf),
        'mensaje': f'{total} imagen(es) convertida(s) a PDF correctamente'
    }


# Registrar procesador en el job_manager
job_manager.registrar_procesador('img-to-1pdf', procesar_img_to_1pdf)
