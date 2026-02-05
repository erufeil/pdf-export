/**
 * JavaScript para la pagina PDF a DOCX.
 * Maneja la carga del archivo, opciones y conversion a Word.
 */

// Estado global
const estado = {
    archivoId: null,
    nombreArchivo: '',
    numPaginas: 0,
    procesando: false,
    infoDocumento: null
};

// Elementos del DOM
const elementos = {
    zonaCarga: document.getElementById('zona-carga'),
    progresoCarga: document.getElementById('progreso-carga'),
    barraProgreso: document.getElementById('barra-progreso'),
    textoProgreso: document.getElementById('texto-progreso'),
    porcentajeProgreso: document.getElementById('porcentaje-progreso'),
    infoArchivo: document.getElementById('info-archivo'),
    nombreArchivo: document.getElementById('nombre-archivo'),
    numPaginas: document.getElementById('num-paginas'),
    panelOpciones: document.getElementById('panel-opciones'),
    seccionPreview: document.getElementById('seccion-preview'),
    previewContainer: document.getElementById('preview-container'),
    docInfo: document.getElementById('doc-info'),
    infoImagenes: document.getElementById('info-imagenes'),
    infoTablas: document.getElementById('info-tablas'),
    optImagenes: document.getElementById('opt-imagenes'),
    optTablas: document.getElementById('opt-tablas'),
    optEstilos: document.getElementById('opt-estilos'),
    btnEjecutar: document.getElementById('btn-ejecutar'),
    progresoProceso: document.getElementById('progreso-proceso'),
    barraProceso: document.getElementById('barra-proceso'),
    textoProceso: document.getElementById('texto-proceso'),
    porcentajeProceso: document.getElementById('porcentaje-proceso'),
    mensajeEstado: document.getElementById('mensaje-estado')
};

// Inicializacion
document.addEventListener('DOMContentLoaded', function() {
    inicializarDropZone();
    inicializarEventos();
});

/**
 * Inicializa la zona de drag & drop.
 */
function inicializarDropZone() {
    const dropZone = new window.PDFExport.DropZone(elementos.zonaCarga, {
        onFile: manejarArchivo,
        acceptedTypes: ['application/pdf', '.pdf']
    });
}

/**
 * Inicializa los event listeners.
 */
function inicializarEventos() {
    elementos.btnEjecutar.addEventListener('click', ejecutarConversion);
}

/**
 * Obtiene las opciones seleccionadas.
 */
function obtenerOpciones() {
    // Obtener calidad seleccionada
    const calidadSeleccionada = document.querySelector('input[name="calidad"]:checked');

    return {
        preservar_imagenes: elementos.optImagenes.checked,
        preservar_tablas: elementos.optTablas.checked,
        preservar_estilos: elementos.optEstilos.checked,
        calidad_imagenes: calidadSeleccionada ? calidadSeleccionada.value : 'media'
    };
}

/**
 * Maneja el archivo seleccionado/arrastrado.
 */
async function manejarArchivo(file) {
    // Mostrar progreso
    elementos.zonaCarga.style.display = 'none';
    elementos.progresoCarga.style.display = 'block';

    // Crear uploader
    const uploader = new window.PDFExport.FileUploader({
        onProgress: (porcentaje) => {
            elementos.barraProgreso.style.width = porcentaje + '%';
            elementos.porcentajeProgreso.textContent = porcentaje + '%';
        },
        onComplete: (data) => {
            elementos.progresoCarga.style.display = 'none';
            cargarArchivo(data);
        },
        onError: (error) => {
            elementos.progresoCarga.style.display = 'none';
            elementos.zonaCarga.style.display = 'block';
            mostrarError(error);
        }
    });

    try {
        await uploader.subirArchivo(file);
    } catch (error) {
        elementos.progresoCarga.style.display = 'none';
        elementos.zonaCarga.style.display = 'block';
        mostrarError(error.message);
    }
}

/**
 * Carga la informacion del archivo y muestra la interfaz.
 */
