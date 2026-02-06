/**
 * JavaScript para la pagina de rotacion de PDF.
 * Maneja la visualizacion de miniaturas y rotacion de paginas.
 */

// Estado global
const estado = {
    archivoId: null,
    nombreArchivo: '',
    numPaginas: 0,
    paginaActual: 1,
    paginasPorVista: 20,
    rotaciones: {},  // {numeroPagina: angulo}
    rotacionesOriginales: {},  // Rotaciones originales del PDF
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
    thumbnailsSection: document.getElementById('thumbnails-section'),
    thumbnailsGrid: document.getElementById('thumbnails-grid'),
    pagination: document.getElementById('pagination'),
    pagInicio: document.getElementById('pag-inicio'),
    pagFin: document.getElementById('pag-fin'),
    pagTotal: document.getElementById('pag-total'),
    btnAnterior: document.getElementById('btn-anterior'),
    btnSiguiente: document.getElementById('btn-siguiente'),
    btnRotarTodas90: document.getElementById('btn-rotar-todas-90'),
    btnRotarTodas180: document.getElementById('btn-rotar-todas-180'),
    btnRestaurar: document.getElementById('btn-restaurar'),
    panelOpciones: document.getElementById('panel-opciones'),
    numCambios: document.getElementById('num-cambios'),
    btnAplicar: document.getElementById('btn-aplicar'),
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
    elementos.btnAplicar.addEventListener('click', aplicarRotaciones);
    elementos.btnAnterior.addEventListener('click', paginaAnterior);
    elementos.btnSiguiente.addEventListener('click', paginaSiguiente);
    elementos.btnRotarTodas90.addEventListener('click', () => rotarTodas(90));
    elementos.btnRotarTodas180.addEventListener('click', () => rotarTodas(180));
    elementos.btnRestaurar.addEventListener('click', restaurarTodas);
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
 * Carga la informacion del archivo y muestra las miniaturas.
 */
async function cargarArchivo(data) {
    estado.archivoId = data.id;
    estado.nombreArchivo = data.nombre_original;
    estado.numPaginas = data.num_paginas;
    estado.paginaActual = 1;
    estado.rotaciones = {};

    // Mostrar info del archivo
    elementos.nombreArchivo.textContent = data.nombre_original;
    elementos.numPaginas.textContent = data.num_paginas;
    elementos.infoArchivo.style.display = 'block';

    if (data.ya_existia) {
        mostrarInfo('Archivo ya estaba en el servidor, se reutilizo');
    }

    // Cargar informacion de paginas
    await cargarPaginas();

    // Mostrar panel de opciones
    elementos.panelOpciones.style.display = 'block';
    elementos.thumbnailsSection.style.display = 'block';

    // Mostrar paginacion si hay mas de 20 paginas
    if (estado.numPaginas > estado.paginasPorVista) {
        elementos.pagination.style.display = 'flex';
        elementos.pagTotal.textContent = estado.numPaginas;
        actualizarPaginacion();
    }

    actualizarContadorCambios();
}

/**
 * Carga las paginas de la vista actual.
 */
async function cargarPaginas() {
    try {
        const respuesta = await fetch(
            `${window.AppConfig.API_BASE_URL}/convert/rotate/info?file_id=${estado.archivoId}&pagina_inicio=${estado.paginaActual}&cantidad=${estado.paginasPorVista}`
        );

        const datos = await respuesta.json();

        if (!datos.success) {
            throw new Error(datos.error?.message || 'Error al cargar paginas');
        }

        // Guardar rotaciones originales
        datos.data.paginas.forEach(pag => {
            if (!(pag.numero in estado.rotacionesOriginales)) {
                estado.rotacionesOriginales[pag.numero] = pag.rotacion_actual;
            }
        });

        // Renderizar miniaturas
        renderizarMiniaturas(datos.data.paginas);

    } catch (error) {
        mostrarError(error.message);
    }
}

/**
 * Renderiza las miniaturas de las paginas.
 */
function renderizarMiniaturas(paginas) {
    elementos.thumbnailsGrid.innerHTML = '';

    paginas.forEach(pagina => {
        const rotacionActual = estado.rotaciones[pagina.numero] !== undefined
            ? estado.rotaciones[pagina.numero]
            : pagina.rotacion_actual;

        const tieneRotacion = rotacionActual !== estado.rotacionesOriginales[pagina.numero];

        const thumbnail = document.createElement('div');
        thumbnail.className = `page-thumbnail ${tieneRotacion ? 'rotated' : ''}`;
        thumbnail.dataset.pagina = pagina.numero;

        const urlMiniatura = `${window.AppConfig.API_BASE_URL}/files/${estado.archivoId}/thumbnail/${pagina.numero}`;

        thumbnail.innerHTML = `
            <div class="thumbnail-image-container">
                <img class="thumbnail-image" src="${urlMiniatura}"
                     alt="Pagina ${pagina.numero}"
                     style="transform: rotate(${rotacionActual}deg)"
                     onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 140%22><rect fill=%22%23f0f0f0%22 width=%22100%22 height=%22140%22/><text x=%2250%22 y=%2275%22 text-anchor=%22middle%22 fill=%22%23999%22 font-size=%2212%22>Pag ${pagina.numero}</text></svg>'">
                ${rotacionActual !== 0 ? `<div class="rotation-indicator">${rotacionActual}°</div>` : ''}
            </div>
            <div class="page-info">
                <span class="page-number">Pagina ${pagina.numero}</span>
                <span class="rotation-badge ${rotacionActual === 0 ? 'no-rotation' : ''}">${rotacionActual}°</span>
            </div>
        `;

        thumbnail.addEventListener('click', () => rotarPagina(pagina.numero));

        elementos.thumbnailsGrid.appendChild(thumbnail);
    });
}

/**
 * Rota una pagina 90 grados.
 */
function rotarPagina(numeroPagina) {
    const rotacionActual = estado.rotaciones[numeroPagina] !== undefined
        ? estado.rotaciones[numeroPagina]
        : (estado.rotacionesOriginales[numeroPagina] || 0);

    // Siguiente rotacion (0 -> 90 -> 180 -> 270 -> 0)
    const nuevaRotacion = (rotacionActual + 90) % 360;

    estado.rotaciones[numeroPagina] = nuevaRotacion;

    // Actualizar UI
    actualizarMiniatura(numeroPagina, nuevaRotacion);
    actualizarContadorCambios();
}

/**
 * Actualiza la miniatura de una pagina.
 */
function actualizarMiniatura(numeroPagina, rotacion) {
    const thumbnail = elementos.thumbnailsGrid.querySelector(`[data-pagina="${numeroPagina}"]`);
    if (!thumbnail) return;

    const tieneRotacion = rotacion !== estado.rotacionesOriginales[numeroPagina];
    thumbnail.className = `page-thumbnail ${tieneRotacion ? 'rotated' : ''}`;

    const img = thumbnail.querySelector('.thumbnail-image');
    if (img) {
        img.style.transform = `rotate(${rotacion}deg)`;
    }

    // Actualizar indicador
    const container = thumbnail.querySelector('.thumbnail-image-container');
    const indicadorExistente = container.querySelector('.rotation-indicator');
    if (indicadorExistente) {
        indicadorExistente.remove();
    }
    if (rotacion !== 0) {
        const indicador = document.createElement('div');
        indicador.className = 'rotation-indicator';
        indicador.textContent = `${rotacion}°`;
        container.appendChild(indicador);
    }

    // Actualizar badge
    const badge = thumbnail.querySelector('.rotation-badge');
    if (badge) {
        badge.textContent = `${rotacion}°`;
        badge.className = `rotation-badge ${rotacion === 0 ? 'no-rotation' : ''}`;
    }
}

/**
 * Rota todas las paginas visibles.
 */
function rotarTodas(angulo) {
    for (let i = 1; i <= estado.numPaginas; i++) {
        const rotacionActual = estado.rotaciones[i] !== undefined
            ? estado.rotaciones[i]
            : (estado.rotacionesOriginales[i] || 0);

        estado.rotaciones[i] = (rotacionActual + angulo) % 360;
    }

    // Recargar miniaturas
    cargarPaginas();
    actualizarContadorCambios();
}

/**
 * Restaura todas las rotaciones al estado original.
 */
function restaurarTodas() {
    estado.rotaciones = {};

    // Recargar miniaturas
    cargarPaginas();
    actualizarContadorCambios();
}

/**
 * Actualiza el contador de cambios.
 */
function actualizarContadorCambios() {
    let cambios = 0;

    for (const [pagina, rotacion] of Object.entries(estado.rotaciones)) {
        const original = estado.rotacionesOriginales[pagina] || 0;
        if (rotacion !== original) {
            cambios++;
        }
    }

    elementos.numCambios.textContent = cambios;
    elementos.btnAplicar.disabled = cambios === 0;
}

/**
 * Actualiza la paginacion.
 */
function actualizarPaginacion() {
    const inicio = estado.paginaActual;
    const fin = Math.min(estado.paginaActual + estado.paginasPorVista - 1, estado.numPaginas);

    elementos.pagInicio.textContent = inicio;
    elementos.pagFin.textContent = fin;

    elementos.btnAnterior.disabled = estado.paginaActual === 1;
    elementos.btnSiguiente.disabled = fin >= estado.numPaginas;
}

/**
 * Va a la pagina anterior.
 */
function paginaAnterior() {
    if (estado.paginaActual > 1) {
        estado.paginaActual = Math.max(1, estado.paginaActual - estado.paginasPorVista);
        cargarPaginas();
        actualizarPaginacion();
    }
}

/**
 * Va a la pagina siguiente.
 */
function paginaSiguiente() {
    if (estado.paginaActual + estado.paginasPorVista <= estado.numPaginas) {
        estado.paginaActual += estado.paginasPorVista;
        cargarPaginas();
        actualizarPaginacion();
    }
}

/**
 * Aplica las rotaciones y descarga el PDF.
 */
async function aplicarRotaciones() {
    if (estado.procesando || !estado.archivoId) return;

    // Filtrar solo las rotaciones que cambiaron
    const rotacionesAplicar = {};
    for (const [pagina, rotacion] of Object.entries(estado.rotaciones)) {
        const original = estado.rotacionesOriginales[pagina] || 0;
        if (rotacion !== original) {
            rotacionesAplicar[pagina] = rotacion;
        }
    }

    if (Object.keys(rotacionesAplicar).length === 0) {
        mostrarInfo('No hay cambios para aplicar');
        return;
    }

    estado.procesando = true;
    elementos.btnAplicar.disabled = true;

    // Mostrar progreso
    elementos.progresoProceso.style.display = 'block';
    elementos.barraProceso.style.width = '0%';
    elementos.porcentajeProceso.textContent = '0%';
    elementos.textoProceso.textContent = 'Iniciando...';

    try {
        // Enviar peticion
        const respuesta = await fetch(`${window.AppConfig.API_BASE_URL}/convert/rotate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                file_id: estado.archivoId,
                rotaciones: rotacionesAplicar
            })
        });

        const datos = await respuesta.json();

        if (!datos.success) {
            throw new Error(datos.error?.message || 'Error al iniciar rotacion');
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
                elementos.btnAplicar.disabled = false;
                mostrarExito('PDF rotado correctamente. Iniciando descarga...');

                // Iniciar descarga
                window.PDFExport.descargarResultado(jobId);
            },
            (error) => {
                elementos.progresoProceso.style.display = 'none';
                estado.procesando = false;
                elementos.btnAplicar.disabled = false;
                mostrarError(error);
            }
        );

    } catch (error) {
        elementos.progresoProceso.style.display = 'none';
        estado.procesando = false;
        elementos.btnAplicar.disabled = false;
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
