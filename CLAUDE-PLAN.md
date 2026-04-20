# CLAUDE-PLAN.md — Arquitectura y Planificación de Etapas

> **Cuándo leer este archivo:**
> - Al implementar una etapa nueva (consultar specs de UI, endpoint y lógica)
> - Al revisar el estado del proyecto (tabla de etapas)
> - Al entender el sistema de deployment o las reglas de negocio del sistema

---

## 1. Arquitectura del sistema

### Stack de despliegue
- **SO:** Ubuntu Server 22.04.5 LTS
- **Contenedor:** Docker + Docker Compose
- **Proxy:** Nginx Proxy Manager (control de acceso externo, SSL)
- **Workflow:** `git pull` en servidor → `docker build` → `docker compose up`

### Estructura del contenedor
Un solo contenedor sirve:
- Endpoints REST (`/api/v1/...`)
- Archivos estáticos (`/static/...`)
- `index.html` en la raíz (`/`)
- `config.js` con variables de entorno inyectadas

### Reglas de negocio principales
| Regla | Valor |
|-------|-------|
| Retención de archivos | 4 horas desde la subida |
| Limpieza automática | APScheduler, cada 1 hora |
| Tamaño máximo de archivo | 1 GB |
| Detección de duplicados | Coincidencia exacta: nombre + tamaño + fecha_modificacion |
| Retorno por defecto | ZIP con máxima compresión |
| Sin ZIP (retorno directo) | webp-to-png, svg-to-png, img-to-1pdf, img-to-txt, eps-to-png |
| Control de acceso | Sin auth en la app — Nginx Proxy Manager en el exterior |

### Servicios externos opcionales
| Servicio | Imagen Docker | URL default | Uso |
|----------|---------------|-------------|-----|
| Apache Tika | `apache/tika:latest-full` | `http://172.21.0.17:9998` | OCR (Etapa 22, 24) |
| NLM Ingestor | `ghcr.io/nlmatics/nlm-ingestor:latest` | `http://172.21.0.19:5001` | Extracción tablas complejas (Etapa 15) |

---

## 2. Estructura de carpetas

```
PDFexport/
├── app.py                    # Flask app factory + scheduler
├── config.py                 # Variables de entorno y rutas
├── models.py                 # ORM SQLite (archivos, trabajos)
├── entrypoint.py             # Genera config.js desde env vars
├── index.html                # Landing page (raíz del proyecto)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.development
├── .env.produccion
│
├── api/
│   ├── routes_files.py       # Upload, list, thumbnail, delete
│   ├── routes_convert.py     # Todos los endpoints de conversión
│   └── routes_jobs.py        # Estado, progreso SSE, descarga
│
├── services/
│   ├── pdf_split.py          # Etapa 2
│   ├── pdf_to_txt.py         # Etapa 3
│   ├── pdf_to_docx.py        # Etapa 4
│   ├── pdf_to_images.py      # Etapas 5 y 6 (PNG y JPG)
│   ├── pdf_compress.py       # Etapa 7
│   ├── pdf_extract_images.py # Etapa 8
│   ├── pdf_rotate.py         # Etapa 9
│   ├── html_to_pdf.py        # Etapa 10
│   ├── pdf_merge.py          # Etapa 11
│   ├── pdf_extract_pages.py  # Etapa 12
│   ├── pdf_reorder.py        # Etapa 13
│   ├── ndm_to_tables_seq.py  # Etapa 14
│   ├── pdf_to_csv.py         # Etapa 15
│   ├── web_scraper.py        # Etapa 16
│   ├── img_to_1pdf.py        # Etapa 17
│   ├── webp_to_png.py        # Etapa 18
│   ├── pdf_scanned_to_csv.py # Etapa 22
│   ├── svg_to_png.py         # Etapa 23
│   ├── img_to_txt.py         # Etapa 24
│   ├── pdf_metadata.py       # Etapa 25
│   ├── eps_to_png.py         # Etapa 27 (pendiente)
│   └── img_metadata.py       # Etapa 28
│
├── utils/
│   ├── file_manager.py       # Subida, ZIP, miniaturas, limpieza
│   ├── job_manager.py        # Cola de trabajos con threads
│   └── thumbnail.py          # Helper de miniaturas
│
├── static/
│   ├── js/common.js          # Helpers compartidos (descargar, formatBytes)
│   ├── pdf-to-txt.html
│   ├── pdf-to-docx.html
│   ├── pdf-to-png.html
│   ├── pdf-to-jpg.html
│   ├── pdf-compress.html
│   ├── pdf-extract-images.html
│   ├── pdf-split.html
│   ├── pdf-rotate.html
│   ├── html-to-pdf.html
│   ├── pdf-merge.html
│   ├── pdf-extract-pages.html
│   ├── pdf-reorder.html
│   ├── ndm-to-tables-seq.html
│   ├── pdf-to-csv.html
│   ├── web-scraper.html
│   ├── img-to-1pdf.html
│   ├── webp-to-png.html
│   ├── pdf-scanned-to-csv.html
│   ├── svg-to-png.html
│   ├── img-to-txt.html
│   ├── pdf-metadata.html     # Etapa 25
│   ├── eps-to-png.html       # Etapa 27 (pendiente)
│   ├── img-metadata.html     # Etapa 28
│   └── help.html             # Etapa 26
│
├── uploads/                  # Archivos subidos (limpieza automática 4h)
├── outputs/                  # Archivos procesados (limpieza automática 4h)
└── data/
    └── pdfexport.db
```

