/**
 * JavaScript para la pagina PDF a TXT.
 * Maneja la carga del archivo, opciones y extraccion de texto.
 */

// Estado global
const estado = {
    archivoId: null,
    nombreArchivo: '',
    numPaginas: 0,
    procesando: false
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
    previewLineas: document.getElementById('preview-lineas'),
    optNumeros: document.getElementById('opt-numeros'),
    optEncabezados: document.getElementById('opt-encabezados'),
    optPies: document.getElementById('opt-pies'),
    optParrafos: document.getElementById('opt-parrafos'),
    optColumnas: document.getElementById('opt-columnas'),
    btnPreview: document.getElementById('btn-preview'),
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
    elementos.btnPreview.addEventListener('click', generarPreview);
    elementos.btnEjecutar.addEventListener('click', ejecutarExtraccion);

    // Actualizar preview cuando cambian opciones
    [elementos.optNumeros, elementos.optEncabezados, elementos.optPies,
     elementos.optParrafos, elementos.optColumnas].forEach(checkbox => {
        checkbox.addEventListener('change', () => {
            // Limpiar preview al cambiar opciones
            elementos.previewContainer.innerHTML = '<p class="preview-placeholder">Haz clic en "Vista Previa" para ver el resultado</p>';
            elementos.previewLineas.textContent = '0';
        });
    });
}

/**
 * Obtiene las opciones seleccionadas.
 */
function obtenerOpciones() {
    return {
        remover_numeros_pagina: elementos.optNumeros.checked,
        remover_encabezados: elementos.optEncabezados.checked,
        remover_pies_pagina: elementos.optPies.checked,
        preservar_parrafos: elementos.optParrafos.checked,
        detectar_columnas: elementos.optColumnas.checked
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
function cargarArchivo(data) {
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

    // Habilitar botones
    elementos.btnPreview.disabled = false;
    elementos.btnEjecutar.disabled = false;

    if (data.ya_existia) {
        mostrarInfo('Archivo ya estaba en el servidor, se reutilizo');
    }

    // Generar preview automaticamente
    generarPreview();
}

/**
 * Genera vista previa del texto.
 */
async function generarPreview() {
    if (!estado.archivoId) return;

    elementos.previewContainer.innerHTML = '<p class="preview-placeholder">Generando vista previa...</p>';
    elementos.btnPreview.disabled = true;

    try {
        const respuesta = await fetch(`${window.AppConfig.API_BASE_URL}/convert/to-txt/preview`, {
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

        if (datos.success) {
            // Mostrar preview
            const textoEscapado = escapeHtml(datos.data.preview);
            elementos.previewContainer.innerHTML = textoEscapado || '<p class="preview-placeholder">No se extrajo texto del documento</p>';
            elementos.previewLineas.textContent = datos.data.lineas;
        } else {
            throw new Error(datos.error?.message || 'Error generando preview');
        }
    } catch (error) {
        elementos.previewContainer.innerHTML = `<p class="preview-placeholder" style="color: var(--color-danger);">Error: ${error.message}</p>`;
    } finally {
        elementos.btnPreview.disabled = false;
    }
}

/**
 * Ejecuta la extraccion completa y descarga.
 */
async function ejecutarExtraccion() {
    if (estado.procesando || !estado.archivoId) return;

    estado.procesando = true;
    elementos.btnEjecutar.disabled = true;
    elementos.btnPreview.disabled = true;

    // Mostrar progreso
    elementos.progresoProceso.style.display = 'block';
    elementos.barraProceso.style.width = '0%';
    elementos.porcentajeProceso.textContent = '0%';
    elementos.textoProceso.textContent = 'Iniciando...';

    try {
        // Enviar peticion
        const respuesta = await fetch(`${window.AppConfig.API_BASE_URL}/convert/to-txt`, {
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
            throw new Error(datos.error?.message || 'Error al iniciar extraccion');
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
                elementos.btnPreview.disabled = false;
                mostrarExito('Texto extraido correctamente. Iniciando descarga...');

                // Iniciar descarga
                window.PDFExport.descargarResultado(jobId);
            },
            (error) => {
                elementos.progresoProceso.style.display = 'none';
                estado.procesando = false;
                elementos.btnEjecutar.disabled = false;
                elementos.btnPreview.disabled = false;
                mostrarError(error);
            }
        );

    } catch (error) {
        elementos.progresoProceso.style.display = 'none';
        estado.procesando = false;
        elementos.btnEjecutar.disabled = false;
        elementos.btnPreview.disabled = false;
        mostrarError(error.message);
    }
}

/**
 * Escapa HTML para mostrar texto seguro.
 */
function escapeHtml(texto) {
    const div = document.createElement('div');
    div.textContent = texto;
    return div.innerHTML;
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
