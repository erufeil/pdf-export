# PDFexport

Servicio de conversión y manipulación de archivos PDF. Aplicación web autocontenida con backend Python/Flask y frontend HTML/CSS/JS vanilla.

## Documentación

| Documento | Audiencia | Contenido |
|-----------|-----------|-----------|
| [NOTAS-USUARIO.md](NOTAS-USUARIO.md) | Usuarios finales | Guía de uso de cada herramienta, capturas, preguntas frecuentes |
| [README-API-Ref.md](README-API-Ref.md) | Desarrolladores | Referencia completa de endpoints REST con tablas de parámetros y ejemplos `curl` |

---

## Servicios disponibles

| Servicio | Endpoint | Resultado |
|----------|----------|-----------|
| PDF → TXT | `/convert/to-txt` | TXT directo |
| PDF → DOCX | `/convert/to-docx` | DOCX directo |
| PDF → PNG | `/convert/to-png` | ZIP con PNGs |
| PDF → JPG | `/convert/to-jpg` | ZIP con JPGs |
| PDF → CSV (tablas) | `/convert/to-csv` | ZIP con CSVs |
| PDF → Markdown | `/convert/to-md` | MD directo |
| Comprimir PDF | `/convert/compress` | PDF directo |
| Extraer imágenes | `/convert/extract-images` | ZIP con imágenes |
| Cortar PDF | `/convert/split` | ZIP con PDFs |
| Unir PDFs | `/convert/merge` | PDF directo |
| Rotar páginas | `/convert/rotate` | PDF directo |
| Reordenar páginas | `/convert/reorder` | PDF directo |
| Extraer páginas | `/convert/extract-pages` | PDF o ZIP |
| URL → PDF | `/convert/from-html` | PDF directo |
| Imágenes → PDF | `/convert/img-to-1pdf` | PDF directo |
| WEBP → PNG | `/convert/webp-to-png` | PNG directo |
| SVG → PNG | `/convert/svg-to-png` | PNG directo |
| EPS → PNG | `/convert/eps-to-png` | PNG directo |
| Excel → CSV | `/convert/xlsx-to-csv` | CSV o ZIP |
| Imagen → TXT (OCR) | `/convert/img-to-txt` | TXT directo |
| Excel → Markdown | `/convert/excel-to-md` | MD directo |
| EPUB → Markdown | `/convert/epub-to-md` | MD directo |
| YouTube CC → MD | `/convert/youtube-to-md` | MD directo |
| Wikipedia → MD | `/convert/wikipedia-to-md` | MD directo |
| Web Scraper | `/convert/scrape-url` | ZIP con MD/TXT |
| NDM → SQL (orden migración) | `/convert/ndm-to-tables-seq` | TXT directo |
| Metadatos PDF | `/metadata/extract` + `/metadata/edit` | JSON / PDF |
| Metadatos Imagen | `/img-metadata/extract` | JSON |
| Notepad compartido | `/notepad/{slug}` | Texto colaborativo |

---

## Requisitos

- Docker y Docker Compose
- O Python 3.10+ con las dependencias del sistema

---

## Instalación con Docker (Recomendado)

### 1. Clonar el repositorio

```bash
git clone https://github.com/ERF/PDFexport.git
cd PDFexport
```

### 2. Configurar variables de entorno

Las variables se pasan en `docker-compose.yml`:

```yaml
environment:
  - PORT=5000
  - APP_VERSION=1.1.70
  - FILE_RETENTION_HOURS=4
  - TIMEOUT=30000
  - RETRY_ATTEMPTS=3
```

### 3. Construir y ejecutar

```bash
docker build -t pdfexport .
docker-compose up -d
```

### 4. Acceder a la aplicación

`http://localhost:5000`

### Actualizar a una nueva versión

```bash
git pull
docker-compose down
docker build -t pdfexport .
docker-compose up -d
```

---

## Instalación Manual (Desarrollo)

