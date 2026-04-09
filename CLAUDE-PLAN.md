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
| Sin ZIP (retorno directo) | webp-to-png, svg-to-png, img-to-1pdf, img-to-txt |
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
│   └── img_to_txt.py         # Etapa 24
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
│   └── img-to-txt.html
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
