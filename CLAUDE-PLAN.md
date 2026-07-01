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
- `config.js` con variables de entorno inyectadas (ruta Flask dinámica, `Cache-Control: no-store`)

### Reglas de negocio principales
| Regla | Valor |
|-------|-------|
| Retención de archivos | 4 horas desde la subida |
| Limpieza automática | APScheduler, cada 1 hora |
| Tamaño máximo de archivo | 1 GB |
| Detección de duplicados | Coincidencia exacta: nombre + tamaño + fecha_modificacion |
| Control de acceso | Sin auth en la app — Nginx Proxy Manager en el exterior |
| Sin ZIP (retorno directo) | compress, to-txt, to-docx, rotate, from-html, merge, reorder, img-to-1pdf, webp-to-png, svg-to-png, img-to-txt, eps-to-png, ndm-to-tables-seq |
| Con ZIP | split, to-png, to-jpg, extract-images, to-csv, to-csv-ocr, scrape-url, extract-pages (modo separados) |

### Servicios externos opcionales
| Servicio | Imagen Docker | URL default | Uso |
|----------|---------------|-------------|-----|
| Apache Tika | `apache/tika:latest-full` | `http://172.21.0.17:9998` | OCR (Etapas 22, 24, 28) |
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
│   ├── routes_files.py       # Upload, list, thumbnail, delete, /help
│   ├── routes_convert.py     # Todos los endpoints de conversión
│   └── routes_jobs.py        # Estado, progreso SSE, descarga
│
├── services/
│   ├── pdf_split.py          # Etapa 2
│   ├── pdf_to_txt.py         # Etapa 3
│   ├── pdf_to_docx.py        # Etapa 4
│   ├── pdf_to_images.py      # Etapas 5 y 6 (PNG y JPG)
│   ├── pdf_compress.py       # Etapa 7 / 32
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
│   ├── eps_to_png.py         # Etapa 27
│   └── img_metadata.py       # Etapa 28
│
├── utils/
│   ├── file_manager.py       # Subida, ZIP, miniaturas, limpieza
│   ├── job_manager.py        # Cola de trabajos con threads
│   └── thumbnail.py          # Helper de miniaturas
│
├── static/
│   ├── js/common.js          # Helpers: formatBytes, escHtml, toggleSidebar
│   ├── js/pdf-compress.js    # Lógica compress (SSE + polling híbrido)
│   └── [modulo].html         # Un HTML por servicio
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
| 3 | PDF→TXT | pdf_to_txt.py | /to-txt | TXT directo |
| 4 | PDF→DOCX | pdf_to_docx.py | /to-docx | DOCX directo |
| 5 | PDF→PNG | pdf_to_images.py | /to-png | ZIP |
| 6 | PDF→JPG | pdf_to_images.py | /to-jpg | ZIP |
| 7 | Comprimir PDF | pdf_compress.py | /compress | PDF directo |
| 8 | Extraer imágenes | pdf_extract_images.py | /extract-images | ZIP |
| 9 | Rotar PDF | pdf_rotate.py | /rotate | PDF directo |
| 10 | HTML→PDF | html_to_pdf.py | /from-html | PDF directo |
| 11 | Unir PDFs | pdf_merge.py | /merge | PDF directo |
| 12 | Extraer páginas | pdf_extract_pages.py | /extract-pages | PDF directo (único) / ZIP (separados) |
| 13 | Reordenar páginas | pdf_reorder.py | /reorder | PDF directo |
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
| 25 | Metadatos PDF | pdf_metadata.py | /metadata/extract + /metadata/edit | JSON (sync) / PDF directo (edit) |
| 26 | Help — Ayuda de usuario | routes_files.py | GET /help | JSON con contenido MD |
| 27 | EPS→PNG | eps_to_png.py | /eps-to-png | PNG directo |
| 28 | Metadatos Imagen | img_metadata.py | /img-metadata/extract | JSON (sync) |
| 29 | Homogeneización frontend | — | — | — |
| 30 | JSON Viewer | — (frontend puro) | — | — |
| 31 | Markdown Viewer | — (frontend puro) | — | — |
| 32 | Comprimir PDF (avanzado) | pdf_compress.py | /compress + /compress/analyze | PDF directo |
| 33 | Caracteres Invisibles Viewer | — (frontend puro) | — | — |
| 34 | Mejorar PDF→TXT (detección escaneado) | pdf_to_txt.py | /to-txt | TXT directo |
| 35 | Excel→CSV | xlsx_to_csv.py | /xlsx-to-csv + /xlsx-to-csv/info | CSV directo o ZIP |
| 36 | Mejoras de stack | pdf_metadata.py | /metadata/extract (+pdf_escaneado) | — |
| 37 | Categoría "Quiero un MD" en sidebar | index.html | — | — |
| 38 | PDF→MD | pdf_to_md.py | /to-md | MD directo |
| 39 | Excel→MD | xlsx_to_md.py | /excel-to-md | MD directo |
| 43 | YouTube CC→MD | youtube_to_md.py | /youtube-to-md | MD directo |
| 44 | Wikipedia→MD | wikipedia_to_md.py | /wikipedia-to-md | MD directo |

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

