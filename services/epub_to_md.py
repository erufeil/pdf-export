# -*- coding: utf-8 -*-
"""
Servicio de conversion EPUB a Markdown para PDFexport (Etapa 40).
Extrae capitulos del EPUB y los convierte a Markdown usando BeautifulSoup + markdownify.
"""

import re
import zipfile
import logging
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from bs4 import BeautifulSoup
import markdownify as md_lib

import config
import models
from utils import job_manager

logger = logging.getLogger(__name__)


def _leer_entrada(zf: zipfile.ZipFile, path: str) -> bytes:
    """Lee una entrada del ZIP con fallback case-insensitive."""
    path = path.replace('\\', '/').lstrip('/')
    nombres = zf.namelist()
    if path in nombres:
        return zf.read(path)
    path_low = path.lower()
    for n in nombres:
        if n.lower() == path_low:
            return zf.read(n)
    raise KeyError(f"No encontrado en EPUB: {path}")


def _obtener_opf_path(zf: zipfile.ZipFile) -> tuple:
    """Lee META-INF/container.xml y retorna (opf_path, opf_dir)."""
    xml = _leer_entrada(zf, 'META-INF/container.xml')
    soup = BeautifulSoup(xml, 'lxml-xml')
    rootfile = soup.find('rootfile')
    if not rootfile:
        raise ValueError("EPUB inválido: container.xml sin <rootfile>")
    opf_path = rootfile.get('full-path', '')
    opf_dir = str(PurePosixPath(opf_path).parent)
    if opf_dir == '.':
        opf_dir = ''
    return opf_path, opf_dir


def _find_text(soup, *nombres) -> str:
    """Busca el texto de la primera etiqueta que coincida con alguno de los nombres."""
    for nombre in nombres:
        tag = soup.find(nombre)
        if tag:
            t = tag.get_text(strip=True)
            if t:
                return t
    return ''


def _extraer_meta(opf_soup) -> dict:
    """Extrae titulo, autores, idioma, editorial y fecha del OPF."""
    meta = {}
    titulo = _find_text(opf_soup, 'dc:title', 'title')
    if titulo:
        meta['titulo'] = titulo

    autores = opf_soup.find_all('dc:creator') or opf_soup.find_all('creator')
    if autores:
        meta['autores'] = [a.get_text(strip=True) for a in autores if a.get_text(strip=True)]

    for campo, tags in [
        ('idioma',    ['dc:language', 'language']),
        ('editorial', ['dc:publisher', 'publisher']),
        ('fecha',     ['dc:date', 'date']),
    ]:
        v = _find_text(opf_soup, *tags)
        if v:
            meta[campo] = v

    return meta


def _extraer_spine(opf_soup, opf_dir: str) -> list:
    """Retorna lista de rutas internas del ZIP en orden del spine."""
    # Construir manifest: id → {href, tipo}
    manifest = {}
    for item in opf_soup.find_all('item'):
        iid  = item.get('id', '')
        href = item.get('href', '')
        tipo = item.get('media-type', '')
        if iid and href:
            manifest[iid] = {'href': href, 'tipo': tipo}

    rutas = []
    spine = opf_soup.find('spine')
    if not spine:
        return rutas

    for itemref in spine.find_all('itemref'):
        idref = itemref.get('idref', '')
        if idref not in manifest:
            continue
        item = manifest[idref]
        if 'html' not in item['tipo'] and 'xhtml' not in item['tipo']:
            continue
        # Resolver ruta relativa al directorio OPF y decodificar URL encoding
        href = unquote(item['href']).split('#')[0]
        if not href:
            continue
        ruta = f"{opf_dir}/{href}" if opf_dir else href
        rutas.append(ruta)

    return rutas


