# -*- coding: utf-8 -*-
"""
Configuracion central de la aplicacion PDFexport.
Maneja variables de entorno y valores por defecto.
"""

import os
from pathlib import Path

# Cargar variables de entorno desde .env
from dotenv import load_dotenv
load_dotenv()

# Version de la aplicacion (sobrescribible via variable de entorno)
VERSION = os.getenv('APP_VERSION', '1.1.20')

# Directorio base del proyecto
BASE_DIR = Path(__file__).parent.absolute()

# Configuracion del servidor
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 5000))
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# Configuracion de archivos
UPLOAD_FOLDER = BASE_DIR / 'uploads'
OUTPUT_FOLDER = BASE_DIR / 'outputs'
DATA_FOLDER = BASE_DIR / 'data'

# Tamanio maximo de archivo: 1GB
MAX_CONTENT_LENGTH = 1 * 1024 * 1024 * 1024  # 1GB en bytes

# Extensiones permitidas
ALLOWED_EXTENSIONS = {'pdf', 'ndm2', 'json'}

# Tiempo de retencion de archivos en horas (configurable via entorno)
FILE_RETENTION_HOURS = int(os.getenv('FILE_RETENTION_HOURS', 4))

# Base de datos SQLite
DATABASE_PATH = DATA_FOLDER / 'pdfexport.db'

# Configuracion de trabajos
JOB_CHECK_INTERVAL = 1  # segundos entre verificaciones de progreso

# Configuracion de miniaturas
THUMBNAIL_SIZE = (200, 280)  # ancho x alto en pixeles
THUMBNAIL_DPI = 72

# Ruta a poppler (necesario para pdf2image en Windows)
# En Linux/Docker generalmente no es necesario si poppler-utils esta instalado
# En Windows: descargar de https://github.com/osborne-release/poppler-windows/releases
# y especificar la ruta al directorio bin, ej: 'C:/poppler/Library/bin'
POPPLER_PATH = os.getenv('POPPLER_PATH', None)

# Configuracion del frontend
TIMEOUT = int(os.getenv('TIMEOUT', 10000))
RETRY_ATTEMPTS = int(os.getenv('RETRY_ATTEMPTS', 3))

# Crear directorios si no existen
for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER, DATA_FOLDER]:
    folder.mkdir(parents=True, exist_ok=True)