### Etapa 7 / 32 — Comprimir PDF (avanzado)
**Página:** `static/pdf-compress.html` | **JS:** `static/js/pdf-compress.js`
**Servicio:** `services/pdf_compress.py`
**Endpoints:** `POST /compress` (async) + `POST /compress/analyze` (sync)
**Acento UI:** `#E63946` (rojo)
**Retorna:** PDF directo (sin ZIP)

#### Presets
| Preset | Qué aplica | Reducción estimada |
|--------|-----------|-------------------|
| Ligero | Metadatos XMP + thumbnails + garbage + comprimir streams | 5–15% |
| Estándar | Ligero + imágenes a 150 DPI / 85% JPEG + dedup objetos | 20–50% |
| Agresivo | Estándar + 96 DPI / 60% + dedup fuentes + anotaciones + adjuntos + JS + OCG | 50–80% |
| Máximo | Agresivo + grises + linearizar + bajar versión PDF + Ghostscript | 60–90% |

#### 7 categorías de optimización
- **A. Imágenes:** remuestrear DPI, recomprimir JPEG, escala de grises, dedup por SHA-256
- **B. Fuentes:** font subsetting (`doc.subset_fonts()` sin args), dedup fuentes, eliminar familias estándar
- **C. Metadatos:** eliminar XMP, limpiar campos básicos, eliminar thumbnails
- **D. Estructura:** garbage collection (garbage=4), comprimir streams (deflate=), xref comprimida, dedup objetos
- **E. Elementos interactivos:** anotaciones, formularios, JavaScript, firmas, adjuntos
- **F. Navegación:** marcadores (bookmarks), destinos nombrados, capas OCG
- **G. Transmisión:** linearizar (Fast Web View), Ghostscript (rasteriza fuentes COLR/emoji)

#### Monitoreo del job
SSE + polling paralelo cada 2s. `terminado` flag evita doble-disparo. SSE keepalive cada 10s (`: keepalive\n\n`) para mantener TCP vivo durante GS.

#### Notas técnicas importantes
- `doc.save()` usa `deflate=True`, NO `compress=` (no existe en PyMuPDF v1.23.7)
- `deflate_fonts=True` debe pasarse explícitamente
- `subset_fonts()` sin argumentos (v1.23.7)
- `get_fonts(full=True)` retorna >6 campos — acceder por índice, no por unpacking
- Fuentes COLR (emoji): solo Ghostscript puede comprimirlas. Detectar con `b'COLR' in doc.extract_font(xref)[:1000]`
- `/compress/analyze` retorna `tiene_colr`, `fuentes_colr`, `gs_disponible`

---

### Etapa 8 — Extraer Imágenes de PDF
**Página:** `static/pdf-extract-images.html`
**UI:** Drop zone → análisis automático (N imágenes encontradas) → galería miniaturas → formato salida [Original|PNG|JPG] → filtro tamaño mínimo → extraer seleccionadas/todas.
**Nota:** SMask xrefs (alpha channels) excluidos de la lista de imágenes reales.

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
**Salida:** TXT plano con orden topológico de migración.
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
**Librería:** cairosvg (requiere libcairo2 en Docker).
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
**Librería:** PyMuPDF (fitz)
**Endpoints:** `POST /metadata/extract` (sync) + `POST /metadata/edit` (async, tipo `'metadata-edit'`)
**Acento:** azul `#58A6FF`