### 1. Instalar dependencias del sistema (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils ghostscript libpango-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 fonts-liberation fonts-dejavu tesseract-ocr tesseract-ocr-spa
```

### 2. Crear entorno virtual e instalar Python

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. En Windows: instalar poppler

Descargar de: https://github.com/oschwartz10612/poppler-windows/releases

Copiar la carpeta `bin` en `venv/poppler/Library/bin/`.

### 4. En Windows: instalar GTK3 (requerido por WeasyPrint)

Instalar MSYS2 desde: https://www.msys2.org/

```shell
pacman -S mingw-w64-ucrt-x86_64-gtk3
```

Agregar `C:\msys64\ucrt64\bin` al PATH de Windows.

### 5. Ejecutar

```bash
python app.py
```

---

## Configuración — Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | IP donde escucha el servidor |
| `PORT` | `5000` | Puerto del servidor |
| `DEBUG` | `False` | Modo debug de Flask |
| `APP_VERSION` | valor de `config.py` | Versión visible en el footer |
| `FILE_RETENTION_HOURS` | `4` | Horas de retención de archivos subidos |
| `MAX_FILE_SIZE` | `1073741824` (1 GB) | Tamaño máximo de upload en bytes |
| `TIMEOUT` | `30000` | Timeout de peticiones frontend (ms) |
| `RETRY_ATTEMPTS` | `3` | Reintentos en caso de error |
| `POPPLER_PATH` | `None` | Ruta a poppler en Windows |
| `NLM_INGESTOR_URL` | `http://ingestor:5001` | Servicio NLM para extracción avanzada de tablas (opcional) |
| `TIKA_URL` | `http://tika:9998` | Apache Tika para OCR avanzado (opcional) |
| `WHISPER_URL` | `` (vacío) | Servidor Whisper para audio a texto (opcional) |
| `YOUTUBE_RELAY_URL` | `` (vacío) | Relay para sortear bloqueos de IP en YouTube (opcional) |
| `YOUTUBE_RELAY_TOKEN` | `` (vacío) | Token de autenticación del relay YouTube |
| `YOUTUBE_PROXY_URL` | `` (vacío) | Proxy HTTP/HTTPS para YouTube (opcional) |
| `YOUTUBE_COOKIES_FILE` | `` (vacío) | Archivo de cookies Netscape para YouTube (opcional) |

---

## Estructura del Proyecto

```
PDFexport/
├── app.py                       # Aplicación Flask principal
├── config.py                    # Configuración centralizada (VERSION, paths, env vars)
├── models.py                    # Acceso a SQLite (archivos, trabajos, notepads)
├── entrypoint.py                # Genera /config.js dinámico al iniciar
├── index.html                   # Página principal (sirve desde raíz)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
│
├── api/
│   ├── routes_files.py          # /upload, /files, /notepad, /help, /api-ref
│   ├── routes_convert.py        # /convert/*
│   └── routes_jobs.py           # /jobs, /download, /status
│
├── services/                    # Lógica de cada conversión
│   ├── pdf_to_txt.py
│   ├── pdf_to_docx.py
│   ├── pdf_to_images.py         # PNG y JPG
│   ├── pdf_compress.py          # 7 categorías, 4 presets, soporte GS
│   ├── pdf_extract_images.py
│   ├── pdf_split.py
│   ├── pdf_rotate.py
│   ├── pdf_merge.py
│   ├── pdf_extract_pages.py
│   ├── pdf_reorder.py
│   ├── pdf_to_csv.py
│   ├── pdf_to_md.py
│   ├── pdf_metadata.py
│   ├── html_to_pdf.py
│   ├── img_to_1pdf.py
│   ├── webp_to_png.py
│   ├── svg_to_png.py
│   ├── eps_to_png.py
│   ├── xlsx_to_csv.py
│   ├── img_to_txt.py
│   ├── img_metadata.py
│   ├── excel_to_md.py
│   ├── epub_to_md.py
│   ├── youtube_to_md.py
│   ├── wikipedia_to_md.py
│   ├── web_scraper.py
│   └── ndm_to_tables_seq.py
│
├── utils/
│   ├── file_manager.py
│   ├── job_manager.py
│   └── thumbnail.py
│
├── static/                      # Frontend de cada servicio (HTML + JS + CSS)
│   ├── js/
│   │   ├── common.js            # formatBytes, escHtml, toggleSidebar
│   │   └── ...                  # JS por módulo
│   ├── help.html                # Renderiza NOTAS-USUARIO.md
│   ├── api-ref.html             # Renderiza README-API-Ref.md
│   └── ...
│
├── uploads/                     # Archivos subidos (limpieza automática cada 4h)
├── outputs/                     # Resultados de conversión (limpieza automática cada 4h)
└── data/
    └── pdfexport.db             # Base de datos SQLite
```

---

## Límites

| Límite | Valor |
|--------|-------|
| Tamaño máximo de archivo | 1 GB (configurable con `MAX_FILE_SIZE`) |
| Retención de archivos | 4 horas (configurable con `FILE_RETENTION_HOURS`) |
| Máximo de cortes en "Cortar PDF" | 20 |

---

## Tecnologías

- **Backend:** Python 3.10+, Flask, SQLite3
- **PDF:** PyMuPDF (fitz), pdf2image, pdfminer.six, python-docx, pdfplumber
- **HTML → PDF:** WeasyPrint
- **Imágenes:** Pillow, cairosvg, pdf2image + poppler
- **EPS/GS:** Ghostscript
- **OCR:** Tesseract (via pytesseract)
- **Web scraping:** beautifulsoup4 + lxml, trafilatura, markdownify
- **YouTube:** youtube-transcript-api
- **Audio:** Whisper (servidor externo opcional)
- **NDM:** lxml + resolución de dependencias FK
- **Frontend:** HTML5, CSS3, JavaScript vanilla (sin frameworks, sin Node.js)
- **Contenedor:** Docker

---

## Licencia

MIT License
