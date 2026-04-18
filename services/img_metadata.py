# -*- coding: utf-8 -*-
"""
Servicio Etapa 28: Extraer metadatos forenses completos de una imagen.
Extrae: propiedades técnicas, EXIF (cámara, captura, GPS), IPTC/XMP via Tika,
historial de edición Photoshop y análisis de colores dominantes (determinista).
"""

import hashlib
import logging
from collections import Counter
from pathlib import Path

from PIL import Image, ExifTags, ImageStat

import config
import models

logger = logging.getLogger(__name__)

# MIME types por extensión
MIME_POR_EXTENSION = {
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png':  'image/png',
    '.tiff': 'image/tiff',
    '.tif':  'image/tiff',
    '.bmp':  'image/bmp',
    '.gif':  'image/gif',
    '.webp': 'image/webp',
}

# IFD pointers
_EXIF_IFD = 0x8769
_GPS_IFD  = 0x8825

# Tablas de decodificación EXIF
_METERING_MODE = {
    0: 'Desconocido', 1: 'Promedio', 2: 'Ponderado al centro',
    3: 'Puntual', 4: 'Multi-puntual', 5: 'Evaluativo/Patron', 6: 'Parcial', 255: 'Otro',
}
_EXPOSURE_PROG = {
    0: 'No definido', 1: 'Manual', 2: 'Programa normal',
    3: 'Prioridad apertura', 4: 'Prioridad obturador',
    5: 'Creativo (profundidad)', 6: 'Accion (velocidad)',
    7: 'Modo retrato', 8: 'Modo paisaje',
}
_EXPOSURE_MODE = {0: 'Auto', 1: 'Manual', 2: 'Auto bracket'}
_WHITE_BALANCE = {0: 'Auto', 1: 'Manual'}
_SCENE_CAPTURE = {0: 'Estandar', 1: 'Paisaje', 2: 'Retrato', 3: 'Nocturno'}
_FLASH_DESC = {
    0: 'No disparo', 1: 'Disparo', 5: 'Disparo (sin retorno)',
    7: 'Disparo (con retorno)', 9: 'Disparo forzado',
    16: 'No disparo (flash apagado)', 24: 'No disparo (sin flash)',
    25: 'Disparo (reduccion ojos rojos)', 32: 'No disparo (modo auto)',
    65: 'Disparo (modo auto)', 89: 'Disparo (relleno)',
}
_COLOR_SPACE = {1: 'sRGB', 65535: 'No calibrado / Adobe RGB'}
_ADJUSTMENTS  = {0: 'Normal', 1: 'Bajo', 2: 'Alto'}
_ORIENTATION  = {
    1: 'Normal (0)', 2: 'Espejado horizontal', 3: 'Rotado 180',
    4: 'Espejado vertical', 5: 'Espejado H + Rotado 270',
    6: 'Rotado 90 horario', 7: 'Espejado H + Rotado 90', 8: 'Rotado 270 horario',
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _calcular_hashes(ruta: Path) -> dict:
    """MD5 y SHA-256 del archivo en disco."""
    md5    = hashlib.md5()
    sha256 = hashlib.sha256()
    with open(ruta, 'rb') as f:
        for bloque in iter(lambda: f.read(65536), b''):
            md5.update(bloque)
            sha256.update(bloque)
    return {'sha256': sha256.hexdigest().upper(), 'md5': md5.hexdigest().upper()}


def _nombre_icc(icc_bytes: bytes) -> str:
    """Extrae el nombre del perfil ICC desde los bytes del perfil."""
    try:
        nombre = icc_bytes[8:40].decode('ascii', errors='replace').strip('\x00').strip()
        if not nombre:
            nombre = icc_bytes[128:192].decode('ascii', errors='replace').strip('\x00').strip()
        return nombre or 'Presente'
    except Exception:
        return 'Presente'


def _safe(val) -> str:
    """Convierte un valor EXIF a string seguro."""
    if val is None:
        return ''
    try:
        if hasattr(val, 'numerator') and hasattr(val, 'denominator'):
            return str(float(val))
        if isinstance(val, tuple) and len(val) == 2 and isinstance(val[0], int):
            return str(val[0] / val[1]) if val[1] != 0 else str(val[0])
        return str(val)
    except Exception:
        return str(val)


def _exposure_time_str(val) -> str:
    try:
        if hasattr(val, 'numerator'):
            n, d = int(val.numerator), int(val.denominator)
        elif isinstance(val, tuple):
            n, d = int(val[0]), int(val[1])
        else:
            return _safe(val)
        if d == 0:
            return str(n)
        if n == 1:
            return f'1/{d} s'
        return f'{n}/{d} s'
    except Exception:
        return _safe(val)


def _fnumber_str(val) -> str:
    try:
        return f'f/{float(val):.1f}'
    except Exception:
        return _safe(val)


# ─── Extracción técnica (Pillow) ──────────────────────────────────────────────

def _extraer_tecnico(img: Image.Image) -> dict:
    info = img.info

    dpi_x = dpi_y = None
    dpi = info.get('dpi')
    if dpi:
        dpi_x, dpi_y = round(dpi[0], 1), round(dpi[1], 1)

    icc_nombre = ''
    if 'icc_profile' in info:
        icc_nombre = _nombre_icc(info['icc_profile'])

    frames = 1
    try:
        frames = getattr(img, 'n_frames', 1)
    except Exception:
        pass

    transparencia = (img.mode in ('RGBA', 'LA', 'PA')) or ('transparency' in info)

    bits_map = {
        '1': 1, 'L': 8, 'P': 8, 'RGB': 8, 'RGBA': 8, 'CMYK': 8,
        'YCbCr': 8, 'LAB': 8, 'HSV': 8, 'I': 32, 'F': 32, 'I;16': 16,
    }
    bits = bits_map.get(img.mode, 8)

    return {
        'formato':       img.format or 'Desconocido',
        'modo':          img.mode,
        'ancho':         img.width,
        'alto':          img.height,
        'megapixeles':   round(img.width * img.height / 1_000_000, 2),
        'dpi_x':         dpi_x,
        'dpi_y':         dpi_y,
        'bits_muestra':  bits,
        'canales':       len(img.getbands()),
        'frames':        frames,
        'transparencia': transparencia,
        'icc_perfil':    icc_nombre,
        'progresivo':    bool(info.get('progressive', False)),
        'compresion':    str(info.get('compression', '')),
    }


# ─── Extracción EXIF (Pillow getexif) ────────────────────────────────────────

def _extraer_exif(img: Image.Image) -> tuple:
    """Retorna (ifd0_dict, exif_ifd_raw, gps_ifd_raw) con nombres de tags."""
    ifd0_dict    = {}
    exif_ifd_raw = {}
    gps_ifd_raw  = {}
    try:
        exif = img.getexif()
        if not exif:
            return ifd0_dict, exif_ifd_raw, gps_ifd_raw

        tags = ExifTags.TAGS
        for tag_id, val in exif.items():
            nombre = tags.get(tag_id, f'Tag_{tag_id}')
            if nombre in ('ExifOffset', 'GPSInfo'):
                continue
            ifd0_dict[nombre] = _safe(val)

        exif_sub = exif.get_ifd(_EXIF_IFD)
        for tag_id, val in exif_sub.items():
            nombre = tags.get(tag_id, f'Tag_{tag_id}')
            exif_ifd_raw[nombre] = val  # raw para formateo posterior

        gps_sub = exif.get_ifd(_GPS_IFD)
        gps_tags = ExifTags.GPSTAGS
        for tag_id, val in gps_sub.items():
            nombre = gps_tags.get(tag_id, f'GPS_{tag_id}')
            gps_ifd_raw[nombre] = val

    except Exception as e:
        logger.debug(f'Error EXIF: {e}')

    return ifd0_dict, exif_ifd_raw, gps_ifd_raw


def _formatear_exif_ifd(raw: dict) -> dict:
    """Convierte raw ExifIFD a strings legibles para el usuario."""
    r = {}

    def g(k):
        return raw.get(k)

    if g('DateTimeOriginal'):     r['fecha_original']      = str(g('DateTimeOriginal'))
    if g('DateTimeDigitized'):    r['fecha_digitalizada']  = str(g('DateTimeDigitized'))
    if g('SubSecTimeOriginal'):   r['subsegundos']         = str(g('SubSecTimeOriginal'))
    if g('ExposureTime'):         r['exposicion']          = _exposure_time_str(g('ExposureTime'))
    if g('FNumber'):              r['apertura']            = _fnumber_str(g('FNumber'))
    if g('ISOSpeedRatings'):      r['iso']                 = str(g('ISOSpeedRatings'))
    if g('ExposureBiasValue') is not None:
        r['compensacion_ev']     = f'{float(g("ExposureBiasValue")):.2f} EV'
    if g('MeteringMode') is not None:
        r['modo_medicion']       = _METERING_MODE.get(g('MeteringMode'), str(g('MeteringMode')))
    if g('Flash') is not None:
        r['flash']               = _FLASH_DESC.get(g('Flash'), str(g('Flash')))
    if g('FocalLength'):          r['focal_mm']            = f'{float(g("FocalLength")):.1f} mm'
    if g('FocalLengthIn35mmFilm'): r['focal_35mm']         = f'{g("FocalLengthIn35mmFilm")} mm'
    if g('ExposureProgram') is not None:
        r['programa']            = _EXPOSURE_PROG.get(g('ExposureProgram'), str(g('ExposureProgram')))
    if g('ExposureMode') is not None:
        r['modo_exposicion']     = _EXPOSURE_MODE.get(g('ExposureMode'), str(g('ExposureMode')))
    if g('WhiteBalance') is not None:
        r['balance_blancos']     = _WHITE_BALANCE.get(g('WhiteBalance'), str(g('WhiteBalance')))
    if g('SceneCaptureType') is not None:
        r['tipo_escena']         = _SCENE_CAPTURE.get(g('SceneCaptureType'), str(g('SceneCaptureType')))
    if g('ColorSpace') is not None:
        r['espacio_color']       = _COLOR_SPACE.get(g('ColorSpace'), str(g('ColorSpace')))
    if g('Contrast') is not None:   r['contraste']   = _ADJUSTMENTS.get(g('Contrast'), str(g('Contrast')))
    if g('Saturation') is not None: r['saturacion']  = _ADJUSTMENTS.get(g('Saturation'), str(g('Saturation')))
    if g('Sharpness') is not None:  r['nitidez']     = _ADJUSTMENTS.get(g('Sharpness'), str(g('Sharpness')))
    if g('LensMake'):               r['lente_marca'] = str(g('LensMake'))
    if g('LensModel'):              r['lente_modelo'] = str(g('LensModel'))
    if g('BodySerialNumber'):       r['serial_cuerpo'] = str(g('BodySerialNumber'))
    if g('LensSerialNumber'):       r['serial_lente']  = str(g('LensSerialNumber'))
    if g('LensSpecification'):
        ls = g('LensSpecification')
        try:
            r['lente_especificacion'] = f'{float(ls[0]):.0f}-{float(ls[1]):.0f}mm f/{float(ls[2]):.1f}-{float(ls[3]):.1f}'
        except Exception:
            r['lente_especificacion'] = str(ls)

    return r


# ─── GPS ──────────────────────────────────────────────────────────────────────

def _gps_a_decimal(val, ref: str) -> float:
    """Convierte coordenada GPS (IFDRational o tupla) a decimal. Determinista."""
    try:
        d = float(val[0])
        m = float(val[1])
        s = float(val[2])
        dec = d + m / 60 + s / 3600
        return round(-dec if ref in ('S', 'W') else dec, 7)
    except Exception:
        return 0.0


def _decodificar_gps(gps_raw: dict) -> dict:
    if not gps_raw:
        return {}
    resultado = {}

    lat_val = gps_raw.get('GPSLatitude')
    lat_ref = str(gps_raw.get('GPSLatitudeRef', 'N'))
    lon_val = gps_raw.get('GPSLongitude')
    lon_ref = str(gps_raw.get('GPSLongitudeRef', 'E'))

    if lat_val and lon_val:
        lat = _gps_a_decimal(lat_val, lat_ref)
        lon = _gps_a_decimal(lon_val, lon_ref)
        resultado['latitud']  = lat
        resultado['longitud'] = lon
        resultado['link_osm'] = f'https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom=15'

    alt_val = gps_raw.get('GPSAltitude')
    if alt_val is not None:
        alt_m = round(float(alt_val), 1)
        bajo  = (gps_raw.get('GPSAltitudeRef', 0) == 1)
        resultado['altitud'] = f'{alt_m} m {"bajo" if bajo else "sobre"} el nivel del mar'

    spd = gps_raw.get('GPSSpeed')
    if spd is not None:
        ref_vel = {'K': 'km/h', 'M': 'mph', 'N': 'nudos'}.get(
            str(gps_raw.get('GPSSpeedRef', 'K')), 'km/h')
        resultado['velocidad'] = f'{float(spd):.1f} {ref_vel}'

    direccion = gps_raw.get('GPSImgDirection')
    if direccion is not None:
        ref_dir = gps_raw.get('GPSImgDirectionRef', 'M')
        label = 'Magnetico' if ref_dir == 'M' else 'Verdadero'
        resultado['direccion_camara'] = f'{float(direccion):.1f} {label}'

    if gps_raw.get('GPSDateStamp'):
        resultado['fecha_gps'] = str(gps_raw['GPSDateStamp'])
    if gps_raw.get('GPSTimeStamp'):
        ts = gps_raw['GPSTimeStamp']
        try:
            resultado['hora_gps'] = '{:02.0f}:{:02.0f}:{:02.0f} UTC'.format(
                float(ts[0]), float(ts[1]), float(ts[2]))
        except Exception:
            resultado['hora_gps'] = str(ts)
    if gps_raw.get('GPSSatellites'):
        resultado['satelites'] = str(gps_raw['GPSSatellites'])

    return resultado


# ─── Tika /meta ───────────────────────────────────────────────────────────────

def _extraer_tika(ruta: Path, mime_type: str) -> dict:
    url = config.TIKA_URL
    if not url:
        return {}
    import requests
    try:
        headers = {'Content-Type': mime_type, 'Accept': 'application/json'}
        with open(ruta, 'rb') as f:
            r = requests.put(f'{url}/meta', headers=headers, data=f, timeout=60)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.debug(f'Tika /meta: {e}')
    return {}


def _parsear_iptc_xmp(tika_dict: dict) -> tuple:
    """Separa tika_dict en (contenido, historial)."""
    contenido = {}
    historial = {}

    mapa_contenido = {
        'dc:title':                       'titulo',
        'dc:creator':                     'autor',
        'dc:description':                 'descripcion',
        'dc:subject':                     'palabras_clave',
        'dc:rights':                      'derechos',
        'photoshop:Credit':               'credito',
        'photoshop:City':                 'ciudad',
        'photoshop:Country':              'pais',
        'photoshop:State':                'estado_provincia',
        'photoshop:Category':             'categoria',
        'photoshop:ICCProfile':           'perfil_icc_ps',
        'photoshop:ColorMode':            'modo_color_ps',
        'Iptc4xmpCore:Location':          'ubicacion',
        'Iptc4xmpCore:IntellectualGenre': 'genero',
    }
    mapa_historial = {
        'xmp:CreatorTool':       'herramienta_creadora',
        'xmp:CreateDate':        'fecha_creacion_xmp',
        'xmp:ModifyDate':        'fecha_modificacion_xmp',
        'xmp:MetadataDate':      'fecha_metadatos_xmp',
        'xmpMM:DocumentID':      'document_id',
        'xmpMM:OriginalDocumentID': 'original_document_id',
        'xmpMM:InstanceID':      'instance_id',
        'xmpMM:History':         'historial_acciones',
        'xmpMM:DerivedFrom':     'derivado_de',
    }

    def _val_str(v):
        return ', '.join(str(x) for x in v) if isinstance(v, list) else str(v)

    for k, dest in mapa_contenido.items():
        v = tika_dict.get(k)
        if v:
            contenido[dest] = _val_str(v)

    for k, dest in mapa_historial.items():
        v = tika_dict.get(k)
        if v:
            historial[dest] = _val_str(v)

    doc_id  = historial.get('document_id', '').strip()
    inst_id = historial.get('instance_id', '').strip()
    historial['fue_editado'] = (doc_id != inst_id) if (doc_id and inst_id) else None

    return contenido, historial


# ─── Análisis de colores (determinista) ──────────────────────────────────────

def _analizar_colores(img: Image.Image) -> dict:
    """
    Colores dominantes via MEDIANCUT (determinista: misma imagen = mismo resultado).
    No usa random en ningún paso.
    """
    img_rgb = img.convert('RGB')
    small   = img_rgb.resize((100, 100), Image.Resampling.LANCZOS)

    n = 8
    quantized   = small.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    palette_raw = quantized.getpalette()
    frecuencias = Counter(quantized.getdata())
    total_px    = 100 * 100

    colores = []
    for idx, count in frecuencias.most_common(n):
        r = palette_raw[idx * 3]
        g = palette_raw[idx * 3 + 1]
        b = palette_raw[idx * 3 + 2]
        pct = round(count / total_px * 100, 1)
        colores.append({'hex': '#{:02X}{:02X}{:02X}'.format(r, g, b), 'r': r, 'g': g, 'b': b, 'pct': pct})

    stat    = ImageStat.Stat(img_rgb)
    prom_r, prom_g, prom_b = [round(x, 1) for x in stat.mean[:3]]
    std_r,  std_g,  std_b  = [round(x, 1) for x in stat.stddev[:3]]

    r_a, g_a, b_a = int(prom_r), int(prom_g), int(prom_b)
    hex_avg = '#{:02X}{:02X}{:02X}'.format(r_a, g_a, b_a)

    stat_grey = ImageStat.Stat(img_rgb.convert('L'))
    brillo    = round(stat_grey.mean[0], 1)

    return {
        'colores_dominantes': colores,
        'color_promedio': {'hex': hex_avg, 'r': r_a, 'g': g_a, 'b': b_a},
        'brillo': brillo,
        'brillo_desc': 'oscura' if brillo < 85 else ('clara' if brillo > 170 else 'media'),
        'prom_r': prom_r, 'prom_g': prom_g, 'prom_b': prom_b,
        'std_r':  std_r,  'std_g':  std_g,  'std_b':  std_b,
    }


# ─── Función principal ────────────────────────────────────────────────────────

def extraer_metadatos_imagen(archivo_id: str) -> dict:
    """
    Extrae todos los metadatos forenses de una imagen.
    Retorna dict con 10 bloques de información.
    """
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError('Archivo no encontrado')

    ruta   = Path(archivo['ruta_archivo'])
    nombre = archivo['nombre_original']
    ext    = Path(nombre).suffix.lower()
    mime   = MIME_POR_EXTENSION.get(ext, 'application/octet-stream')

    hashes = _calcular_hashes(ruta)

    img = Image.open(str(ruta))
    try:
        tecnico  = _extraer_tecnico(img)
        ifd0, exif_raw, gps_raw = _extraer_exif(img)

        # Bloque 3: cámara (subset del IFD0)
        campos_camara = ('Make', 'Model', 'Software', 'Artist', 'Copyright',
                         'ImageDescription', 'Orientation', 'DateTime',
                         'XResolution', 'YResolution', 'ResolutionUnit')
        exif_camara = {k: ifd0[k] for k in campos_camara if k in ifd0}
        if 'Orientation' in exif_camara:
            try:
                exif_camara['Orientation'] = _ORIENTATION.get(
                    int(exif_camara['Orientation']), exif_camara['Orientation'])
            except Exception:
                pass

        # Bloque 4+5: captura + lente/seriales
        exif_captura = _formatear_exif_ifd(exif_raw)

        # Bloque 6: GPS
        gps = _decodificar_gps(gps_raw)

        # Bloque 7+8: Tika
        tika_dict      = _extraer_tika(ruta, mime)
        tika_disponible = bool(tika_dict)
        contenido, historial = _parsear_iptc_xmp(tika_dict)

        # Bloque 10: raw Tika (excluye meta-campos internos)
        _excluir = {'Content-Type', 'Content-Length', 'resourceName',
                    'X-TIKA:Parsed-By', 'X-TIKA:parse_time_millis'}
        tika_raw = {k: v for k, v in tika_dict.items() if k not in _excluir}

        # Bloque 9: colores
        colores = _analizar_colores(img)

    finally:
        img.close()

    return {
        'nombre_archivo':   nombre,
        'tamano_bytes':     archivo['tamano_bytes'],
        'hashes':           hashes,
        'tecnico':          tecnico,
        'exif_camara':      exif_camara,
        'exif_captura':     exif_captura,
        'gps':              gps,
        'contenido':        contenido,
        'historial':        historial,
        'colores':          colores,
        'tika_raw':         tika_raw,
        'tika_disponible':  tika_disponible,
    }