def _html_a_md(contenido: bytes) -> str:
    """Convierte XHTML de un capitulo EPUB a Markdown limpio."""
    try:
        soup = BeautifulSoup(contenido, 'lxml')
    except Exception:
        soup = BeautifulSoup(contenido, 'html.parser')

    # Eliminar elementos no textuales
    for tag in soup(['script', 'style', 'head', 'nav', 'aside',
                     'figure', 'figcaption', 'img', 'svg']):
        tag.decompose()

    body = soup.find('body')
    html_limpio = str(body) if body else str(soup)

    # Convertir a Markdown; strip=['a'] mantiene el texto de los links pero quita las URLs
    texto_md = md_lib.markdownify(
        html_limpio,
        heading_style='ATX',
        bullets='-',
        strip=['a'],
    )

    texto_md = re.sub(r'\n{3,}', '\n\n', texto_md)
    return texto_md.strip()


def _encabezado_meta(meta: dict, nombre_base: str) -> str:
    """Genera bloque de metadatos en Markdown."""
    titulo = meta.get('titulo', nombre_base)
    lineas = [f'# {titulo}', '']
    if 'autores' in meta:
        lineas.append('**Autores:** ' + ', '.join(meta['autores']) + '  ')
    if 'idioma' in meta:
        lineas.append(f"**Idioma:** {meta['idioma']}  ")
    if 'editorial' in meta:
        lineas.append(f"**Editorial:** {meta['editorial']}  ")
    if 'fecha' in meta:
        lineas.append(f"**Fecha:** {meta['fecha']}  ")
    return '\n'.join(lineas)


def procesar_epub_to_md(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    """
    Procesador principal registrado en job_manager como 'epub-to-md'.
    Extrae todos los capitulos del EPUB y los une en un unico .md.
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta = Path(archivo['ruta_archivo'])
    if not ruta.exists():
        raise ValueError("Archivo físico no encontrado")

    nombre_original = archivo['nombre_original']
    nombre_base = Path(nombre_original).stem

    job_manager.actualizar_progreso(trabajo_id, 5, "Abriendo EPUB")

    try:
        with zipfile.ZipFile(str(ruta), 'r') as zf:
            job_manager.actualizar_progreso(trabajo_id, 10, "Leyendo estructura del EPUB")
            opf_path, opf_dir = _obtener_opf_path(zf)

            opf_contenido = _leer_entrada(zf, opf_path)
            opf_soup = BeautifulSoup(opf_contenido, 'lxml-xml')

            meta = _extraer_meta(opf_soup)
            spine_rutas = _extraer_spine(opf_soup, opf_dir)

            if not spine_rutas:
                raise ValueError("El EPUB no tiene capítulos en el spine")

            encabezado = _encabezado_meta(meta, nombre_base)
            partes = [encabezado]
            num_caps = len(spine_rutas)

            for i, ruta_cap in enumerate(spine_rutas):
                progreso = 15 + int((i + 1) / num_caps * 65)
                job_manager.actualizar_progreso(trabajo_id, progreso, f"Capítulo {i+1}/{num_caps}")
                try:
                    contenido = _leer_entrada(zf, ruta_cap)
                    texto = _html_a_md(contenido)
                    if texto:
                        partes.append(texto)
                except Exception as e:
                    logger.warning(f"Error convirtiendo capítulo {ruta_cap}: {e}")

    except ValueError:
        raise
    except zipfile.BadZipFile:
        raise ValueError("El archivo no es un EPUB válido (ZIP corrupto)")
    except Exception as e:
        raise ValueError(f"Error procesando EPUB: {e}")

    if len(partes) <= 1:
        raise ValueError("No se pudo extraer contenido del EPUB")

    contenido_md = '\n\n---\n\n'.join(partes)

    job_manager.actualizar_progreso(trabajo_id, 85, "Guardando archivo")

    ruta_md = config.OUTPUT_FOLDER / f"{trabajo_id}_{nombre_base}.md"
    with open(ruta_md, 'w', encoding='utf-8') as f:
        f.write(contenido_md)

    num_caps_ok = len(partes) - 1
    num_chars   = len(contenido_md)
    return {
        'ruta_resultado': str(ruta_md),
        'mensaje': f'Markdown generado: {num_caps_ok} capítulo(s), {num_chars} caracteres'
    }


job_manager.registrar_procesador('epub-to-md', procesar_epub_to_md)
