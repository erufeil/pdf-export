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
El análisis de colores NO usa `random`. Usa `img.resize((100,100), Image.LANCZOS).quantize(colors=8, method=Image.Quantize.MEDIANCUT)`. MEDIANCUT es determinista: la misma imagen siempre produce los mismos colores. No pasar parámetro `random_seed` ni usar `random` en ninguna parte de este servicio ni de ningún análisis forense.

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

### Etapa 30 — JSON Viewer (completada v1.1.43)

**Página:** `static/json-viewer.html` (frontend puro, sin backend)
**Categoría sidebar:** Viewers (nueva categoría entre Forensis y Misceláneos)
**Acento UI:** azul `#58A6FF` (`cat-viewer`)

#### Objetivo
Visor interactivo de archivos JSON con árbol colapsable, coloreado por tipo y búsqueda en tiempo real.

#### Funcionalidades

- Drop zone para archivos `.json` o pegado directo en textarea
- Árbol colapsable/expandible: objetos `{}` y arrays `[]` con toggle `▼/▶`
- Colores por tipo: claves (azul), strings (verde), números (naranja), booleanos (violeta), null (gris)
- Barra de herramientas: búsqueda con resaltado, Expandir todo, Colapsar todo, Copiar formateado
- Estadísticas: tipo raíz, cantidad de nodos, tamaño del archivo
- Error informativo si el JSON es inválido (muestra mensaje del parser)
- 100% frontend — no requiere backend ni job

#### Cambios en index.html

- Nueva CSS class `cat-viewer` (borde azul `--blue`)
- Nueva sección `view-viewers` con tarjeta JSON Viewer
- Nuevo nav-item "Viewers" (👁️) en sidebar Operaciones entre Forensis y Misceláneos

----

### Etapa 31 — Markdown Viewer (completada v1.1.44)

**Página:** `static/md-viewer.html` (frontend puro, sin backend)
**Categoría sidebar:** Viewers (misma categoría que JSON Viewer)
**Acento UI:** verde `#3FB950`

#### Objetivo
Visor con renderizado completo de Markdown: headings, párrafos, listas, tablas, código, blockquotes, links, negrita, cursiva, tachado.

#### Funcionalidades MD Viewer

- Drop zone para archivos `.md`/`.markdown`/`.txt` o pegado directo en textarea
- Parser Markdown puro JS (sin librerías externas): h1–h6, párrafos, ul, ol, blockquotes, code blocks, inline code, tablas, hr, bold/italic/strikethrough, links, imágenes (referencia visual)
- Toggle **Vista previa** / **Fuente** para alternar entre renderizado y texto raw
- **Copiar MD** — copia el markdown original al portapapeles
- Estadísticas: número de líneas, palabras y encabezados
- Error de parsing: nunca falla (el parser maneja cualquier input)
- 100% frontend — no requiere backend ni job

#### Seguridad del parser MD

- Todo texto de usuario se escapa con `escaparHTML()` antes de insertarse en el DOM
- Links solo permiten protocolos `https://`, `http://`, `mailto:`, `#`, `/` — el resto se reemplaza con `#`
- Imágenes externas NO se cargan — se muestra un placeholder `🖼 [nombre]`
- Sin passthrough de HTML crudo del Markdown fuente

#### Cambios index.html — Etapa 31

- Tarjeta MD Viewer agregada en `view-viewers`
- Contador actualizado a "2 herramientas"


----

### Etapa 32 — Comprimir PDF (avanzado)

**Página:** `static/pdf-compress.html`
**Servicio:** `services/pdf_compress.py` (ampliar el existente de Etapa 7)
**Endpoint:** `POST /api/v1/convert/compress` (ya existe — ampliar parámetros)
**Endpoint análisis:** `POST /api/v1/convert/compress/analyze` (nuevo, síncrono)
**Categoría sidebar:** Tengo un PDF...
**Acento UI:** `#E63946` (rojo)
**Retorna:** PDF sin comprimir

