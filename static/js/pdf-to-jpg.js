/**
 * JavaScript para la pagina PDF a JPG.
 * Maneja la carga del archivo, opciones y conversion a imagenes JPG.
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
    rangoInputs: document.getElementById('rango-inputs'),
    especificasInput: document.getElementById('especificas-input'),
    paginaDesde: document.getElementById('pagina-desde'),
    paginaHasta: document.getElementById('pagina-hasta'),
    paginasLista: document.getElementById('paginas-lista'),
    sizeEstimate: document.getElementById('size-estimate'),
    estPaginas: document.getElementById('est-paginas'),
    estTamanoJpg: document.getElementById('est-tamano-jpg'),
    estAhorro: document.getElementById('est-ahorro'),
    calidadSlider: document.getElementById('calidad-slider'),
    calidadValor: document.getElementById('calidad-valor'),
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

    // Slider de calidad
    elementos.calidadSlider.addEventListener('input', function() {
        elementos.calidadValor.textContent = this.value;
        actualizarEstimacion();
    });

    // Mostrar/ocultar inputs segun tipo de paginas seleccionado
    document.querySelectorAll('input[name="paginas-tipo"]').forEach(radio => {
        radio.addEventListener('change', function() {
            elementos.rangoInputs.style.display = this.value === 'range' ? 'flex' : 'none';
            elementos.especificasInput.style.display = this.value === 'specific' ? 'block' : 'none';
            actualizarEstimacion();
        });
    });

    // Actualizar estimacion cuando cambian opciones
    document.querySelectorAll('input[name="dpi"]').forEach(radio => {
        radio.addEventListener('change', actualizarEstimacion);
    });

    elementos.paginaDesde.addEventListener('change', actualizarEstimacion);
    elementos.paginaHasta.addEventListener('change', actualizarEstimacion);
    elementos.paginasLista.addEventListener('input', actualizarEstimacion);
}

/**
 * Obtiene las opciones seleccionadas.
 */
function obtenerOpciones() {
    const dpiSeleccionado = document.querySelector('input[name="dpi"]:checked');
    const tipoSeleccionado = document.querySelector('input[name="paginas-tipo"]:checked');
    const calidad = parseInt(elementos.calidadSlider.value);

    let paginas = 'all';

    if (tipoSeleccionado && tipoSeleccionado.value === 'range') {
        const desde = parseInt(elementos.paginaDesde.value) || 1;
        const hasta = parseInt(elementos.paginaHasta.value) || estado.numPaginas;
        paginas = `${desde}-${hasta}`;
    } else if (tipoSeleccionado && tipoSeleccionado.value === 'specific') {
        paginas = elementos.paginasLista.value || 'all';
    }

    return {
        dpi: parseInt(dpiSeleccionado?.value || 150),
        calidad: calidad,
        paginas: paginas
    };
}

/**
 * Calcula el numero de paginas seleccionadas.
 */
function calcularPaginasSeleccionadas() {
    const tipoSeleccionado = document.querySelector('input[name="paginas-tipo"]:checked');

    if (!tipoSeleccionado || tipoSeleccionado.value === 'all') {
        return estado.numPaginas;
    }

    if (tipoSeleccionado.value === 'range') {
        const desde = parseInt(elementos.paginaDesde.value) || 1;
        const hasta = parseInt(elementos.paginaHasta.value) || estado.numPaginas;
        return Math.max(0, hasta - desde + 1);
    }

    if (tipoSeleccionado.value === 'specific') {
        const lista = elementos.paginasLista.value;
        if (!lista) return estado.numPaginas;

        let count = 0;
        const partes = lista.replace(/\s/g, '').split(',');

        for (const parte of partes) {
            if (parte.includes('-')) {
                const [inicio, fin] = parte.split('-').map(Number);
                if (!isNaN(inicio) && !isNaN(fin)) {
                    count += Math.max(0, fin - inicio + 1);
                }
            } else {
                const num = parseInt(parte);
                if (!isNaN(num)) count++;
            }
        }

        return count || estado.numPaginas;
    }

    return estado.numPaginas;
}

/**
 * Estima el tamano del resultado en PNG.
 */
function estimarTamanoPng(numPaginas, dpi) {
    // Estimacion: 1.5MB por pagina a 150 DPI, escala cuadratica con DPI
    const baseMB = 1.5;
    const factorDPI = Math.pow(dpi / 150, 2);
    return baseMB * factorDPI * numPaginas;
}

/**
 * Estima el tamano del resultado en JPG.
 */
function estimarTamanoJpg(numPaginas, dpi, calidad) {
    // JPG es mas pequeno que PNG, el factor depende de la calidad
    const tamanoPng = estimarTamanoPng(numPaginas, dpi);
    // Factor de compresion JPG: calidad 95 = 0.6x PNG, calidad 60 = 0.2x PNG
    const factorCompresion = 0.2 + (calidad - 60) * (0.4 / 35);
    return tamanoPng * factorCompresion;
}

/**
 * Formatea el tamano en unidades legibles.
 */
function formatearTamano(tamanoMB) {
    if (tamanoMB < 1) {
        return `${(tamanoMB * 1024).toFixed(0)} KB`;
    } else if (tamanoMB < 1024) {
        return `${tamanoMB.toFixed(1)} MB`;
    } else {
        return `${(tamanoMB / 1024).toFixed(2)} GB`;
    }
}

/**
 * Actualiza la estimacion de tamano.
 */
function actualizarEstimacion() {
    if (!estado.archivoId) return;

    const paginasSeleccionadas = calcularPaginasSeleccionadas();
    const dpi = parseInt(document.querySelector('input[name="dpi"]:checked')?.value || 150);
    const calidad = parseInt(elementos.calidadSlider.value);

    const tamanoPng = estimarTamanoPng(paginasSeleccionadas, dpi);
    const tamanoJpg = estimarTamanoJpg(paginasSeleccionadas, dpi, calidad);
    const ahorro = ((1 - tamanoJpg / tamanoPng) * 100).toFixed(0);

    elementos.estPaginas.textContent = paginasSeleccionadas;
    elementos.estTamanoJpg.textContent = `~${formatearTamano(tamanoJpg)}`;
    elementos.estAhorro.textContent = `${ahorro}% menor que PNG`;
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

    // Configurar limites de paginas
    elementos.paginaDesde.max = data.num_paginas;
    elementos.paginaHasta.max = data.num_paginas;
    elementos.paginaHasta.value = data.num_paginas;

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

    // Actualizar estimacion
    actualizarEstimacion();
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
 * Ejecuta la conversion a JPG.
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
        const respuesta = await fetch(`${window.AppConfig.API_BASE_URL}/convert/to-jpg`, {
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
                mostrarExito('Imagenes JPG generadas correctamente. Iniciando descarga...');

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
