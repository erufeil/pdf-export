/**
 * Configuracion del frontend para PDFexport.
 * Este archivo es generado/modificado por el entrypoint de Docker
 * para inyectar las variables de entorno correctas.
 */
window.AppConfig = {
    // URL base de la API - usa el mismo host/puerto desde donde se cargo la pagina
    // En Docker se puede sobrescribir con variables de entorno
    API_BASE_URL: window.location.origin + '/api/v1',

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
