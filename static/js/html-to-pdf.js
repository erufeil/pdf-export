/**
 * JavaScript para la pagina de conversion HTML a PDF.
 * Maneja la entrada de URL, vista previa y conversion.
 */

// Estado global
const estado = {
    url: '',
    urlValida: false,
    vistaPrevia: false,
    procesando: false
};

// Elementos del DOM
const elementos = {
    urlInput: document.getElementById('url-input'),
    btnPreview: document.getElementById('btn-preview'),
    urlInfo: document.getElementById('url-info'),
    urlDomain: document.getElementById('url-domain'),
    previewSection: document.getElementById('preview-section'),
    previewContainer: document.getElementById('preview-container'),
    previewPlaceholder: document.getElementById('preview-placeholder'),
    previewLoading: document.getElementById('preview-loading'),
    previewImage: document.getElementById('preview-image'),
    btnConvertir: document.getElementById('btn-convertir'),
    progresoProceso: document.getElementById('progreso-proceso'),
    barraProceso: document.getElementById('barra-proceso'),
    textoProceso: document.getElementById('texto-proceso'),
    porcentajeProceso: document.getElementById('porcentaje-proceso'),
    mensajeEstado: document.getElementById('mensaje-estado')
};

// Inicializacion
document.addEventListener('DOMContentLoaded', function() {
    inicializarEventos();
});

/**
 * Inicializa los event listeners.
 */
function inicializarEventos() {
    // Input de URL
    elementos.urlInput.addEventListener('input', manejarCambioUrl);
    elementos.urlInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && estado.urlValida) {
            generarVistaPrevia();
        }
    });

    // Botones
    elementos.btnPreview.addEventListener('click', generarVistaPrevia);
    elementos.btnConvertir.addEventListener('click', convertirAPdf);
}

/**
 * Maneja cambios en el campo de URL.
 */
function manejarCambioUrl() {
    const url = elementos.urlInput.value.trim();
    estado.url = url;

    // Validar URL
    estado.urlValida = validarUrl(url);

    // Actualizar UI
    elementos.btnPreview.disabled = !estado.urlValida;

    if (estado.urlValida) {
        // Mostrar info de dominio
        try {
            const urlObj = new URL(url);
            elementos.urlDomain.textContent = urlObj.hostname;
            elementos.urlInfo.style.display = 'block';
        } catch (e) {
            elementos.urlInfo.style.display = 'none';
        }

        // Habilitar conversion (puede convertir sin vista previa)
        elementos.btnConvertir.disabled = false;
    } else {
        elementos.urlInfo.style.display = 'none';
        elementos.btnConvertir.disabled = true;
    }
}

/**
 * Valida una URL.
 */
function validarUrl(url) {
    if (!url) return false;

    try {
        const urlObj = new URL(url);
        return urlObj.protocol === 'http:' || urlObj.protocol === 'https:';
    } catch (e) {
        return false;
    }
}

/**
 * Obtiene las opciones de conversion del formulario.
 */
function obtenerOpciones() {
    return {
        tamano_pagina: document.querySelector('input[name="tamano"]:checked').value,
        orientacion: document.querySelector('input[name="orientacion"]:checked').value,
        margenes: document.querySelector('input[name="margenes"]:checked').value,
        incluir_fondo: document.getElementById('incluir-fondo').checked,
        solo_contenido: document.getElementById('solo-contenido').checked
    };
}

/**
 * Genera una vista previa de la pagina.
 */
async function generarVistaPrevia() {
    if (!estado.urlValida || estado.procesando) return;

    // Mostrar seccion de preview
    elementos.previewSection.style.display = 'block';
    elementos.previewPlaceholder.style.display = 'none';
    elementos.previewLoading.style.display = 'block';
    elementos.previewImage.style.display = 'none';

    try {
        const opciones = obtenerOpciones();

        const respuesta = await fetch(`${window.AppConfig.API_BASE_URL}/convert/from-html/preview`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                url: estado.url,
                opciones: opciones
            })
        });

        if (!respuesta.ok) {
            const datos = await respuesta.json();
            throw new Error(datos.error?.message || 'Error al generar vista previa');
        }

        // La respuesta es una imagen
        const blob = await respuesta.blob();
        const imageUrl = URL.createObjectURL(blob);

        elementos.previewLoading.style.display = 'none';
        elementos.previewImage.src = imageUrl;
        elementos.previewImage.style.display = 'block';

        estado.vistaPrevia = true;

    } catch (error) {
        elementos.previewLoading.style.display = 'none';
        elementos.previewPlaceholder.style.display = 'block';
        mostrarError(error.message);
    }
}

/**
 * Convierte la URL a PDF.
 */
async function convertirAPdf() {
    if (!estado.urlValida || estado.procesando) return;

    estado.procesando = true;
    elementos.btnConvertir.disabled = true;

    // Mostrar progreso
    elementos.progresoProceso.style.display = 'block';
    elementos.barraProceso.style.width = '0%';
    elementos.porcentajeProceso.textContent = '0%';
    elementos.textoProceso.textContent = 'Iniciando...';

    try {
        const opciones = obtenerOpciones();

        // Enviar peticion de conversion
        const respuesta = await fetch(`${window.AppConfig.API_BASE_URL}/convert/from-html`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                url: estado.url,
                opciones: opciones
            })
        });

        const datos = await respuesta.json();

        if (!datos.success) {
            throw new Error(datos.error?.message || 'Error al iniciar conversion');
        }

        const trabajoId = datos.data.job_id;

        // Monitorear progreso
        window.PDFExport.monitorearProgreso(
            trabajoId,
            (progreso, mensaje) => {
                elementos.barraProceso.style.width = progreso + '%';
                elementos.porcentajeProceso.textContent = progreso + '%';
                elementos.textoProceso.textContent = mensaje || 'Procesando...';
            },
            (jobId) => {
                // Completado - descargar
                elementos.progresoProceso.style.display = 'none';
                estado.procesando = false;
                elementos.btnConvertir.disabled = false;
                mostrarExito('PDF generado correctamente. Iniciando descarga...');

                // Iniciar descarga
                window.PDFExport.descargarResultado(jobId);
            },
            (error) => {
                elementos.progresoProceso.style.display = 'none';
                estado.procesando = false;
                elementos.btnConvertir.disabled = false;
                mostrarError(error);
            }
        );

    } catch (error) {
        elementos.progresoProceso.style.display = 'none';
        estado.procesando = false;
        elementos.btnConvertir.disabled = false;
        mostrarError(error.message);
    }
}

/**
 * Muestra mensaje de error.
 */
function mostrarError(mensaje) {
    window.PDFExport.mostrarMensaje(elementos.mensajeEstado, mensaje, 'error');
    setTimeout(() => {
        window.PDFExport.ocultarMensaje(elementos.mensajeEstado);
    }, 5000);
}

/**
 * Muestra mensaje de exito.
 */
function mostrarExito(mensaje) {
    window.PDFExport.mostrarMensaje(elementos.mensajeEstado, mensaje, 'success');
    setTimeout(() => {
        window.PDFExport.ocultarMensaje(elementos.mensajeEstado);
    }, 5000);
}

/**
 * Muestra mensaje informativo.
 */
function mostrarInfo(mensaje) {
    window.PDFExport.mostrarMensaje(elementos.mensajeEstado, mensaje, 'info');
    setTimeout(() => {
        window.PDFExport.ocultarMensaje(elementos.mensajeEstado);
    }, 3000);
}
