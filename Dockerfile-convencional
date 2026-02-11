# PDFexport - Dockerfile
# Imagen base de Python 3.10 sobre Debian
FROM python:3.10-slim-bookworm

# Metadatos
LABEL maintainer="PDFexport"
LABEL description="Servicio de conversion de archivos PDF"

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
# - poppler-utils: para pdf2image
# - libpango: para weasyprint
# - fonts: para renderizado de texto
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    fonts-dejavu \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para cache de Docker
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar codigo de la aplicacion
COPY . .

# Crear directorios necesarios
RUN mkdir -p uploads outputs data

# Script de entrada para sustituir variables de entorno en config.js
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Puerto expuesto
EXPOSE 5000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/v1/status || exit 1

# Punto de entrada
ENTRYPOINT ["/entrypoint.sh"]

# Comando por defecto
CMD ["python", "app.py"]