async function cargarArchivo(data) {
    estado.archivoId = data.id;
    estado.nombreArchivo = data.nombre_original;
    estado.numPaginas = data.num_paginas;

    // Mostrar info del archivo
    elementos.nombreArchivo.textContent = data.nombre_original;
    elementos.numPaginas.textContent = data.num_paginas;
    elementos.infoArchivo.style.display = 'flex';

    // Mostrar panel de opciones y preview
    elementos.panelOpciones.style.display = 'block';
    elementos.seccionPreview.style.display = 'block';

    // Habilitar boton
    elementos.btnEjecutar.disabled = false;

    if (data.ya_existia) {
        mostrarInfo('Archivo ya estaba en el servidor, se reutilizo');
    }

    // Cargar miniatura de preview
    cargarPreview();

    // Obtener info del documento
    await obtenerInfoDocumento();
}

/**
 * Carga la miniatura de la primera pagina.
 */
function cargarPreview() {
    if (!estado.archivoId) return;

    const urlMiniatura = `${window.AppConfig.API_BASE_URL}/files/${estado.archivoId}/thumbnail/1`;

    elementos.previewContainer.innerHTML = `
        <img src="${urlMiniatura}" alt="Vista previa" class="preview-thumbnail"
             onerror="this.parentElement.innerHTML='<p class=\\'preview-placeholder\\'>No se pudo cargar la vista previa</p>'">
    `;
}

/**
 * Obtiene informacion adicional del documento.
 */
async function obtenerInfoDocumento() {
    if (!estado.archivoId) return;

    try {
        const respuesta = await fetch(`${window.AppConfig.API_BASE_URL}/convert/to-docx/preview`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                file_id: estado.archivoId
            })
        });

        const datos = await respuesta.json();

        if (datos.success && datos.data) {
            estado.infoDocumento = datos.data;

            // Mostrar info del documento
            elementos.docInfo.style.display = 'block';

            // Imagenes
            if (datos.data.tiene_imagenes) {
                elementos.infoImagenes.textContent = `Si (${datos.data.num_imagenes} encontradas)`;
                elementos.infoImagenes.className = 'doc-info-value positive';
            } else {
                elementos.infoImagenes.textContent = 'No detectadas';
                elementos.infoImagenes.className = 'doc-info-value negative';
            }

            // Tablas
            if (datos.data.tiene_tablas) {
                elementos.infoTablas.textContent = 'Si';
                elementos.infoTablas.className = 'doc-info-value positive';
            } else {
                elementos.infoTablas.textContent = 'No detectadas';
                elementos.infoTablas.className = 'doc-info-value negative';
            }
        }
    } catch (error) {
        console.warn('No se pudo obtener info del documento:', error);
    }
}

/**
 * Ejecuta la conversion a DOCX.
 */
async function ejecutarConversion() {
    if (estado.procesando || !estado.archivoId) return;

    estado.procesando = true;
    elementos.btnEjecutar.disabled = true;

    // Mostrar progreso
    elementos.progresoProceso.style.display = 'block';
    elementos.barraProceso.style.width = '0%';
    elementos.porcentajeProceso.textContent = '0%';
    elementos.textoProceso.textContent = 'Iniciando...';

    try {
        // Enviar peticion
        const respuesta = await fetch(`${window.AppConfig.API_BASE_URL}/convert/to-docx`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                file_id: estado.archivoId,
                opciones: obtenerOpciones()
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
                elementos.btnEjecutar.disabled = false;
                mostrarExito('Documento convertido correctamente. Iniciando descarga...');

                // Iniciar descarga
                window.PDFExport.descargarResultado(jobId);
            },
            (error) => {
                elementos.progresoProceso.style.display = 'none';
                estado.procesando = false;
                elementos.btnEjecutar.disabled = false;
                mostrarError(error);
            }
        );

    } catch (error) {
        elementos.progresoProceso.style.display = 'none';
        estado.procesando = false;
        elementos.btnEjecutar.disabled = false;
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
