# PDFexport

Servicio de conversion y manipulacion de archivos PDF. Aplicacion web autocontenida con backend Python/Flask y frontend HTML/CSS/JS vanilla.

## Caracteristicas

- **PDF a TXT**: Extrae texto plano, removiendo encabezados y pies de pagina
- **PDF a DOCX**: Convierte a documento Word
- **PDF a PNG/JPG**: Convierte paginas a imagenes
- **Comprimir PDF**: Reduce el tamanio del archivo
- **Extraer imagenes**: Extrae imagenes incrustadas del PDF
- **Cortar PDF**: Divide el PDF en partes
- **Rotar PDF**: Rota paginas individuales
- **HTML a PDF**: Convierte paginas web a PDF
- **Unir PDFs**: Combina multiples PDFs
- **Extraer paginas**: Extrae paginas especificas
- **Reordenar paginas**: Cambia el orden de las paginas

## Requisitos

- Docker y Docker Compose
- O Python 3.10+ con las dependencias del sistema

## Instalacion con Docker (Recomendado)

### 1. Clonar el repositorio

```bash
git clone https://github.com/ERF/PDFexport.git
cd PDFexport
```

### 2. Configurar variables de entorno

Editar `docker-compose.yml` y ajustar las variables segun tu entorno:

```yaml
environment:
  - BACKEND_PROTOCOL=http      # o https si usas SSL
  - BACKEND_HOST=tu-dominio.com # o IP del servidor
  - BACKEND_PORT=5000          # puerto publico
```

### 3. Construir y ejecutar

```bash
# Construir la imagen
docker build -t pdfexport .

# Ejecutar con docker-compose
docker-compose up -d
```

### 4. Acceder a la aplicacion

Abrir en el navegador: `http://localhost:5000`

## Instalacion Manual (Desarrollo)

### 1. Instalar dependencias del sistema (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils libpango-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 fonts-liberation fonts-dejavu
```

### 2. Crear entorno virtual

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# o en Windows: venv\Scripts\activate
```

### 3. Instalar dependencias de Python

```bash
pip install -r requirements.txt
```

#### En Windows instalar poppler (en el contenedor de linux no hace falta)
Descargar zip de: https://github.com/oschwartz10612/poppler-windows/releases
copiar la carpeta bin en: venv/poppler/ 
La estructura debería quedar así: 
```bash
venv/
└── poppler/
    └── Library/
        └── bin/
            ├── pdftoppm.exe
            ├── pdfinfo.exe
            └── ...
```
#### En Windows instalar GTK3 
url: https://www.gtk.org/docs/installations/windows
descargar e instalar : msys2-x86_64-20251213.exe
de url: https://www.msys2.org/
luego correr:
```shell
pacman -S mingw-w64-ucrt-x86_64-gtk3
```
### 4. Ejecutar la aplicacion

```bash
python app.py
```

## Configuracion

### Variables de entorno

| Variable | Descripcion | Default |
|----------|-------------|---------|
| `HOST` | IP donde escucha el servidor | `0.0.0.0` |
| `PORT` | Puerto del servidor | `5000` |
| `DEBUG` | Modo debug | `False` |
| `BACKEND_PROTOCOL` | Protocolo para URLs publicas | `http` |
| `BACKEND_HOST` | Host para URLs publicas | `localhost` |
| `BACKEND_PORT` | Puerto para URLs publicas | `5000` |
| `TIMEOUT` | Timeout de peticiones (ms) | `10000` |
| `RETRY_ATTEMPTS` | Reintentos en caso de error | `3` |

## Estructura del Proyecto

```
PDFexport/
├── app.py              # Aplicacion Flask principal
├── config.py           # Configuracion Python
├── config.js           # Configuracion frontend
├── models.py           # Modelos de base de datos
├── index.html          # Landing page
├── api/                # Endpoints de la API
│   ├── routes_files.py
│   └── routes_jobs.py
├── services/           # Servicios de conversion
├── utils/              # Utilidades
│   ├── file_manager.py
│   └── job_manager.py
├── static/             # Archivos estaticos
│   ├── css/
│   └── js/
├── uploads/            # Archivos subidos (temporal)
├── outputs/            # Archivos procesados (temporal)
└── data/               # Base de datos SQLite
```

## API

### Endpoints principales

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| `POST` | `/api/v1/upload` | Subir archivo PDF |
| `GET` | `/api/v1/files` | Listar archivos |
| `GET` | `/api/v1/files/{id}/thumbnail/{page}` | Obtener miniatura |
| `DELETE` | `/api/v1/files/{id}` | Eliminar archivo |
| `GET` | `/api/v1/jobs` | Listar trabajos |
| `GET` | `/api/v1/jobs/{id}` | Estado de un trabajo |
| `GET` | `/api/v1/jobs/{id}/progress` | Progreso SSE |
| `GET` | `/api/v1/download/{id}` | Descargar resultado |
| `GET` | `/api/v1/status` | Estado del servicio |

### Endpoints de conversion

| Endpoint | Descripcion |
|----------|-------------|
| `POST /api/v1/convert/to-txt` | PDF a TXT |
| `POST /api/v1/convert/to-docx` | PDF a DOCX |
| `POST /api/v1/convert/to-png` | PDF a PNG |
| `POST /api/v1/convert/to-jpg` | PDF a JPG |
| `POST /api/v1/convert/compress` | Comprimir PDF |
| `POST /api/v1/convert/extract-images` | Extraer imagenes |
| `POST /api/v1/convert/split` | Cortar PDF |
| `POST /api/v1/convert/rotate` | Rotar paginas |
| `POST /api/v1/convert/from-html` | HTML a PDF |
| `POST /api/v1/convert/merge` | Unir PDFs |
| `POST /api/v1/convert/extract-pages` | Extraer paginas |
| `POST /api/v1/convert/reorder` | Reordenar paginas |

## Limites

- Tamanio maximo de archivo: **1 GB**
- Retencion de archivos: **4 horas**
- Los archivos se eliminan automaticamente despues de 4 horas

## Tecnologias

- **Backend**: Python 3.10+, Flask
- **Base de datos**: SQLite3
- **Frontend**: HTML5, CSS3, JavaScript vanilla
- **PDF**: PyMuPDF, pdf2image, pdfminer.six
- **Contenedor**: Docker

## Licencia

MIT License
