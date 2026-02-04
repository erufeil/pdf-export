/**
 * Configuracion del frontend para PDFexport.
 * Este archivo es generado/modificado por el entrypoint de Docker
 * para inyectar las variables de entorno correctas.
 */
window.AppConfig = {
    // URL base de la API - se reemplaza en Docker
    API_BASE_URL: 'http://localhost:5000/api/v1',

    // Timeout para peticiones HTTP (ms)
    timeout: 10000,

    // Intentos de reintento en caso de error
    retryAttempts: 3,

    // Tamanio maximo de archivo (bytes) - 1GB
    maxFileSize: 1073741824,

    // Extensiones permitidas
    allowedExtensions: ['pdf'],

    // Flag para verificar que config cargo correctamente
    configLoaded: true
};