#### Objetivo

Reducir el tamaño de un PDF al máximo posible mediante 7 categorías de optimización con checkboxes. El usuario elige un preset o personaliza cada opción. Un análisis previo muestra estadísticas del PDF y el ahorro estimado por categoría antes de procesar.

---

#### Análisis automático (síncrono, antes de comprimir)

```
POST /api/v1/convert/compress/analyze
{ "file_id": "uuid" }
```

Respuesta:
```json
{
  "tamanio_bytes": 4500000,
  "paginas": 24,
  "imagenes": {
    "total": 18,
    "tamanio_estimado_bytes": 3200000,
    "dpi_promedio": 240,
    "tiene_duplicadas": true
  },
  "fuentes": {
    "total": 6,
    "embebidas": 5,
    "subseteadas": 2
  },
  "metadatos": {
    "tiene_xmp": true,
    "tiene_thumbnails": false,
    "campos_basicos": ["Title", "Author", "Producer"]
  },
  "estructura": {
    "tiene_tags_accesibilidad": true,
    "version_pdf": "1.7",
    "objetos_no_referenciados": 12
  },
  "interactivo": {
    "anotaciones": 3,
    "formularios": 0,
    "javascript": false,
    "firmas": 0,
    "adjuntos": 0
  },
  "navegacion": {
    "marcadores": 8,
    "capas_ocg": 0,
    "destinos_nombrados": 2
  },
  "optimizacion": {
    "esta_linearizado": false,
    "streams_sin_comprimir": 4,
    "xref_sin_comprimir": true
  }
}
```

---

#### Presets

| Preset | Qué aplica | Reducción estimada |
|--------|-----------|-------------------|
| **Ligero** | Metadatos XMP + thumbnails + garbage + comprimir streams | 5–15% |
| **Estándar** | Ligero + imágenes a 150 DPI / 85% JPEG + dedup objetos | 20–50% |
| **Agresivo** | Estándar + 96 DPI / 60% + dedup fuentes + anotaciones + adjuntos + JS + OCG | 50–80% |
| **Máximo** | Agresivo + convertir a grises + linearizar + bajar versión PDF | 60–90% |

---

#### Categorías y opciones

##### A. Imágenes (mayor impacto en tamaño)

| Opción | Descripción | Default Estándar | Agresivo | Máximo |
|--------|------------|-----------------|---------|--------|
| Remuestrear imágenes | DPI máximo destino: 72 / 96 / 120 / 150 / 300 | 150 DPI | 96 DPI | 72 DPI |
| Recomprimir JPEG | Calidad destino: 60 / 75 / 85 / 95 % | 85% | 60% | 60% |
| Convertir a escala de grises | Luma (0.299R + 0.587G + 0.114B) — reduce ~3× en imágenes color | Off | Off | On |
| Eliminar imágenes duplicadas | Detecta streams con mismo SHA-256 y unifica referencias | Off | On | On |
| Recodificar como JPEG 2000 | Mejor ratio calidad/tamaño (requiere Pillow con OpenJPEG) | Off | Off | Off |

**Librería:** PyMuPDF — `page.get_images()`, `doc.extract_image()`, `page.insert_image()`

---

##### B. Fuentes

| Opción | Descripción | Estándar | Agresivo |
|--------|------------|---------|---------|
| Subconjunto de fuentes (font subsetting) | Solo glifos usados — via `save(garbage=4, clean=True)` | Off | On |
| Eliminar fuentes duplicadas | Misma fuente referenciada múltiples veces → una sola | Off | On |
| Eliminar fuentes de familias estándar | Helvetica, Times, Courier, Symbol no necesitan embeberse | Off | Off |

**Nota:** PyMuPDF aplica subsetting automáticamente con `garbage=4`. Para subsetting preciso se requiere Ghostscript.

---

##### C. Metadatos

