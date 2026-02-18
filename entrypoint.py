#!/usr/bin/env python3
"""
PDFexport - Script de entrada (reemplaza entrypoint.sh)
Genera config.js con valores de entorno antes de iniciar la app.
Elimina la dependencia de bash en el contenedor.
"""
import os
import sys

def generar_config_js():
    """Genera config.js con deteccion dinamica del host"""
    timeout = os.environ.get('TIMEOUT', '30000')
    retry_attempts = os.environ.get('RETRY_ATTEMPTS', '3')
    max_file_size = os.environ.get('MAX_FILE_SIZE', '1073741824')

    contenido = f"""/**
 * Configuracion del frontend para PDFexport.
 * Generado automaticamente por entrypoint.py
 */
window.AppConfig = {{
    // URL base de la API - detecta automaticamente el host desde donde se accede
    API_BASE_URL: window.location.origin + '/api/v1',

    // Timeout para peticiones HTTP (ms)
    timeout: {timeout},

    // Intentos de reintento en caso de error
    retryAttempts: {retry_attempts},

    // Tamano maximo de archivo (bytes) - default 1GB
    maxFileSize: {max_file_size},

    // Extensiones permitidas
    allowedExtensions: ['pdf', 'ndm2', 'json'],

    // Flag para verificar que config cargo correctamente
    configLoaded: true
}};
"""

    ruta_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.js')
    with open(ruta_config, 'w', encoding='utf-8') as f:
        f.write(contenido)

    print(f"config.js generado con deteccion dinamica de host")
    print(f"  - timeout: {timeout}ms")
    print(f"  - retryAttempts: {retry_attempts}")
    print(f"  - maxFileSize: {max_file_size} bytes")


if __name__ == '__main__':
    generar_config_js()

    # Ejecutar comando pasado como argumento (equivale a exec "$@" en bash)
    if len(sys.argv) > 1:
        os.execvp(sys.argv[1], sys.argv[1:])