---

## 3. Tabla de etapas implementadas

| Etapa | Servicio | Archivo service | Endpoint | Retorna |
|-------|----------|----------------|----------|---------|
| 1 | Landing page + estructura | — | GET / | HTML |
| 2 | Cortar PDF | pdf_split.py | /split | ZIP |
| 3 | PDF→TXT | pdf_to_txt.py | /to-txt | ZIP |
| 4 | PDF→DOCX | pdf_to_docx.py | /to-docx | ZIP |
| 5 | PDF→PNG | pdf_to_images.py | /to-png | ZIP |
| 6 | PDF→JPG | pdf_to_images.py | /to-jpg | ZIP |
| 7 | Comprimir PDF | pdf_compress.py | /compress | ZIP |
| 8 | Extraer imágenes | pdf_extract_images.py | /extract-images | ZIP |
| 9 | Rotar PDF | pdf_rotate.py | /rotate | ZIP |
| 10 | HTML→PDF | html_to_pdf.py | /from-html | ZIP |
| 11 | Unir PDFs | pdf_merge.py | /merge | ZIP |
| 12 | Extraer páginas | pdf_extract_pages.py | /extract-pages | ZIP |
| 13 | Reordenar páginas | pdf_reorder.py | /reorder | ZIP |
| 14 | NDM2→SQL | ndm_to_tables_seq.py | /ndm-to-tables-seq | TXT directo |
| 15 | PDF→CSV (texto) | pdf_to_csv.py | /to-csv | ZIP |
| 16 | Web Scraper | web_scraper.py | /scrape-url | ZIP |
| 17 | IMG→PDF | img_to_1pdf.py | /img-to-1pdf | PDF directo |
| 18 | WEBP→PNG | webp_to_png.py | /webp-to-png | PNG directo |
| 19 | Rediseño HOME | — | — | — |
| 20 | Rediseño PDF→TXT | — | — | — |
| 21 | Rediseño todos los servicios | — | — | — |
| 22 | PDF Escaneado→CSV (OCR) | pdf_scanned_to_csv.py | /to-csv-ocr | ZIP |
| 23 | SVG→PNG | svg_to_png.py | /svg-to-png | PNG directo |
| 24 | IMG→TXT (OCR) | img_to_txt.py | /img-to-txt | TXT directo |
| 25 | Metadatos PDF | pdf_metadata.py | /metadata/extract + /metadata/edit | JSON (sync) + PDF directo (edit) |
| 26 | Help — Ayuda de usuario | routes_files.py | GET /help | JSON con contenido MD |
| 27 | EPS→PNG | eps_to_png.py | /eps-to-png | PNG directo |
| 28 | Metadatos Imagen | img_metadata.py | /img-metadata/extract | JSON (sync) |

---

## 4. Specs por etapa

### Etapa 2 — Cortar PDF
**Página:** `static/pdf-split.html`
**UI:** Carga PDF → miniaturas primera/última → define cortes (inicio/fin editables) → opción "N partes iguales" → hasta 20 cortes → ejecutar todos → ZIP.
**Regla:** miniatura actualiza al cambiar número de página.

---

### Etapa 3 — PDF a TXT
**Página:** `static/pdf-to-txt.html`
**UI:** Drop zone → opciones (remover nros pág, encabezados, pies, preservar párrafos, detectar columnas) → preview 500 líneas → descargar TXT.
**Lógica detección márgenes:**
- Encabezado: texto en primeros 5% de página, repetido en >80% de páginas
- Pie: texto en últimos 5%, repetido
- Número de página: patrón numérico aislado que incrementa

---

### Etapa 4 — PDF a DOCX
**Página:** `static/pdf-to-docx.html`
**UI:** Drop zone → opciones (preservar imágenes, tablas, estilos, calidad imágenes) → miniatura → convertir.
**Limitaciones:** PDFs escaneados generan DOCX con imágenes. Tablas complejas pueden no detectarse.