| Opción | Descripción | Estándar | Agresivo |
|--------|------------|---------|---------|
| Eliminar stream XMP | Borra el bloque XMP completo del PDF | On | On |
| Limpiar campos básicos | Vacía Título, Autor, Asunto, Palabras clave, Creador, Productor | Off | Off |
| Eliminar thumbnails embebidos | Imágenes miniatura de página almacenadas internamente | On | On |
| Eliminar información XML interno | Limpia entradas adicionales del diccionario del documento | On | On |

**Librería:** PyMuPDF — `doc.set_xml_metadata('')`, `doc.set_metadata({})`

---

##### D. Estructura

| Opción | Descripción | Estándar | Agresivo |
|--------|------------|---------|---------|
| Garbage collection (objetos huérfanos) | Elimina objetos no referenciados desde la raíz del PDF | On | On |
| Comprimir streams de contenido | Aplica Deflate/zlib a streams sin comprimir | On | On |
| Comprimir tabla xref | Usa xref comprimida (PDF 1.5+) — reduce overhead de tabla | On | On |
| Deduplicar objetos idénticos | Fusiona objetos con mismo contenido en el xref | On | On |
| Eliminar comentarios del PDF | Elimina `%% comments` del byte stream del PDF | On | On |
| Bajar versión PDF | 1.7 → 1.6 → 1.5 → 1.4 — habilita más optimizaciones antiguas | Off | Off |
| Eliminar árbol de estructura (tags) | Elimina tags de accesibilidad — afecta lectores de pantalla | Off | Off |

**Librería:** PyMuPDF — `doc.save(..., garbage=4, compress=True, deflate=True, clean=True)`

---

##### E. Elementos interactivos

| Opción | Descripción | Estándar | Agresivo |
|--------|------------|---------|---------|
| Eliminar anotaciones y comentarios | Highlights, sticky notes, marcas de revisión de PDF | Off | On |
| Aplanar formularios | Convierte campos de formulario a texto estático (no editable) | Off | Off |
| Eliminar campos de formulario | Borra campos sin aplanarlos (se pierden datos ingresados) | Off | Off |
| Eliminar JavaScript | Elimina scripts JS embebidos en el PDF | On | On |
| Eliminar firmas digitales | Borra objetos de firma del diccionario del PDF | Off | Off |
| Eliminar adjuntos | Elimina archivos embebidos (EmbeddedFiles / attachments) | Off | On |

**Librería:** PyMuPDF — `pagina.annots()`, `pagina.delete_annot(annot)`, manipulación de `/AcroForm` y `/EmbeddedFiles`

---

##### F. Navegación

| Opción | Descripción | Estándar | Agresivo |
|--------|------------|---------|---------|
| Eliminar marcadores (bookmarks) | Borra el outline / tabla de contenidos del PDF | Off | Off |
| Eliminar destinos nombrados | Elimina `/Dests` del diccionario raíz | Off | Off |
| Eliminar capas opcionales (OCG) | Borra capas de contenido opcional (OCG/OCMD) | Off | On |

**Librería:** PyMuPDF — `doc.set_toc([])`, manipulación del catálogo del PDF

---

##### G. Optimización de transmisión

| Opción | Descripción | Estándar | Máximo |
|--------|------------|---------|-------|
| Linearizar (Fast Web View) | Optimiza para carga incremental en browser — best effort | Off | On |

**Librería:** PyMuPDF — `doc.save(..., linear=True)`

---

#### UI — Layout

