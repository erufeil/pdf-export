/**
 * JavaScript para la pagina PDF a PNG (modo pagina completa).
 * Maneja carga del archivo, opciones de DPI/paginas y conversion.
 */

// Estado global
const estado = {
    archivoId: null,
    nombreArchivo: '',
    numPaginas: 0,
    procesando: false,
    jobId: null
};

// Elementos del DOM
const elementos = {
    zonaCarga:          document.getElementById('zona-carga'),
    progresoCarga:      document.getElementById('progreso-carga'),
    barraProgreso:      document.getElementById('barra-progreso'),
    textoProgreso:      document.getElementById('texto-progreso'),
    porcentajeProgreso: document.getElementById('porcentaje-progreso'),
    infoArchivo:        document.getElementById('info-archivo'),
    nombreArchivo:      document.getElementById('nombre-archivo'),
    numPaginas:         document.getElementById('num-paginas'),
    panelOpciones:      document.getElementById('panel-opciones'),
    seccionPreview:     document.getElementById('seccion-preview'),
    previewContainer:   document.getElementById('preview-container'),
    rangoInputs:        document.getElementById('rango-inputs'),
    especificasInput:   document.getElementById('especificas-input'),
    paginaDesde:        document.getElementById('pagina-desde'),
    paginaHasta:        document.getElementById('pagina-hasta'),
    paginasLista:       document.getElementById('paginas-lista'),
    estPaginas:         document.getElementById('est-paginas'),
    estTamano:          document.getElementById('est-tamano'),
    btnEjecutar:        document.getElementById('btn-ejecutar'),
    progresoProceso:    document.getElementById('progreso-proceso'),
    barraProceso:       document.getElementById('barra-proceso'),
    textoProceso:       document.getElementById('texto-proceso'),
    porcentajeProceso:  document.getElementById('porcentaje-proceso'),
    mensajeEstado:      document.getElementById('mensaje-estado')
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
    new window.PDFExport.DropZone(elementos.zonaCarga, {
        onFile: manejarArchivo,
        acceptedTypes: ['application/pdf', '.pdf']
    });
}

/**
 * Inicializa los event listeners de opciones.
 */
function inicializarEventos() {
    elementos.btnEjecutar.addEventListener('click', ejecutarConversion);

    // Mostrar/ocultar sub-inputs segun tipo de paginas
    document.querySelectorAll('input[name="paginas-tipo"]').forEach(radio => {
        radio.addEventListener('change', function() {
            elementos.rangoInputs.style.display   = this.value === 'range'    ? 'flex'  : 'none';
            elementos.especificasInput.style.display = this.value === 'specific' ? 'block' : 'none';
            actualizarEstimacion();
        });
    });

    // Actualizar estimacion al cambiar DPI o rangos
    document.querySelectorAll('input[name="dpi"]').forEach(radio => {
        radio.addEventListener('change', actualizarEstimacion);
    });
    elementos.paginaDesde.addEventListener('change', actualizarEstimacion);
    elementos.paginaHasta.addEventListener('change', actualizarEstimacion);
    elementos.paginasLista.addEventListener('input', actualizarEstimacion);
}

// ────────────────────────────────────────────────────────────
// OPCIONES
// ────────────────────────────────────────────────────────────

/**
 * Construye el objeto de opciones segun los controles actuales.
 */
function obtenerOpciones() {
    const dpiSeleccionado  = document.querySelector('input[name="dpi"]:checked');
    const tipoSeleccionado = document.querySelector('input[name="paginas-tipo"]:checked');

    let paginas = 'all';

    if (tipoSeleccionado && tipoSeleccionado.value === 'range') {
        const desde = parseInt(elementos.paginaDesde.value) || 1;
        const hasta = parseInt(elementos.paginaHasta.value) || estado.numPaginas;
        paginas = `${desde}-${hasta}`;
    } else if (tipoSeleccionado && tipoSeleccionado.value === 'specific') {
        paginas = elementos.paginasLista.value.trim() || 'all';
    }

    return {
        dpi:    parseInt(dpiSeleccionado?.value || 150),
        paginas
    };
}

/**
 * Calcula la cantidad de paginas seleccionadas para la estimacion.
 */