---

### Etapas 5 y 6 — PDF a PNG / PDF a JPG
**Páginas:** `static/pdf-to-png.html`, `static/pdf-to-jpg.html`
**UI:** Drop zone → DPI [72|150|300|600] → rango de páginas (todas / rango / específicas) → preview → convertir.
**JPG extra:** slider calidad [60%|75%|85%|95%].

---

### Etapa 7 — Comprimir PDF
**Página:** `static/pdf-compress.html`
**UI:** Drop zone → tamaño actual → nivel [Baja|Media|Alta|Personalizada] → opciones adicionales (metadatos, anotaciones, bookmarks, grises) → estimación tamaño → comprimir.
**Niveles:**
- Baja: 150 DPI, calidad 90%
- Media: 120 DPI, calidad 75%
- Alta: 96 DPI, calidad 60%

---

### Etapa 8 — Extraer Imágenes de PDF
**Página:** `static/pdf-extract-images.html`
**UI:** Drop zone → análisis automático (N imágenes encontradas) → galería miniaturas → formato salida [Original|PNG|JPG] → filtro tamaño mínimo → extraer seleccionadas/todas.

---

### Etapa 9 — Rotar PDF
**Página:** `static/pdf-rotate.html`
**UI:** Drop zone → grilla miniaturas (20 por vez) → click = rota 90° horario → indicador rotación actual → acciones rápidas (todas 90°, todas 180°, restaurar) → paginador si >20 págs → aplicar y descargar.

---

### Etapa 10 — HTML a PDF
**Página:** `static/html-to-pdf.html`
**UI:** Campo URL → botón "Vista Previa" → opciones (tamaño página, orientación, márgenes, fondo, solo contenido) → convertir.
**Consideraciones:** Timeout 30s. Sin soporte para páginas con login o SPAs sin SSR.

---

### Etapa 11 — Unir PDFs
**Página:** `static/pdf-merge.html`
**UI:** Carga múltiple → lista reordenable con drag&drop → info total páginas/tamaño → opción marcadores → unir.

---

### Etapa 12 — Extraer Páginas Específicas
**Página:** `static/pdf-extract-pages.html`
**UI:** Drop zone → miniaturas clicables → campo texto "1, 3, 5-10" → seleccionar/deseleccionar/invertir/pares/impares → formato salida (único PDF o separados) → extraer.

---

### Etapa 13 — Reordenar Páginas
**Página:** `static/pdf-reorder.html`
**UI:** Drop zone → grilla drag&drop → acciones rápidas (invertir, restaurar, mover al inicio/fin) → vista lista compacta para >20 páginas → campo "mover pág X a posición Y" → aplicar.

---

### Etapa 14 — Migrar SQL (NDM2)
**Página:** `static/ndm-to-tables-seq.html`
**Formato entrada:** Navicat Data Modeler v2, JSON con extensión `.ndm2`
**Salida:** TXT plano (Notepad Windows) con orden topológico de migración.
**Algoritmo:** Topological sort manual (sin graphlib). Itera hasta convergencia, detecta ciclos con max_iteraciones = len(tablas).
**JSON path:** `json["server"]["schemas"][0]` → `name` (DB) + `tables[].name` + `tables[].foreignKeys[].referenceTable`

---

### Etapa 15 — PDF a CSV (tablas con texto)
**Página:** `static/pdf-to-csv.html`
**Librería:** pdfplumber (primera opción) + fallback PyMuPDF para PDFs sin líneas claras.
**Endpoint análisis sync:** `POST /api/v1/convert/to-csv/analyze`
**UI:** Drop zone → análisis automático (N tablas, ¿mismas en varias páginas?) → opciones (unificar iguales, separador, saltos de línea) → extraer.
**Nombre CSV:** `tabla_pag{N}_{M}_{titulo_20chars}.csv`
**Nota:** Solo para PDFs con texto incrustado. Para escaneados → Etapa 22.

---

### Etapa 16 — Web Scraper
**Página:** `static/web-scraper.html`
**Stack:** requests + beautifulsoup4+lxml + trafilatura + markdownify
**UI:** Campo URL → previsualizar (tabs: Metadatos | Contenido | Footer | Links) → opciones (Markdown o texto plano, secciones a incluir) → descargar ZIP con TXT.
**Endpoints:** `POST /scrape-url` (async) + `POST /scrape-url/preview` (sync)
**Estructura TXT:** separadores `===` para METADATOS / CONTENIDO / FOOTER / LINKS

---

### Etapa 17 — IMG a PDF
**Página:** `static/img-to-1pdf.html`
**UI:** Carga múltiple de imágenes (cualquier formato) → lista ordenable → crear 1 PDF → retorno PDF directo (sin ZIP).

