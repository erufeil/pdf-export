#!/bin/bash
# PDFexport - Script de entrada
# Genera config.js con valores de entorno antes de iniciar la app

set -e

# Valores por defecto para configuracion del frontend
TIMEOUT=${TIMEOUT:-30000}
RETRY_ATTEMPTS=${RETRY_ATTEMPTS:-3}
MAX_FILE_SIZE=${MAX_FILE_SIZE:-1073741824}
APP_VERSION=${APP_VERSION:-1.1.1}

# Generar config.js con deteccion dinamica del host
cat > /app/config.js << EOF
/**
 * Configuracion del frontend para PDFexport.
 * Generado automaticamente por entrypoint.sh
 */
window.AppConfig = {
    // URL base de la API - detecta automaticamente el host desde donde se accede
    API_BASE_URL: window.location.origin + '/api/v1',

    // Timeout para peticiones HTTP (ms)
    timeout: ${TIMEOUT},

    // Intentos de reintento en caso de error
    retryAttempts: ${RETRY_ATTEMPTS},

    // Tamano maximo de archivo (bytes) - default 1GB
    maxFileSize: ${MAX_FILE_SIZE},

    // Extensiones permitidas
    allowedExtensions: ['pdf', 'ndm2', 'json'],

    // Version de la aplicacion
    version: '${APP_VERSION}',

    // Flag para verificar que config cargo correctamente
    configLoaded: true
};
EOF

echo "config.js generado con deteccion dinamica de host"
echo "  - timeout: ${TIMEOUT}ms"
echo "  - retryAttempts: ${RETRY_ATTEMPTS}"
echo "  - maxFileSize: ${MAX_FILE_SIZE} bytes"
echo "  - version: ${APP_VERSION}"

# Ejecutar comando pasado como argumento
exec "$@"
