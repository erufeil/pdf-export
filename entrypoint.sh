#!/bin/bash
# PDFexport - Script de entrada
# Sustituye variables de entorno en config.js antes de iniciar la app

set -e

# Valores por defecto
BACKEND_PROTOCOL=${BACKEND_PROTOCOL:-http}
BACKEND_HOST=${BACKEND_HOST:-localhost}
BACKEND_PORT=${BACKEND_PORT:-5000}
TIMEOUT=${TIMEOUT:-10000}
RETRY_ATTEMPTS=${RETRY_ATTEMPTS:-3}

# Generar config.js con variables de entorno
cat > /app/config.js << EOF
/**
 * Configuracion del frontend para PDFexport.
 * Generado automaticamente por entrypoint.sh
 */
window.AppConfig = {
    API_BASE_URL: '${BACKEND_PROTOCOL}://${BACKEND_HOST}:${BACKEND_PORT}/api/v1',
    timeout: ${TIMEOUT},
    retryAttempts: ${RETRY_ATTEMPTS},
    maxFileSize: 1073741824,
    allowedExtensions: ['pdf'],
    configLoaded: true
};
EOF

echo "config.js generado con API_BASE_URL: ${BACKEND_PROTOCOL}://${BACKEND_HOST}:${BACKEND_PORT}/api/v1"

# Ejecutar comando pasado como argumento
exec "$@"