**6 bloques de información:**
1. **Básicos (editables):** título, autor, tema, palabras clave, creador, productor
2. **Fechas:** creación, modificación, versión PDF
3. **Identidad forense:** ID original, ID actual, `fue_modificado` (IDs difieren), encriptado, linealizado, entradas xref
4. **Estructura:** páginas, tamaño, fuentes, imágenes, anotaciones, marcadores, formularios, adjuntos, JavaScript, firmas, capas OCG
5. **Contenido de texto:** `total_caracteres`, `total_palabras`, `ratio_bytes_por_caracter` (densidad texto)
6. **Permisos:** imprimir, modificar, copiar, anotar, rellenar formularios, accesibilidad, ensamblar
7. **XMP XML:** raw completo con botón copiar

**Nota:** `fue_modificado=True` indica `id_original ≠ id_actual` en el trailer. `ratio < 1` = texto muy denso, `< 5` = texto + gráficos, `< 20` = mixto, `>= 20` = predominantemente imágenes.

---

### Etapa 26 — Help / Ayuda de usuario
**Página:** `static/help.html`
**Endpoint:** `GET /api/v1/help` — lee `NOTAS-USUARIO.md` del servidor y retorna su contenido como texto plano.
**UI:** TOC fijo a la izquierda (resalta sección visible) + contenido renderizado a la derecha. Barra de búsqueda con resaltado y scroll al primer resultado.
**Acceso:** Botón ❓ Ayuda en el sidebar (abre en nueva pestaña).

---

### Etapa 27 — EPS a PNG
**Página:** `static/eps-to-png.html`
**Servicio:** `services/eps_to_png.py`
**Endpoint:** `POST /eps-to-png` (async)
**Librería:** Pillow (`Image.open()` sobre `.eps` delega a Ghostscript interno)
**Retorna:** PNG directo (sin ZIP)
**UI:** Drop zone `.eps` → escala [1×|2×|3×|4×] (default 2×) → convertir.
**Acento:** naranja `#F4A261`
**Dockerfile:** `ghostscript` en `apt-get install`.

---

### Etapa 28 — Metadatos Imagen (Forense)
**Página:** `static/img-metadata.html`
**Servicio:** `services/img_metadata.py`
**Endpoint:** `POST /img-metadata/extract` (síncrono, sin job)
**Formatos:** JPG, JPEG, PNG, TIFF, TIF, BMP, GIF, WEBP
**Acento UI:** verde `#3FB950`

**10 bloques:** Archivo (SHA-256, MD5) · Técnico (formato, modo, dims, DPI) · Cámara/Dispositivo (EXIF IFD0) · Configuración de captura (ExifIFD) · Lente y seriales · GPS (con link OSM + advertencia privacidad) · Contenido/Autoría (Tika: dc:, photoshop:, IPTC) · Historial de edición (Tika: xmp:, xmpMM:) · Análisis de colores (MEDIANCUT determinista) · Tika RAW.

**Regla forense:** ningún `random`. `img.quantize(colors=8, method=Image.Quantize.MEDIANCUT)` es determinista. Fix conocido: `float()` antes de `round()` con valores EXIF de Pillow (evita Fraction no serializable).

**Tika opcional:** Si no disponible, bloques 7, 8 y 10 muestran `"Tika no disponible"`.

---

### Etapa 29 — Homogeneización frontend (completada v1.1.42)
`--accent: #HEX` en `:root` por módulo, `var(--accent)` internamente. `common.js` exporta `formatBytes`, `escHtml`, `toggleSidebar` como `window.X`. Logo sidebar: `<div class="sidebar-logo">` (no `<a>`). API URL: `const API = window.AppConfig?.API_BASE_URL || '/api/v1'`. Breadcrumbs estandarizados. Footer: `PDF Export — Nombre (Etapa N · lib)`.

---

### Etapa 30 — JSON Viewer (completada v1.1.43)
**Página:** `static/json-viewer.html` (frontend puro, sin backend)
**Categoría sidebar:** Viewers (nueva, entre Forensis y Misceláneos)
**Acento UI:** azul `#58A6FF` (`cat-viewer`)