```
┌─ Drop Zone ────────────────────────────────────────────────────┐
│   Arrastra tu PDF aquí o haz clic para seleccionar             │
└────────────────────────────────────────────────────────────────┘

 📊 Análisis automático:  24 pág · 4.3 MB · 18 imágenes (74%) · 6 fuentes · XMP presente

┌─ Modo de compresión ──────────────────────────────────────────┐
│  ○ Ligero   ● Estándar   ○ Agresivo   ○ Máximo   ○ Personalizado │
└────────────────────────────────────────────────────────────────┘

[▼ A. Imágenes — ahorro estimado: ~60%]
   ☑ Remuestrear   DPI máx: [150▼]    Calidad JPEG: [85%▼]
   ☐ Eliminar duplicadas
   ☐ Convertir a escala de grises
   ☐ Recodificar como JPEG 2000

[▼ B. Fuentes — ahorro estimado: ~8%]
   ☐ Subconjunto de fuentes
   ☐ Eliminar fuentes duplicadas
   ☐ Eliminar familias estándar (Helvetica, Times, Courier)

[▶ C. Metadatos — ahorro estimado: ~1%]
   ☑ Eliminar XMP    ☑ Eliminar thumbnails    ☐ Limpiar campos básicos

[▶ D. Estructura — ahorro estimado: ~3%]
   ☑ Garbage collection    ☑ Comprimir streams    ☑ Comprimir xref
   ☑ Deduplicar objetos    ☑ Eliminar comentarios
   ☐ Bajar versión PDF     ☐ Eliminar tags de accesibilidad

[▶ E. Elementos interactivos — ahorro estimado: ~0%]
   ☐ Eliminar anotaciones    ☐ Aplanar formularios
   ☑ Eliminar JavaScript     ☐ Eliminar firmas    ☐ Eliminar adjuntos

[▶ F. Navegación — ahorro estimado: ~0%]
   ☐ Eliminar marcadores    ☐ Destinos nombrados    ☐ Capas OCG

[▶ G. Optimización de transmisión]
   ☐ Linearizar (Fast Web View)

 Ahorro total estimado: ~64%    →    4.3 MB  ➜  ~1.5 MB

[ Comprimir PDF ]
```

---

#### Backend — `services/pdf_compress.py` (ampliar)

```python
def procesar_compress(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    opciones = parametros.get('opciones', {})

    # A — Imágenes
    if opciones.get('reimagenes', True):
        _recomprimir_imagenes(doc, dpi=opciones.get('dpi', 150), calidad=opciones.get('calidad_jpeg', 85))
    if opciones.get('grises', False):
        _convertir_grises(doc)
    if opciones.get('dedup_imagenes', False):
        _eliminar_imagenes_duplicadas(doc)

    # C — Metadatos
    if opciones.get('eliminar_xmp', True):
        doc.set_xml_metadata('')
    if opciones.get('limpiar_basicos', False):
        doc.set_metadata({})
    if opciones.get('eliminar_thumbnails', True):
        _eliminar_thumbnails(doc)

    # E — Elementos interactivos
    if opciones.get('eliminar_anotaciones', False):
        for pagina in doc:
            for annot in list(pagina.annots()):
                pagina.delete_annot(annot)
    if opciones.get('eliminar_js', True):
        _eliminar_javascript(doc)
    if opciones.get('eliminar_adjuntos', False):
        _eliminar_adjuntos(doc)
    if opciones.get('aplanar_formularios', False):
        _aplanar_formularios(doc)

    # F — Navegación
    if opciones.get('eliminar_marcadores', False):
        doc.set_toc([])
    if opciones.get('eliminar_ocg', False):
        _eliminar_ocg(doc)

    # D + B + G — save con flags PyMuPDF
    doc.save(str(ruta_salida),
        garbage=4 if opciones.get('garbage', True) else 0,
        compress=opciones.get('comprimir_streams', True),
        deflate=opciones.get('comprimir_streams', True),
        clean=True,
        linear=opciones.get('linearizar', False),
    )
```

---

#### Parámetros del job (`parametros.opciones`)

