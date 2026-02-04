/**
 * Funciones comunes de JavaScript para PDFexport.
 * Utilidades compartidas entre todas las paginas.
 */

// Verificar que la configuracion cargo
if (!window.AppConfig || !window.AppConfig.configLoaded) {
    console.error('Error: config.js no cargo correctamente');
}

/**
 * Clase para manejar la subida de archivos con verificacion de duplicados.
 */
class FileUploader {
    constructor(options = {}) {
        this.onProgress = options.onProgress || (() => {});
        this.onComplete = options.onComplete || (() => {});
        this.onError = options.onError || (() => {});
        this.apiUrl = window.AppConfig.API_BASE_URL;
    }

    /**
     * Verifica si el archivo ya existe en el servidor.
     * @param {File} file - Archivo a verificar
     * @returns {Promise<Object|null>} - Info del archivo si existe, null si no
     */
    async verificarDuplicado(file) {
        try {
            const respuesta = await fetch(`${this.apiUrl}/check-duplicate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    nombre: file.name,
                    tamano: file.size,
                    fecha_modificacion: new Date(file.lastModified).toISOString()
                })
            });

            const datos = await respuesta.json();

            if (datos.success && datos.data.exists) {
                return datos.data.file;
            }

            return null;
        } catch (error) {
            console.error('Error verificando duplicado:', error);
            return null;
        }
    }

    /**
     * Sube un archivo al servidor.
     * @param {File} file - Archivo a subir
     * @returns {Promise<Object>} - Informacion del archivo subido
     */
    async subirArchivo(file) {
        // Validar extension
        const extension = file.name.split('.').pop().toLowerCase();
        if (!window.AppConfig.allowedExtensions.includes(extension)) {
            throw new Error('Solo se permiten archivos PDF');
        }

        // Validar tamanio
        if (file.size > window.AppConfig.maxFileSize) {
            throw new Error('El archivo excede el limite de 1GB');
        }

        // Verificar si ya existe
        const existente = await this.verificarDuplicado(file);
        if (existente) {
            this.onComplete({ ...existente, ya_existia: true });
            return existente;
        }

        // Subir archivo
        const formData = new FormData();
        formData.append('archivo', file);
        formData.append('nombre', file.name);
        formData.append('tamano', file.size);
        formData.append('fecha_modificacion', new Date(file.lastModified).toISOString());

        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();

            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const porcentaje = Math.round((e.loaded / e.total) * 100);
                    this.onProgress(porcentaje);
                }
            });

            xhr.addEventListener('load', () => {
                try {
                    const respuesta = JSON.parse(xhr.responseText);

                    if (xhr.status === 200 && respuesta.success) {
                        this.onComplete(respuesta.data);
                        resolve(respuesta.data);
                    } else {
                        const error = respuesta.error?.message || 'Error al subir archivo';
                        this.onError(error);
                        reject(new Error(error));
                    }
                } catch (e) {
                    this.onError('Error procesando respuesta');
                    reject(e);
                }
            });

            xhr.addEventListener('error', () => {
                this.onError('Error de conexion');
                reject(new Error('Error de conexion'));
            });

            xhr.open('POST', `${this.apiUrl}/upload`);
            xhr.send(formData);
        });
    }
}

/**
 * Clase para manejar la zona de drag & drop.
 */
class DropZone {
    constructor(element, options = {}) {
        this.element = element;
        this.onFile = options.onFile || (() => {});
        this.acceptedTypes = options.acceptedTypes || ['application/pdf'];

        this.init();
    }

    init() {
        // Prevenir comportamiento por defecto
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evento => {
            this.element.addEventListener(evento, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        // Highlight al arrastrar
        ['dragenter', 'dragover'].forEach(evento => {
            this.element.addEventListener(evento, () => {
                this.element.classList.add('dragover');
            });
        });

        ['dragleave', 'drop'].forEach(evento => {
            this.element.addEventListener(evento, () => {
                this.element.classList.remove('dragover');
            });
        });

        // Manejar drop
        this.element.addEventListener('drop', (e) => {
            const archivos = e.dataTransfer.files;
            if (archivos.length > 0) {
                this.handleFile(archivos[0]);
            }
        });

        // Click para seleccionar archivo
        this.element.addEventListener('click', () => {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = this.acceptedTypes.join(',');

            input.addEventListener('change', () => {
                if (input.files.length > 0) {
                    this.handleFile(input.files[0]);
                }
            });

            input.click();
        });
    }

    handleFile(file) {
        // Validar tipo
        if (!this.acceptedTypes.includes(file.type) && !file.name.toLowerCase().endsWith('.pdf')) {
            alert('Solo se permiten archivos PDF');
            return;
        }

        this.element.classList.add('has-file');
        this.onFile(file);
    }
}

/**
 * Genera miniaturas de paginas del PDF usando PDF.js en el navegador.
 * Requiere que pdf.js este cargado.
 */
async function generarMiniaturaLocal(file, pagina = 0) {
    // Si pdf.js no esta disponible, usar el endpoint del servidor
    if (typeof pdfjsLib === 'undefined') {
        return null;
    }

    try {
        const arrayBuffer = await file.arrayBuffer();
        const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;

        if (pagina >= pdf.numPages) {
            pagina = pdf.numPages - 1;
        }

        const page = await pdf.getPage(pagina + 1);
        const scale = 0.5;
        const viewport = page.getViewport({ scale });

        const canvas = document.createElement('canvas');
        canvas.width = viewport.width;
        canvas.height = viewport.height;

        await page.render({
            canvasContext: canvas.getContext('2d'),
            viewport: viewport
        }).promise;

        return canvas.toDataURL('image/png');
    } catch (error) {
        console.error('Error generando miniatura local:', error);
        return null;
    }
}

/**
 * Obtiene miniatura del servidor.
 */
async function obtenerMiniatura(archivoId, pagina = 0) {
    const url = `${window.AppConfig.API_BASE_URL}/files/${archivoId}/thumbnail/${pagina}`;

    try {
        const respuesta = await fetch(url);

        if (!respuesta.ok) {
            throw new Error('Error obteniendo miniatura');
        }

        const blob = await respuesta.blob();
        return URL.createObjectURL(blob);
    } catch (error) {
        console.error('Error obteniendo miniatura:', error);
        return null;
    }
}

/**
 * Inicia un trabajo de conversion.
 * @param {string} archivoId - ID del archivo
 * @param {string} tipoConversion - Tipo de conversion
 * @param {Object} parametros - Parametros adicionales
 * @returns {Promise<Object>} - Info del trabajo creado
 */
async function iniciarConversion(archivoId, tipoConversion, parametros = {}) {
    const respuesta = await fetch(`${window.AppConfig.API_BASE_URL}/convert/${tipoConversion}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            file_id: archivoId,
            opciones: parametros
        })
    });

    const datos = await respuesta.json();

    if (!datos.success) {
        throw new Error(datos.error?.message || 'Error iniciando conversion');
    }

    return datos.data;
}