Árbol colapsable por tipo (objetos/arrays), colores por tipo de dato, búsqueda con resaltado, estadísticas (tipo raíz, nodos, tamaño). 100% JS — no requiere backend.

---

### Etapa 31 — Markdown Viewer (completada v1.1.44)
**Página:** `static/md-viewer.html` (frontend puro, sin backend)
**Categoría sidebar:** Viewers
**Acento UI:** verde `#3FB950`

Parser Markdown puro JS: h1–h6, listas, tablas, code blocks, blockquotes, bold/italic/strikethrough, links. Toggle Vista previa / Fuente. Links validados (solo http/https/mailto/#). Imágenes: placeholder visual, no se cargan. Sin passthrough de HTML crudo.

---

### Etapa 33 — Caracteres Invisibles Viewer (planificada)
**Página:** `static/txt-invisible.html`
**Categoría sidebar:** Viewers
**Tipo:** Frontend puro, sin backend

**Objetivo:** Pegar o cargar texto → detectar y resaltar caracteres problemáticos:
- **Blanco:** UTF-8 normal
- **Amarillo:** caracteres fuera de UTF-8 (para limpieza manual)
- **Rojo:** caracteres invisibles (zero-width space, BOM, soft hyphen, etc.)
- Si el carácter no tiene glifo visible → mostrar U+1FBC4 (cuadrado con interrogación)

Salida: texto limpiado de invisibles en textarea copiable.

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

**Acento por servicio:** PDF a CSV → verde · PDF Escaneado a CSV → naranja · SVG a PNG → púrpura · IMG a TXT → amarillo · WEBP a PNG → azul · Resto → rojo o azul según contexto.

**`html { background: #0D1117; }` + `<meta name="color-scheme" content="dark">` en todos los módulos.**

---

## 6. Etapas futuras (planificación)

### Etapa 34 — Mejorar PDF→TXT (v1.1.56 — COMPLETADA)
**Servicio:** `services/pdf_to_txt.py` (modificado)
**Hallazgo:** el servicio ya usaba 100% `pdfminer.six` (`extract_text_to_fp` + `extract_pages`), no PyMuPDF
`page.get_text()` como se asumió originalmente en CLAUDE-rta1.md — esa parte del plan ya estaba resuelta.
**Cambio real aplicado:** detección de PDF escaneado. Si el texto extraído queda vacío
(`texto.strip()` falso) el job falla con `ValueError` indicando al usuario que el PDF parece
no tener capa de texto y sugiriendo `/to-csv-ocr` (Tika) como alternativa, en vez de devolver
silenciosamente un .txt vacío.
**UI:** sin cambios. Mismo endpoint `/to-txt`. El preview (`/to-txt/preview`) ya manejaba el caso vacío.

---

### Etapa 35 — Excel→CSV (v1.1.57 — COMPLETADA)
**Página:** `static/xlsx-to-csv.html` · **Servicio:** `services/xlsx_to_csv.py`
**Endpoint:** `POST /xlsx-to-csv` (async) + `POST /xlsx-to-csv/info` (sync, retorna lista de hojas)
**Librería:** pandas + openpyxl (xlsx) + xlrd (xls) — añadidos a `requirements.txt`
**Formatos entrada:** `.xlsx`, `.xls` — añadidos a `ALLOWED_EXTENSIONS`
**Retorna:** CSV directo (1 hoja) o ZIP (múltiples hojas)
**Acento UI:** verde `#3FB950`
**UI:** Drop zone → info de hojas (chips verdes) → opciones (separador `,`/`;`, codificación) → convertir.
**Naming:** individual `{stem} - hoja {N_pad} {hoja_safe}.csv` · ZIP `{job_id}_{stem}_csv.zip`

---

### Etapa 36 — Mejoras de stack (v1.1.58 — COMPLETADA)
Mejoras internas sin nueva UI:
- **Detección PDF escaneado en metadatos ✅:** `_contar_texto()` en `pdf_metadata.py` ahora incluye
  `'pdf_escaneado': total_chars == 0` en `contenido_texto`. Aparece en la respuesta de `/metadata/extract`.
- **pdfplumber en pdf_to_csv.py ✅ (ya correcto):** verificado — usa `page.find_tables()` + `.extract()`
  como extractor primario (equivalente a `extract_table()`). `extract_words()` solo se usa como auxiliar
  en `_buscar_titulo_encabezado()` para buscar texto sobre la tabla detectada. Sin cambios necesarios.
- **pdfminer en pdf_to_txt.py ✅:** completado en Etapa 34.

---

### Etapa 37 — Nueva categoría "Quiero un MD" en sidebar (v1.1.59 — COMPLETADA)
**Archivos modificados:** `index.html`, `config.py`
**Categoría nueva:** "Quiero un MD", ícono 📝
**Color:** `--violet: #9B59B6` (nueva variable CSS en `:root`), clase `.card.cat-md`
**Badge:** `.badge-pronto` (violeta) con texto "Pronto"
**Ubicación:** entre "Quiero un PDF" y "Forensis" en el sidebar (navIdx 2, desplaza forensis→3, viewers→4, misc→5, cache→6, about→7)
**VISTAS map:** `md: { label: 'Quiero un MD', navIdx: 2 }`
**Tarjetas en `view-md`:** PDF→MD, Excel→MD, EPUB→MD, Audio→MD (Whisper), Web→MD
Todas con `class="card cat-md"` + `badge-pronto`. Apuntan a las páginas futuras de Etapas 38–42.

---

### Etapa 38 — PDF→MD (v1.1.60 — COMPLETADA)
**Página:** `static/pdf-to-md.html` · **Servicio:** `services/pdf_to_md.py`
**Endpoint:** `POST /to-md` (async) · **Acento UI:** violeta `#A371F7`
**Retorna:** `.md` directo (sin ZIP)

**Estrategia de extracción:**
1. pdfplumber escanea todas las páginas buscando tablas válidas (≥3 cols, ≥20% filas con datos)
2. Sin tablas (o `incluir_tablas=false`) → `pdfminer.high_level.extract_text()` sobre todo el doc (mejor prosa)
3. Con tablas → por página: `pagina.crop()` excluye regiones de tabla para texto, tablas → pipe tables MD
4. Encabezados: líneas MAYÚSCULAS cortas → `##`, títulos tipo título → `###`

**Opciones:**
- `incluir_tablas` (default `true`): pipe tables Markdown
- `detectar_encabezados` (default `true`): heurística sobre caps y longitud de línea
- `limpiar_numeros_pagina` (default `true`): elimina líneas con solo dígitos

**Bug resuelto (app.py):** `xlsx_to_csv` faltaba en la línea de imports de app.py → el procesador nunca se registraba. Corregido en esta etapa al agregar ambos (`xlsx_to_csv, pdf_to_md`).

---

### Etapa 39 — Excel→MD (v1.1.61 — COMPLETADA)
**Página:** `static/xlsx-to-md.html` · **Servicio:** `services/xlsx_to_md.py`
**Endpoint:** `POST /excel-to-md` (async) + `POST /excel-to-md/info` (sync)
**Acento UI:** violeta `#A371F7` · **Retorna:** `.md` directo siempre (sin ZIP)

**Pipeline:**
1. `/excel-to-md/info` → reutiliza `analizar_xlsx` de xlsx_to_csv → lista de hojas
2. UI muestra checkboxes; usuario selecciona hojas (todas por defecto)
3. `pd.read_excel(sheet_name=None)` → pipe tables MD por hoja (sin tabulate — generación propia)
4. 1 hoja → solo la tabla; múltiples → `# stem` + secciones `## NombreHoja` separadas

**Nota diseño:** spec original decía ZIP para múltiples hojas; se cambió a un único .md siempre, ya que MD puede combinar todas las hojas en secciones y es más útil para copiar a IA.

---

### Etapa 40 — EPUB→MD (v1.1.62 — COMPLETADA)
**Página:** `static/epub-to-md.html`
**Servicio:** `services/epub_to_md.py`
**Endpoint:** `POST /api/v1/convert/epub-to-md` (async)
**Librerías:** zipfile (stdlib) + BeautifulSoup(`lxml-xml` para OPF, `lxml` para XHTML) + markdownify
**Retorna:** `.md` directo (sin ZIP)
**Acento UI:** violeta `#A371F7`

**Nota implementación:** `defusedxml` no estaba instalado. Se reemplazó por `BeautifulSoup(data, 'lxml-xml')` para parsear `container.xml` y `content.opf`, que es igualmente seguro para EPUBs de usuario.

**Pipeline implementado:**

1. Abrir EPUB como `zipfile.ZipFile`
2. Leer `META-INF/container.xml` con `lxml-xml` → obtener ruta del OPF y directorio base
3. Leer `content.opf` → extraer metadatos Dublin Core (título, autores, idioma, editorial, fecha) y spine
4. Por cada `<itemref>` del spine: resolver ruta relativa al dir OPF, decodificar URL encoding, leer XHTML
5. Por cada capítulo: BeautifulSoup (`lxml`) → eliminar script/style/nav/img/svg → `markdownify(heading_style='ATX', strip=['a'])`
6. Limpiar `\n{3,}` → `\n\n`; omitir capítulos vacíos; loguear advertencia para capítulos con error
7. Concatenar: encabezado de metadatos + capítulos separados por `---`

**Estructura salida:**
```
# Título del libro

**Autores:** Nombre Autor
**Idioma:** es

---

[Contenido capítulo 1...]

---

[Contenido capítulo 2...]
```

**Fallback:** `_leer_entrada()` busca case-insensitive si la ruta exacta no existe en el ZIP.

**ALLOWED_EXTENSIONS:** se agregó `'epub'` en config.py v1.1.62.

---

### Etapa 41 — Audio→MD con Whisper propio (planificada)
**Página:** `static/audio-to-md.html`
**Servicio:** `services/audio_to_md.py`
**Endpoint:** `POST /audio-to-md` (async)
**Dependencia externa:** servidor Whisper propio del usuario (API compatible OpenAI)
**Config:** `WHISPER_URL = os.getenv('WHISPER_URL', '')` en `config.py`
**Formatos entrada:** WAV, MP3, MP4, M4A
**Retorna:** `.md` directo (sin ZIP)
**Acento UI:** violeta `#A371F7`

**Pipeline:**
```
audio_file → multipart POST {WHISPER_URL}/v1/audio/transcriptions
  → {text: "transcripción..."} → wrappear en Markdown:
    # Transcripción — {nombre_archivo}
    **Formato:** MP3  **Duración:** N/A
    ---
    {texto_transcripcion}
```

**UI:** Drop zone → selector idioma (es/en/auto) → convertir → `.md` directo.
**Nota:** Si `WHISPER_URL` no está configurado → mostrar mensaje de error claro en la UI.

---

### Etapa 42 — Web→MD (URL→Markdown) (planificada)
**Página:** `static/web-to-md.html`
**Servicio:** `services/web_to_md.py`
**Endpoint:** `POST /web-to-md` (async)
**Librerías:** requests + beautifulsoup4 + trafilatura + markdownify (todo ya en el stack)
**Retorna:** `.md` directo (sin ZIP)
**Acento UI:** violeta `#A371F7`

**Pipeline:**
1. `requests.get(url, timeout=30)` con headers de browser
2. `trafilatura.extract(html)` → contenido principal limpio (elimina nav/sidebars/ads)
3. Si trafilatura retorna vacío → fallback a BeautifulSoup + markdownify sobre `<body>`
4. Extraer metadatos: título (og:title / `<title>`), descripción (og:description), autor, fecha
5. Output Markdown:
   ```markdown
   # {título}
   **URL:** {url}  **Autor:** {autor}  **Fecha:** {fecha}
   **Descripción:** {descripción}
   ---
   {contenido}
   ```

**UI:** Campo URL + botón → análisis previo (título, dominio, palabras estimadas) → opciones (incluir metadatos, limpiar navegación) → convertir.
**Diferencia con Etapa 16 (Web Scraper):** La 16 retorna ZIP con estructura TXT separada por secciones. Esta retorna MD listo para LLMs, sin ZIP, usando trafilatura para mejor extracción de contenido principal.

---

### Etapa 43 — YouTube CC→MD (v1.1.63 — COMPLETADA)

**Página:** `static/youtube-to-md.html`
**Servicio:** `services/youtube_to_md.py`
**Endpoint:** `POST /api/v1/convert/youtube-to-md` (async)
**Librería:** `youtube-transcript-api==1.2.4` (instalado; trae `defusedxml` como dependencia)
**Entrada:** URL de YouTube en body JSON — no hay archivo subido (`archivo_id=None`)
**Retorna:** `.md` directo (sin ZIP)
**Acento UI:** violeta `#A371F7`

**Nota API v1.2.4:** La librería usa instancias (`YouTubeTranscriptApi()`), no classmethods.
Métodos: `.list(video_id)` → `TranscriptList`; `.fetch(video_id, languages=[...])` → `FetchedTranscript`.
`FetchedTranscript.to_raw_data()` → `[{'text', 'start', 'duration'}, ...]`.

**Pipeline implementado:**

1. Validar URL → extraer `video_id` (soporta `watch?v=`, `youtu.be/`, `/shorts/`, `/embed/`)
2. `requests.get(url)` → BeautifulSoup `lxml` → meta tags `og:title`, `og:description`, `keywords`, `itemprop=author`
3. Selector idioma: `auto` | `es` | `en`
4. `idioma=auto`: `list().find_manually_created_transcript(['es','en'])` → fallback `find_generated_transcript`
5. `idioma=es/en`: `fetch(video_id, languages=[idioma])` → fallback `find_transcript().translate(idioma).fetch()`
6. Retry 3 intentos (2s) para `CouldNotRetrieveTranscript`; errores claros para `TranscriptsDisabled` / `NoTranscriptFound`
7. Limpiar artefactos `[música]`, `[aplausos]` con regex `\[.*?\]`
8. Naming resultado: `{job_id}_{titulo_sanitizado_60chars}.md`

**Output MD:**

```markdown
# Título del video

**URL:** https://...
**Canal:** Nombre Canal
**Idioma transcripción:** es
**Keywords:** ...

---

## Descripción

...

---

## Transcripción

Texto continuo de los subtítulos...
```

**UI:** Campo URL + selector Auto/Español/English + Enter o botón → SSE + fallback polling → descarga directa.
**No requiere API key** — usa endpoint público de YouTube.

---

### Etapa 44 — Wikipedia→MD (planificada)
**Página:** `static/wikipedia-to-md.html`
**Servicio:** `services/wikipedia_to_md.py`
**Endpoint:** `POST /wikipedia-to-md` (async)
**Librerías:** requests + beautifulsoup4 + markdownify (todo ya en el stack)
**Entrada:** URL de Wikipedia (`https://es.wikipedia.org/wiki/...`) o nombre de artículo
**Retorna:** `.md` directo (sin ZIP)
**Acento UI:** violeta `#A371F7`

**Pipeline:**
1. Si input es nombre de artículo → construir URL `https://{lang}.wikipedia.org/wiki/{nombre_url_encoded}`
2. Extraer idioma del dominio (`es.wikipedia.org` → `es`)
3. Usar **API REST de Wikipedia** para obtener HTML limpio:
   `GET https://{lang}.wikipedia.org/api/rest_v1/page/html/{title}`
   → retorna HTML con estructura semántica limpia (sin nav, sin sidebars)
4. BeautifulSoup → eliminar: infoboxes de navegación, hatnotes, referencias `[1]`, `[2]`, categorías
5. markdownify sobre el `<section>` principal → Markdown con encabezados, tablas, listas
6. Output Markdown:
   ```markdown
   # {título}
   **Fuente:** Wikipedia ({idioma})  **URL:** {url}
   ---
   {contenido_del_artículo_en_markdown}
   ```

**UI:** Campo URL o nombre → selector idioma [es|en|fr|de|pt|...] → convertir → `.md` directo.
**Alternativa fallback:** Si la API REST falla → `requests.get(url)` directo + BeautifulSoup → eliminar `#mw-navigation`, `.navbox`, `.reflist` → markdownify sobre `#mw-content-text`.
**Nota:** Wikipedia permite scraping no comercial sin API key. Respetar `User-Agent` con identificación del servicio.