| Clave | Tipo | Default Estándar | Descripción |
|-------|------|-----------------|-------------|
| `preset` | str | `'estandar'` | `'ligero'|'estandar'|'agresivo'|'maximo'|'personalizado'` |
| `reimagenes` | bool | True | Recomprimir imágenes |
| `dpi` | int | 150 | DPI máximo: 72 / 96 / 120 / 150 / 300 |
| `calidad_jpeg` | int | 85 | Calidad JPEG: 60 / 75 / 85 / 95 |
| `grises` | bool | False | Convertir imágenes a escala de grises (On en Máximo) |
| `dedup_imagenes` | bool | False | Eliminar imágenes duplicadas (On en Agresivo) |
| `jpeg2000` | bool | False | Recodificar como JPEG 2000 |
| `subset_fuentes` | bool | False | Subconjunto de fuentes (On en Agresivo) |
| `dedup_fuentes` | bool | False | Eliminar fuentes duplicadas (On en Agresivo) |
| `eliminar_xmp` | bool | True | Eliminar stream XMP |
| `limpiar_basicos` | bool | False | Vaciar campos básicos de metadatos |
| `eliminar_thumbnails` | bool | True | Eliminar thumbnails embebidos |
| `garbage` | bool | True | Garbage collection de objetos huérfanos |
| `comprimir_streams` | bool | True | Comprimir streams con Deflate |
| `dedup_objetos` | bool | True | Deduplicar objetos idénticos en xref |
| `bajar_version` | bool | False | Bajar versión PDF |
| `eliminar_tags` | bool | False | Eliminar árbol de estructura (tags) |
| `eliminar_anotaciones` | bool | False | Eliminar anotaciones y comentarios (On en Agresivo) |
| `aplanar_formularios` | bool | False | Aplanar formularios a texto estático |
| `eliminar_js` | bool | True | Eliminar JavaScript embebido |
| `eliminar_firmas` | bool | False | Eliminar firmas digitales |
| `eliminar_adjuntos` | bool | False | Eliminar adjuntos / archivos embebidos (On en Agresivo) |
| `eliminar_marcadores` | bool | False | Eliminar marcadores (bookmarks) |
| `eliminar_ocg` | bool | False | Eliminar capas opcionales OCG (On en Agresivo) |
| `linearizar` | bool | False | Linearizar para Fast Web View (On en Máximo) |

---

#### Endpoint

```
POST /api/v1/convert/compress
{
  "file_id": "uuid",
  "opciones": {
    "preset": "estandar",
    "reimagenes": true,
    "dpi": 150,
    "calidad_jpeg": 85,
    "eliminar_xmp": true,
    "eliminar_thumbnails": true,
    "garbage": true,
    "comprimir_streams": true,
    "dedup_objetos": true,
    "eliminar_js": true
  }
}
```

El procesador `'compress'` ya está registrado en `app.py`. Solo se amplían los parámetros que acepta.

---

#### Nombre de salida

```
{nombre_base}_compress.pdf
```

---

#### Notas de implementación

- **Font subsetting:** PyMuPDF aplica subsetting automáticamente con `save(garbage=4, clean=True)`. Subsetting manual preciso requiere Ghostscript (`gs -dSubsetFonts=true`). Documentar en NOTAS-USUARIO.md.
- **Bajar versión PDF:** PyMuPDF no controla la versión directamente. Alternativa: `gs -dCompatibilityLevel=1.4`. Marcar como "experimental" en la UI si se implementa.
- **Linearización:** `doc.save(..., linear=True)` es best effort — no todos los PDFs se linearizan perfectamente. Advertir al usuario si el PDF resultante no cambia de tamaño.
- **Estimación de ahorro:** Los porcentajes son indicativos, calculados desde el análisis previo. El ahorro real varía según el contenido específico del PDF.
- **Tabla de etapas:** Retorna ZIP (igual que la mayoría de servicios PDF). El procesador `'compress'` ya existe — no registrar uno nuevo.

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

#### A. Logo — enlace externo dentro del div

**Regla definitiva:**

- El div `sidebar-logo` se mantiene como `<div class="sidebar-logo">` (no reemplazarlo por `<a>`)
- Dentro del div, el contenido se envuelve en `<a href="https://pdf-export.xero-one.com/" target="_blank" rel="noopener" class="sidebar-logo-link">`
- CSS: `.sidebar-logo-link { display:flex; align-items:center; gap:10px; text-decoration:none; color:inherit; }`
- El breadcrumb sigue siendo la navegación interna: `Inicio › Categoría › Módulo`

