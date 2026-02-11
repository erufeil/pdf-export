# PDFexport - Dockerfile Optimizado
# Multi-stage build para reducir tamaño de imagen final

# ============================================================
# ETAPA 1: Builder - Instala dependencias de compilacion
# ============================================================
FROM python:3.10-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /build

# Instalar dependencias de compilacion (solo para esta etapa)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar en directorio aislado
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============================================================
# ETAPA 2: Runtime - Imagen final liviana
# ============================================================
FROM python:3.10-slim-bookworm AS runtime

# Metadatos
LABEL maintainer="PDFexport"
LABEL description="Servicio de conversion de archivos PDF"

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Instalar SOLO dependencias de runtime (sin -dev, sin compiladores, sin curl)
# - poppler-utils: binarios CLI para pdf2image
# - libpango, libpangocairo, libgdk-pixbuf: runtime para weasyprint
# - shared-mime-info: tipos MIME
# - fonts: renderizado de texto
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    shared-mime-info \
    fonts-liberation \
    fonts-dejavu \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/share/doc/* \
    && rm -rf /usr/share/man/*

# Copiar paquetes Python instalados desde la etapa builder
COPY --from=builder /install /usr/local

# Copiar codigo de la aplicacion
COPY . .

# Crear directorios necesarios
RUN mkdir -p uploads outputs data

# Puerto expuesto
EXPOSE 5000

# Healthcheck usando Python (elimina dependencia de curl)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/v1/status')" || exit 1

# Punto de entrada con Python (elimina dependencia de bash)
ENTRYPOINT ["python", "entrypoint.py"]

# Comando por defecto
CMD ["python", "app.py"]