function calcularPaginasSeleccionadas() {
    const tipo = document.querySelector('input[name="paginas-tipo"]:checked');

    if (!tipo || tipo.value === 'all') return estado.numPaginas;

    if (tipo.value === 'range') {
        const desde = parseInt(elementos.paginaDesde.value) || 1;
        const hasta = parseInt(elementos.paginaHasta.value) || estado.numPaginas;
        return Math.max(0, hasta - desde + 1);
    }

    if (tipo.value === 'specific') {
        const lista = elementos.paginasLista.value;
        if (!lista.trim()) return estado.numPaginas;
        let count = 0;
        for (const parte of lista.replace(/\s/g, '').split(',')) {
            if (parte.includes('-')) {
                const [a, b] = parte.split('-').map(Number);
                if (!isNaN(a) && !isNaN(b)) count += Math.max(0, b - a + 1);
            } else {
                if (!isNaN(parseInt(parte))) count++;
            }
        }
        return count || estado.numPaginas;
    }

    return estado.numPaginas;
}

/**
 * Estima el tamano del resultado en texto legible.
 */
function estimarTamano(numPaginas, dpi) {
    const baseMB    = 1.5;
    const factorDPI = Math.pow(dpi / 150, 2);
    const tamanoMB  = baseMB * factorDPI * numPaginas;

    if (tamanoMB < 1)    return `${(tamanoMB * 1024).toFixed(0)} KB`;
    if (tamanoMB < 1024) return `${tamanoMB.toFixed(1)} MB`;
    return `${(tamanoMB / 1024).toFixed(2)} GB`;
}

/**
 * Actualiza la estimacion de tamano en la UI.
 */
function actualizarEstimacion() {
    if (!estado.archivoId) return;
    const n   = calcularPaginasSeleccionadas();
    const dpi = parseInt(document.querySelector('input[name="dpi"]:checked')?.value || 150);
    elementos.estPaginas.textContent = n;
    elementos.estTamano.textContent  = `~${estimarTamano(n, dpi)}`;
}

// ────────────────────────────────────────────────────────────
// CARGA DE ARCHIVO
// ────────────────────────────────────────────────────────────

/**
 * Maneja el archivo seleccionado: muestra progreso de carga y sube al servidor.
 */
async function manejarArchivo(file) {
    elementos.zonaCarga.style.display    = 'none';
    elementos.progresoCarga.style.display = 'block';

    const uploader = new window.PDFExport.FileUploader({
        onProgress: (pct) => {
            elementos.barraProgreso.style.width         = pct + '%';
            elementos.porcentajeProgreso.textContent    = pct + '%';
        },
        onComplete: (data) => {
            elementos.progresoCarga.style.display = 'none';
            cargarArchivo(data);
        },
        onError: (error) => {
            elementos.progresoCarga.style.display = 'none';
            elementos.zonaCarga.style.display     = 'block';
            mostrarError(error);
        }
    });

    try {
        await uploader.subirArchivo(file);
    } catch (error) {
        elementos.progresoCarga.style.display = 'none';
        elementos.zonaCarga.style.display     = 'block';
        mostrarError(error.message);
    }
}

/**
 * Muestra la informacion del archivo cargado y habilita opciones.
 */
function cargarArchivo(data) {
    estado.archivoId    = data.id;
    estado.nombreArchivo = data.nombre_original;
    estado.numPaginas   = data.num_paginas;

    elementos.nombreArchivo.textContent = data.nombre_original;
    elementos.numPaginas.textContent    = data.num_paginas;
    elementos.infoArchivo.style.display = 'flex';

    // Configurar limites de rango
    elementos.paginaDesde.max   = data.num_paginas;
    elementos.paginaHasta.max   = data.num_paginas;
    elementos.paginaHasta.value = data.num_paginas;

    elementos.panelOpciones.style.display  = 'block';
    elementos.seccionPreview.style.display = 'block';
    elementos.btnEjecutar.disabled         = false;

    if (data.ya_existia) mostrarInfo('Archivo ya estaba en el servidor, se reutilizo');

    cargarPreview();
    actualizarEstimacion();
}

/**
 * Carga la miniatura de la primera pagina en el panel de preview.
 */
function cargarPreview() {
    if (!estado.archivoId) return;
    const url = `${window.AppConfig.API_BASE_URL}/files/${estado.archivoId}/thumbnail/1`;
    elementos.previewContainer.innerHTML = `
        <img src="${url}" alt="Vista previa" class="preview-thumbnail"
             onerror="this.parentElement.innerHTML='<p class=\\'preview-placeholder\\'>No se pudo cargar la vista previa</p>'">
    `;
}

// ────────────────────────────────────────────────────────────
// CONVERSION
// ────────────────────────────────────────────────────────────

/**
 * Inicia la conversion a PNG.
 */