---

### Etapa 18 — WEBP a PNG
**Página:** `static/webp-to-png.html`
**UI:** Drop zone → retorno PNG directo (sin ZIP). Sin opciones adicionales.
**Nota:** Si el WEBP es animado, extrae primer frame.

---

### Etapa 22 — PDF Escaneado a CSV (OCR)
**Página:** `static/pdf-scanned-to-csv.html`
**Dependencia:** Apache Tika `apache/tika:latest-full` con Tesseract incluido.
**Flujo:** PDF → PUT /tika (Accept: text/html, X-Tika-OCRLanguage) → HTML con `<table>` → BeautifulSoup → CSV(s) → ZIP.
**Endpoints:** `POST /to-csv-ocr` (async) + `POST /to-csv-ocr/analyze` (sync, verifica Tika)
**UI:** Drop zone → verificación estado Tika → idioma OCR [spa|eng|spa+eng|por|fra|deu|ita] → opciones (unificar, separador, saltos) → ejecutar.
**Diferencia con Etapa 15:** Esta funciona con PDFs escaneados (imágenes). La 15 requiere texto incrustado.

---

### Etapa 23 — SVG a PNG
**Página:** `static/svg-to-png.html`
**Librería:** cairosvg (requiere libcairo2 en Docker, ya agregado al Dockerfile).
**UI:** Drop zone `.svg` → escala [1×|2×|3×|4×] (default 2×) → convertir → PNG directo.
**Nota:** preserva transparencia, gradientes y fuentes del SVG.

---

### Etapa 24 — IMG a TXT (OCR)
**Página:** `static/img-to-txt.html`
**Dependencia:** Apache Tika (mismo servicio que Etapa 22).
**Flujo:** Imagen → PUT /tika (Accept: text/plain, Content-Type según MIME) → texto plano → TXT directo.
**Formatos soportados:** JPG, PNG, TIFF, BMP, GIF, WEBP.
**Endpoints:** `POST /img-to-txt` (async) + `POST /img-to-txt/check` (sync, verifica Tika)
**UI:** Drop zone → verificación Tika → idioma OCR → extraer → TXT directo (utf-8-bom).

---

### Etapa 25 — Metadatos PDF (Forense)

**Página:** `static/pdf-metadata.html`
**Librería:** PyMuPDF (fitz) — extracción interna del PDF.

**Endpoints:**

- `POST /metadata/extract` (SINCRONO, sin job) — extrae todos los metadatos
- `POST /metadata/edit` (async job, tipo `'metadata-edit'`) — edita básicos y retorna PDF directo

**UI:** Drop zone → extraer → 6 secciones colapsables → botón copiar por campo → botón "Editar metadatos".

**6 bloques de información:**

1. **Básicos (editables):** título, autor, tema, palabras clave, creador, productor
2. **Fechas:** creación, modificación, versión PDF
3. **Identidad forense:** version PDF, ID original, ID actual, `fue_modificado` (IDs difieren), encriptado, linealizado, entradas xref
4. **Estructura:** páginas, tamaño página, fuentes (con flag incrustada), imágenes, anotaciones, marcadores, formularios, adjuntos, JavaScript, firmas digitales, capas OCG
5. **Permisos:** imprimir, modificar, copiar, anotar, rellenar formularios, accesibilidad, ensamblar
6. **XMP XML:** raw completo, con botón copiar