---

#### B. Sidebar — igual a home

**Regla definitiva:** el sidebar de todos los módulos es idéntico al de `index.html`: mismas secciones, mismo orden, mismos ítems. No es una lista detallada de todos los servicios — es el menú de navegación de alto nivel.

```text
[Operaciones]
  📄  Tengo un PDF...   → href="/"
  ✨  Quiero un PDF     → href="/"
  🔍  Forensis          → href="/"
  🔧  Misceláneos       → href="/"

[Sistema]
  🗄️  Archivos en Cache → href="/"
  ℹ️  Acerca de         → href="/"
  ❓  Ayuda             → href="/help.html" target="_blank"
```

El ítem que corresponde a la categoría del módulo activo recibe `class="nav-item active"`.

---

#### C. Header — formato único

**Estructura obligatoria** (igual a `pdf-to-txt.html`):

```html
<header class="header">
    <div class="breadcrumb">
        <a href="/" title="Inicio">🏠</a>
        <span class="sep">/</span>
        <a href="/">Categoría</a>   <!-- Tengo un PDF / Quiero un PDF / Forensis / Misceláneos -->
        <span class="sep">/</span>
        <span class="current">Nombre del módulo</span>
    </div>
    <div class="header-right">
        <div class="stat-chip"><span class="dot"></span>Online</div>
    </div>
</header>
```

**Sin** botón home (`home-btn`) en el header — ese botón se elimina. Solo breadcrumb + chip Online.

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

#### E. Footer — una sola línea con separadores

**Formato obligatorio** (igual a `pdf-to-txt.html`):

```html
<div class="footer">
    PDF-Export &amp; Import · ERF
    &nbsp;|&nbsp; PDF Export — [Nombre del módulo] (Etapa N · lib)
    &nbsp;|&nbsp; <span id="app-version"></span>
    &nbsp;|&nbsp; <a href="/" class="footer-home-link">🏠 Inicio</a>
</div>
```

CSS requerido:

```css
.footer { text-align: center; color: #aaa; font-size: 0.75rem; padding: 1rem 0 0.5rem; }
.footer-home-link { color: #aaa; text-decoration: none; }
.footer-home-link:hover { color: var(--text); }
```

Sin `site-footer`, sin `footer-legal`, sin `footer-divider` — solo la línea única. El botón 🏠 Inicio va siempre al final.

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
| ☑ Logo con link externo | `sidebar-logo-link` → `https://pdf-export.xero-one.com/` | Spec actualizada v1.1.42 |
| ☑ Sidebar = home | Operaciones (4 ítems) + Sistema — igual a index.html | Spec actualizada v1.1.42 |
| ☑ Header sin home-btn | Solo breadcrumb + chip Online | pdf-to-txt implementado; resto pendiente |
| ☑ Footer una línea | `ERF \| módulo \| version \| 🏠 Inicio` | pdf-to-txt implementado; resto pendiente |
| ☑ `--accent` en CSS | Un solo punto de color de acento | Completado v1.1.42 |
| ☑ Sin `formatBytes` local | Expuesta como `window.formatBytes` desde common.js | Completado v1.1.42 |
| ☑ Sin `escHtml` local | Expuesta como `window.escHtml` desde common.js | Completado v1.1.42 |
| ☑ Sin `toggleSidebar` local | Expuesta como `window.toggleSidebar` desde common.js | Completado v1.1.42 |
| ☑ API URL patrón único | `window.AppConfig?.API_BASE_URL \|\| '/api/v1'` | Completado v1.1.42 |

> **Etapa 29 — Spec actualizada en v1.1.42.** `pdf-to-txt.html` es la referencia canónica para sidebar, logo, header y footer. Los demás módulos se migrarán gradualmente al mismo patrón.