async function ejecutarConversion() {
    if (estado.procesando || !estado.archivoId) return;

    estado.procesando = true;
    elementos.btnEjecutar.disabled = true;
    ocultarMensaje();

    // Mostrar barra de progreso
    elementos.progresoProceso.style.display  = 'block';
    elementos.barraProceso.style.width       = '0%';
    elementos.barraProceso.style.background  = '';
    elementos.porcentajeProceso.textContent  = '0%';
    elementos.textoProceso.textContent       = 'Iniciando...';

    try {
        const resp = await fetch(`${window.AppConfig.API_BASE_URL}/convert/to-png`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ file_id: estado.archivoId, opciones: obtenerOpciones() })
        });
        const datos = await resp.json();

        if (!datos.success) {
            throw new Error(datos.error?.message || 'Error al iniciar conversion');
        }

        estado.jobId = datos.data.job_id;
        monitorearProgreso(estado.jobId);

    } catch (error) {
        finalizarConError(error.message);
    }
}

/**
 * Monitorea el progreso via SSE con fallback a polling.
 */
function monitorearProgreso(jobId) {
    const url = `${window.AppConfig.API_BASE_URL}/jobs/${jobId}/progress`;
    const sse = new EventSource(url);

    sse.onmessage = (e) => {
        try {
            const datos = JSON.parse(e.data);

            // Actualizar barra
            elementos.barraProceso.style.width      = datos.progreso + '%';
            elementos.porcentajeProceso.textContent = datos.progreso + '%';
            elementos.textoProceso.textContent      = datos.mensaje || `${datos.progreso}%`;

            if (datos.estado === 'completado') {
                sse.close();
                finalizarExito(jobId);

            } else if (datos.estado === 'error') {
                sse.close();
                finalizarConError(datos.mensaje || 'Error en la conversion');

            } else if (datos.error) {
                sse.close();
                finalizarConError(datos.error);
            }

        } catch (_) { /* ignorar errores de parseo */ }
    };

    // Cuando el SSE se corta (normal al cerrar servidor, o corte de red),
    // verificar el estado real del trabajo en vez de mostrar error directamente
    sse.onerror = () => {
        sse.close();
        elementos.textoProceso.textContent = 'Verificando estado...';
        verificarEstadoFinal(jobId);
    };
}

/**
 * Verifica el estado del trabajo via GET cuando el SSE falla.
 * Permite recuperarse de cortes de conexion durante la conversion.
 */
async function verificarEstadoFinal(jobId) {
    try {
        const resp = await fetch(`${window.AppConfig.API_BASE_URL}/jobs/${jobId}`);
        const datos = await resp.json();

        if (!datos.success) {
            finalizarConError('No se pudo verificar el estado del trabajo');
            return;
        }

        const trabajo = datos.data;

        if (trabajo.estado === 'completado') {
            elementos.barraProceso.style.width      = '100%';
            elementos.porcentajeProceso.textContent = '100%';
            finalizarExito(jobId);

        } else if (trabajo.estado === 'error') {
            finalizarConError(trabajo.mensaje || 'Error en la conversion');

        } else if (trabajo.estado === 'procesando' || trabajo.estado === 'pendiente') {
            // Aun procesando — reintentar en 2 segundos con polling simple
            setTimeout(() => verificarEstadoFinal(jobId), 2000);

        } else {
            finalizarConError('Estado desconocido: ' + trabajo.estado);
        }

    } catch (e) {
        finalizarConError('Error de red al verificar estado');
    }
}

// ────────────────────────────────────────────────────────────
// FINALIZACION
// ────────────────────────────────────────────────────────────

function finalizarExito(jobId) {
    elementos.progresoProceso.style.display = 'none';
    estado.procesando = false;
    elementos.btnEjecutar.disabled = false;
    mostrarExito('Imagenes generadas. Iniciando descarga...');
    window.PDFExport.descargarResultado(jobId);
}

function finalizarConError(mensaje) {
    elementos.progresoProceso.style.display = 'none';
    elementos.barraProceso.style.background = 'var(--red)';
    estado.procesando = false;
    elementos.btnEjecutar.disabled = false;
    mostrarError(mensaje);
}

// ────────────────────────────────────────────────────────────
// MENSAJES
// ────────────────────────────────────────────────────────────

function mostrarError(mensaje) {
    window.PDFExport.mostrarMensaje(elementos.mensajeEstado, mensaje, 'error');
}

function mostrarExito(mensaje) {
    window.PDFExport.mostrarMensaje(elementos.mensajeEstado, mensaje, 'success');
    setTimeout(() => window.PDFExport.ocultarMensaje(elementos.mensajeEstado), 5000);
}

function mostrarInfo(mensaje) {
    window.PDFExport.mostrarMensaje(elementos.mensajeEstado, mensaje, 'info');
    setTimeout(() => window.PDFExport.ocultarMensaje(elementos.mensajeEstado), 3000);
}

function ocultarMensaje() {
    window.PDFExport.ocultarMensaje(elementos.mensajeEstado);
}