**Acento:** azul (#58A6FF)

**Nota:** `fue_modificado=True` indica que `id_original ≠ id_actual` en el trailer del PDF (firma forense de modificación externa).

---

### Etapa 26 — Help / Ayuda de usuario

**Página:** `static/help.html`
**Endpoint:** `GET /api/v1/help` — lee `NOTAS-USUARIO.md` del servidor y retorna su contenido como texto plano.
**UI:** Layout de dos columnas: TOC fijo a la izquierda (resalta la sección visible) + contenido renderizado a la derecha. Barra de búsqueda en el topbar que resalta coincidencias y hace scroll al primer resultado.
**Acceso:** Botón ❓ Ayuda en el sidebar de `index.html` (abre en nueva pestaña).
**Renderizado:** Parser Markdown vanilla JS (sin dependencias externas): h1/h2/h3, bold, italic, código inline, bloques de código, tablas, blockquotes, listas, hr.
**Nota:** Al actualizar `NOTAS-USUARIO.md` en el servidor los cambios se reflejan automáticamente sin tocar el frontend.

---

### Etapa 27 — EPS a PNG

**Página:** `static/eps-to-png.html`
**Servicio:** `services/eps_to_png.py`
**Endpoint:** `POST /api/v1/convert/eps-to-png` (async job)
**Librería:** Pillow — lee EPS via Ghostscript interno (`Image.open()` sobre `.eps` requiere `gs` instalado en el contenedor).
**Retorna:** PNG directo (sin ZIP) — un único archivo de salida.
**Formatos entrada:** `.eps`
**ALLOWED_EXTENSIONS:** agregar `'eps'`
**Dockerfile:** agregar `ghostscript` al `apt-get install` de la etapa runtime.

**UI:**
Drop zone `.eps` → escala [1×|2×|3×|4×] (default 2×) → convertir → PNG directo.
Acento de color: naranja `#F4A261`.

**Lógica del servicio:**

```python
from PIL import Image

img = Image.open(str(ruta_eps))
img.load(scale=escala)          # Pillow pasa scale a Ghostscript internamente
ancho  = img.width  * escala
alto   = img.height * escala
img = img.resize((ancho, alto), Image.Resampling.LANCZOS).convert('RGBA')
img.save(str(ruta_png), 'PNG')
```

**Endpoint en `routes_convert.py`:**

```json
POST /api/v1/convert/eps-to-png
{ "file_id": "uuid", "opciones": { "escala": 2 } }
```

- `escala`: `1` | `2` | `3` | `4` (default `2`)
- Registrar procesador: `job_manager.registrar_procesador('eps-to-png', procesar_eps_to_png)`

**Nota técnica:** Pillow delega el rasterizado EPS a Ghostscript mediante un proceso externo. Si `gs` no está en el PATH el `Image.open()` lanza `OSError`. Verificar con `which gs` en el contenedor.

**Tabla de etapas:** `Sin ZIP (retorno directo)` — igual que svg-to-png.

---

### Etapa 28 — Metadatos IMG (Forense)

**Página:** `static/img-metadata.html`
**Servicio:** `services/img_metadata.py`
**Endpoint:** `POST /api/v1/convert/img-metadata/extract` (síncrono, sin job)
**Formatos:** JPG, JPEG, PNG, TIFF, TIF, BMP, GIF, WEBP
**Acento UI:** verde `#3FB950`

#### Objetivo
Extraer la huella digital completa de una imagen: metadatos técnicos, EXIF de cámara, GPS, autoría IPTC/XMP, historial de edición Photoshop, análisis de colores dominantes y hashes de integridad. Todo en un único campo de texto copiable.

#### Fuentes de datos

| Fuente | Qué extrae | Disponibilidad |
|--------|-----------|----------------|
| `hashlib` | SHA-256 + MD5 del archivo en disco | Siempre |
| `Pillow` (Image, getexif, ImageStat) | Formato, modo, dims, DPI, ICC, EXIF nativo, GPS, análisis de colores | Siempre |
| `Apache Tika` PUT /meta (Accept: application/json) | IPTC, XMP, Photoshop, Dublin Core, todos los namespaces | Solo si Tika disponible |

Si Tika no está disponible, bloques 7, 8 y 10 muestran `"Tika no disponible"` y el resto funciona igual con Pillow.

---

### Etapa 29 Homogeneizacion

completada. Resumen de lo que se hizo en esta sesión:

--accent CSS: cada módulo HTML ahora define --accent: #HEX en :root y usa var(--accent) en lugar de var(--purple), var(--orange), etc.
Breadcrumbs: estandarizados en todos los módulos con categorías correctas (PDF, Conversión, Web, Forensis)
Footers: formato PDF Export — Nombre (Etapa N · lib) en los 23 módulos
API URL: todos usan const API = window.AppConfig?.API_BASE_URL || '/api/v1'
NOTAS-USUARIO.md: agregada sección EPS a PNG
CLAUDE-PLAN.md: Etapa 29 marcada como completada
config.py: versión 1.1.42

---

#### Arquitectura del servicio

```python
extraer_metadatos_imagen(archivo_id) -> dict
  _calcular_hashes(ruta)            # MD5 + SHA-256
  _extraer_tecnico(img)             # formato, modo, dims, DPI, ICC profile
  _extraer_exif(img)                # getexif() -> IFD0 + ExifIFD(0x8769) + GPSIFD(0x8825)
  _decodificar_gps(gps_ifd)         # IFDRational -> decimal + link OpenStreetMap
  _extraer_tika(ruta, mime_type)    # PUT /meta Accept:application/json -> dict raw
  _parsear_iptc_xmp(tika_dict)      # filtra namespaces tiff/exif/xmp/dc/photoshop
  _analizar_colores(img)            # colores deterministas (sin random, MEDIANCUT)
```

#### Determinismo en el análisis de colores (REGLA IMPORTANTE)
El análisis de colores NO usa `random`. Usa `img.resize((100,100), Image.LANCZOS).quantize(colors=8, method=Image.Quantize.MEDIANCUT)`. MEDIANCUT es determinista: la misma imagen siempre produce los mismos colores. No pasar parámetro `random_seed` ni usar `random` en ninguna parte de este servicio ni de ningún análisis forense. Si un algoritmo requiere seed, usar `random.seed(43)` fijo, pero preferir algoritmos deterministas sin seed.

#### 10 bloques de información

**Bloque 1 — ARCHIVO**
`nombre`, `tamaño` formateado, `SHA-256`, `MD5`

**Bloque 2 — TÉCNICO** (Pillow)
Formato (JPEG/PNG/TIFF/WEBP/BMP/GIF), modo de color (RGB/RGBA/CMYK/L/P/YCbCr),
dimensiones `ancho x alto px` + megapixeles calculados, resolución DPI X/Y,
bits por muestra, numero de canales, frames (GIF animado / TIFF multi / WEBP animado),
transparencia (si/no), perfil ICC (nombre desde bytes 36-68 del bloque),
JPEG progresivo, tipo de compresión.

**Bloque 3 — CAMARA / DISPOSITIVO** (EXIF IFD0, Pillow tag IDs)
`Make`(271), `Model`(272), `Software`(305), `Artist`(315), `Copyright`(33432),
`ImageDescription`(270), `Orientation`(274) con texto legible, `DateTime`(306),
`XResolution`/`YResolution`/`ResolutionUnit`.

**Bloque 4 — CONFIGURACION DE CAPTURA** (ExifIFD via `getexif().get_ifd(0x8769)`)
`DateTimeOriginal`(36867), `DateTimeDigitized`(36868), `SubSecTimeOriginal`(37521),
`ExposureTime`(33434) como fraccion (ej: 1/250s), `FNumber`(33437) como f/N,
`ISOSpeedRatings`(34855), `ShutterSpeedValue`(37377), `ApertureValue`(37378),
`ExposureBiasValue`(37380) en EV, `MeteringMode`(37383) con texto,
`Flash`(37385) legible, `FocalLength`(37386) en mm,
`FocalLengthIn35mmFilm`(41989), `ColorSpace`(40961),
`WhiteBalance`(41987), `ExposureMode`(41986), `ExposureProgram`(34850),
`SceneCaptureType`(41990), `Contrast`(41992)/`Saturation`(41993)/`Sharpness`(41994).

**Bloque 5 — LENTE Y SERIALES** (ExifIFD)
`LensMake`(42035), `LensModel`(42036), `LensSpecification`(42034),
`BodySerialNumber`(42033), `LensSerialNumber`(42037).

**Bloque 6 — GPS** (GPS IFD via `getexif().get_ifd(0x8825)`)
Latitud decimal, longitud decimal, altitud en metros, velocidad, direccion de camara,
fecha/hora GPS, link a OpenStreetMap.
Advertencia de privacidad visible si hay GPS presente.

Conversion de coordenadas (determinista, sin random):
```python
def _gps_a_decimal(val, ref):
    d = val[0][0]/val[0][1]
    m = val[1][0]/val[1][1]
    s = val[2][0]/val[2][1]
    dec = d + m/60 + s/3600
    return -dec if ref in ('S', 'W') else dec
```

**Bloque 7 — CONTENIDO / AUTORIA** (Tika: `dc:`, `photoshop:`, `Iptc4xmpCore:`)
`dc:title`, `dc:creator`, `dc:description`, `dc:subject`, `dc:rights`,
`photoshop:Credit`, `photoshop:City`, `photoshop:Country`, `photoshop:State`,
`photoshop:Category`, `photoshop:ICCProfile`, `photoshop:ColorMode`,
`Iptc4xmpCore:Location`, `Iptc4xmpCore:IntellectualGenre`.

**Bloque 8 — HISTORIAL DE EDICION** (Tika: `xmp:`, `xmpMM:`)
`xmp:CreatorTool`, `xmp:CreateDate`, `xmp:ModifyDate`, `xmp:MetadataDate`,
`xmpMM:DocumentID`, `xmpMM:OriginalDocumentID`, `xmpMM:InstanceID`,
`xmpMM:History`, `xmpMM:DerivedFrom`.
Indicador forense: `fue_editado = (InstanceID != DocumentID)` → badge de advertencia.

**Bloque 9 — ANALISIS DE COLORES** (Pillow, 100% determinista)
- Top 8 colores dominantes via `img.resize((100,100), LANCZOS).quantize(8, MEDIANCUT)` + frecuencia
- Cada color: hex + RGB + porcentaje de presencia
- Color promedio de la imagen: hex de `ImageStat.mean` (R, G, B)
- Brillo promedio: ImageStat sobre canal L (0=negro, 255=blanco)
- StdDev por canal R/G/B (contraste y riqueza)
- En la UI: cuadraditos de color visual encima del textarea (no van en el texto copiable)

**Bloque 10 — TIKA RAW** (dump completo JSON de Tika, si disponible)
Todos los campos devueltos por `/meta` sin filtrar. Captura namespaces no previstos.

#### Endpoint Tika /meta

```python
def _extraer_tika(ruta: Path, mime_type: str) -> dict:
    url = config.TIKA_URL
    if not url:
        return {}
    headers = {'Content-Type': mime_type, 'Accept': 'application/json'}
    with open(ruta, 'rb') as f:
        r = requests.put(f'{url}/meta', headers=headers, data=f, timeout=60)
    return r.json() if r.status_code == 200 else {}
```

#### Frontend `static/img-metadata.html`
- Mismo patron que Etapa 25: sidebar con drop zone + campo texto unico + boton "Copiar todo"
- Acepta: `.jpg .jpeg .png .tiff .tif .bmp .gif .webp`
- Sobre el textarea: fila de cuadraditos de colores dominantes con hex y porcentaje (solo visual)
- Badge rojo si hay GPS: "Esta imagen contiene coordenadas GPS"
- Badge amarillo si fue editado: "Modificado (InstanceID difiere de DocumentID)"
- Nota al pie si Tika no disponible
- Sin boton de edicion

#### En app.py y routes_convert.py
- `from services import img_metadata` en `app.py`
- Endpoint `POST /api/v1/convert/img-metadata/extract` en `routes_convert.py`
- Llamada sincrona directa: `img_metadata.extraer_metadatos_imagen(archivo_id)`

---
### Errores pendientes de correccion:
revisar todos los html para homogeneizarlos con el mismo marco y el mismo home
Falta Etapa 26 y 27
---

## 5. Diseño visual — tema IBM Plex

Todas las páginas de servicios usan el mismo tema oscuro:

```css
--bg:      #0D1117  /* fondo global */
--sidebar: #161B22  /* sidebar y topbar */
--card:    #1C2128  /* tarjetas */
--border:  #30363D
--red:     #E63946  /* logo, acento por defecto */
--orange:  #F4A261  /* OCR escaneado */
--blue:    #58A6FF  /* acciones primarias generales */
--green:   #3FB950  /* éxito, CSV */
--yellow:  #E3B341  /* IMG a TXT */
--purple:  #A371F7  /* SVG a PNG */
--text:    #E6EDF3
--muted:   #8B949E
```

**Acento por servicio:**
- PDF a CSV: verde
- PDF Escaneado a CSV: naranja
- SVG a PNG: púrpura
- IMG a TXT: amarillo
- WEBP a PNG: azul
- Resto: rojo o azul según contexto

---

### Etapa 29 — Corrección general y homogeneización

**Objetivo:** unificar el marco visual y de código de todos los módulos frontend para que sean indistinguibles estructuralmente entre sí. No cambia funcionalidad.

---

#### A. Doble "home" — eliminar el logo-link

**Problema:** algunos módulos (ej. `pdf-to-txt.html`) tienen el logo del sidebar como `<a href="/">` — un botón home redundante. El breadcrumb ya cumple esa función con `Inicio › Categoría › Módulo`.

**Regla definitiva:**
- Sidebar logo: siempre `<div class="sidebar-logo">PDF</div>` — no es un enlace
- Breadcrumb: siempre presente, siempre con `<a href="/">Inicio</a> › Categoría › Módulo actual`
- No existe ningún otro enlace o botón que lleve a home en la página

---

#### B. Sidebar — contenido desactualizado

**Problema:** cada HTML tiene el sidebar hardcodeado y muchos no incluyen los servicios nuevos (eps-to-png, pdf-metadata, img-metadata, help).

**Regla definitiva:** todos los sidebars deben tener exactamente las mismas secciones y links, en el mismo orden:

```text
[Tengo un PDF…]
  TXT  PDF a Texto
  DOC  PDF a DOCX
  PNG  PDF a PNG
  JPG  PDF a JPG
  ZIP  Comprimir PDF
  IMG  Extraer Imágenes
  CUT  Cortar PDF
  ROT  Rotar PDF
  MRG  Unir PDFs
  EXT  Extraer Páginas
  ORD  Reordenar
  CSV  PDF a CSV
  OCR  Escaneado a CSV

[Quiero un PDF…]
  HTM  HTML a PDF
  IMG  IMG a PDF

[Utilidades]
  SCR  Scraper Web
  NDM  Migrar SQL
  WBP  WEBP a PNG
  SVG  SVG a PNG
  EPS  EPS a PNG
  OCR  IMG a TXT

[Forensis]
  META  Metadatos PDF
  EXIF  Metadatos Imagen
```

El ítem activo recibe `class="nav-item active"`. El link apunta siempre a `/static/[nombre].html` (sin `/static/` solo en los que están en raíz: `pdf-metadata.html`, `img-metadata.html`, `help.html` → `/pdf-metadata.html`, etc.).

---

#### C. Topbar / encabezado — formato único

**Estructura obligatoria:**

```html
<div class="topbar">
  <div class="breadcrumb">
    <a href="/">Inicio</a>
    <span class="sep">›</span>
    <span>[Categoría]</span>   <!-- Tengo un PDF / Quiero un PDF / Utilidades / Forensis -->
    <span class="sep">›</span>
    <span class="current">[Nombre del módulo]</span>
  </div>
  <span class="topbar-badge">[SIGLA 3-4 chars]</span>
</div>
```

Sin botones adicionales, sin elementos extra. El badge usa la sigla del módulo (TXT, DOC, PNG, EPS, META, etc.).

---

#### D. Funciones duplicadas — eliminar de los HTML

**Problema:** `formatBytes()` y `escHtml()` están definidas inline en cada HTML (svg-to-png, eps-to-png y otros) además de existir equivalentes en `common.js` (`window.PDFExport.formatearTamano`, pero con diferente nombre).

**Solución:**

1. Agregar a `common.js` → `window.PDFExport`:
   - `formatBytes(b)` — igual a la versión inline actual
   - `escHtml(s)` — igual a la versión inline actual
2. En cada HTML: eliminar las definiciones locales, reemplazar las llamadas directas por `window.PDFExport.formatBytes(...)` y `window.PDFExport.escHtml(...)`
3. `toggleSidebar()` también es idéntica en todos los HTML → mover a `common.js`

---

#### E. Footer — formato único

**Formato obligatorio:**

```text
PDF Export — [Nombre del módulo] (Etapa N · librería principal)
```

Ejemplos:

- `PDF Export — SVG a PNG (Etapa 23 · cairosvg)`
- `PDF Export — EPS a PNG (Etapa 27 · Pillow + Ghostscript)`
- `PDF Export — PDF a Texto (Etapa 3 · PyMuPDF)`

---

#### F. Variable de acento — `--accent` en lugar de nombre de color

**Problema:** cada módulo usa su color de acento con su nombre propio (`--purple`, `--orange`, `--green`) esparcido en decenas de lugares del CSS.

**Solución:** todos los módulos definen `--accent` con su color específico al inicio de `:root`, y el CSS solo usa `var(--accent)` en todos los lugares donde va el color del módulo. Así cambiar el acento de un módulo requiere editar una sola línea.

```css
:root {
  /* ... colores base ... */
  --accent: #A371F7;  /* ← única línea que varía por módulo */
}
```

---

#### G. Detección de API URL — patrón único

Todos los módulos deben usar exactamente:

```js
const API = window.AppConfig?.API_BASE_URL || '/api/v1';
```

Sin variaciones (`window.AppConfig.API_BASE_URL`, hardcoded `/api/v1`, etc.).

---

#### H. Tabla resumen de inconsistencias por módulo

Al ejecutar esta etapa, verificar módulo por módulo:

| Check | Descripción | Estado |
|-------|-------------|--------|
| ☑ Logo no es link | `<div class="sidebar-logo">PDF</div>` sin `<a>` | Completado — todos los HTML convertidos |
| ☐ Breadcrumb completo | Inicio › Categoría › Módulo | Pendiente |
| ☑ Sidebar actualizado | Incluye EPS a PNG + sección Forensis (META + EXIF) | Completado en 9 HTMLs Estilo B |
| ☐ `--accent` en CSS | Un solo punto de color de acento | Pendiente |
| ☑ Sin `formatBytes` local | Expuesta como `window.formatBytes` desde common.js | Completado — eliminada de todos los HTMLs |
| ☑ Sin `escHtml` local | Expuesta como `window.escHtml` desde common.js | Completado — eliminada de todos los HTMLs |
| ☑ Sin `toggleSidebar` local | Expuesta como `window.toggleSidebar` desde common.js | Completado — eliminada de todos los HTMLs |
| ☑ Footer formato correcto | `PDF Export — Nombre (Etapa N · lib)` | Completado v1.1.42 |
| ☑ API URL patrón único | `window.AppConfig?.API_BASE_URL \|\| '/api/v1'` | Completado v1.1.42 |

> **Etapa 29 — Completada en v1.1.42.** Todos los ítems A–G implementados: logo-link, sidebar Forensis+EPS, breadcrumbs, funciones comunes en common.js, footers estandarizados, `--accent` CSS unificado, API URL con optional chaining y fallback.