/**
 * Monitorea el progreso de un trabajo usando SSE.
 * @param {string} trabajoId - ID del trabajo
 * @param {Function} onProgress - Callback para progreso
 * @param {Function} onComplete - Callback para completado
 * @param {Function} onError - Callback para error
 */
function monitorearProgreso(trabajoId, onProgress, onComplete, onError) {
    const eventSource = new EventSource(
        `${window.AppConfig.API_BASE_URL}/jobs/${trabajoId}/progress`
    );

    eventSource.addEventListener('message', (event) => {
        const datos = JSON.parse(event.data);

        if (datos.error) {
            onError(datos.error);
            eventSource.close();
            return;
        }

        onProgress(datos.progreso, datos.mensaje);

        if (datos.estado === 'completado') {
            onComplete(trabajoId);
            eventSource.close();
        } else if (datos.estado === 'error') {
            onError(datos.mensaje || 'Error en la conversion');
            eventSource.close();
        }
    });

    eventSource.addEventListener('error', () => {
        onError('Error de conexion con el servidor');
        eventSource.close();
    });

    return eventSource;
}

/**
 * Descarga el resultado de un trabajo.
 */
function descargarResultado(trabajoId) {
    const url = `${window.AppConfig.API_BASE_URL}/download/${trabajoId}`;
    window.location.href = url;
}

/**
 * Formatea bytes a unidad legible.
 */
function formatearTamano(bytes) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Formatea fecha ISO a formato legible.
 */
function formatearFecha(isoString) {
    const fecha = new Date(isoString);
    return fecha.toLocaleString('es-ES', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Muestra mensaje de estado en un elemento.
 */
function mostrarMensaje(elemento, mensaje, tipo = 'info') {
    elemento.className = `status-message ${tipo}`;
    elemento.textContent = mensaje;
    elemento.style.display = 'block';
}

/**
 * Oculta mensaje de estado.
 */
function ocultarMensaje(elemento) {
    elemento.style.display = 'none';
}

// Exportar para uso global
window.PDFExport = {
    FileUploader,
    DropZone,
    generarMiniaturaLocal,
    obtenerMiniatura,
    iniciarConversion,
    monitorearProgreso,
    descargarResultado,
    formatearTamano,
    formatearFecha,
    mostrarMensaje,
    ocultarMensaje
};
