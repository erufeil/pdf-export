/**
 * JavaScript para la pagina de Cortar PDF.
 * Maneja la carga del archivo, definicion de cortes y ejecucion.
 */

// Estado global de la aplicacion
const estado = {
    archivoId: null,
    nombreArchivo: '',
    numPaginas: 0,
    cortes: [],
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
    vistaPrevia: document.getElementById('vista-previa'),
    thumbPrimera: document.getElementById('thumb-primera'),
    thumbUltima: document.getElementById('thumb-ultima'),
    panelCortes: document.getElementById('panel-cortes'),
    listaCortes: document.getElementById('lista-cortes'),
    btnAgregarCorte: document.getElementById('btn-agregar-corte'),
    numPartesAuto: document.getElementById('num-partes-auto'),
    btnAutoSplit: document.getElementById('btn-auto-split'),
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
    elementos.btnAgregarCorte.addEventListener('click', agregarCorte);
    elementos.btnAutoSplit.addEventListener('click', calcularCortesAutomaticos);
    elementos.btnEjecutar.addEventListener('click', ejecutarCortes);
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

    // Cargar miniaturas
    await cargarMiniaturas();

    // Mostrar vista previa y panel de cortes
    elementos.vistaPrevia.style.display = 'flex';
    elementos.panelCortes.style.display = 'block';

    // Agregar primer corte por defecto (todo el documento)
    estado.cortes = [];
    agregarCorte();

    if (data.ya_existia) {
        mostrarInfo('Archivo ya estaba en el servidor, se reutilizo');
    }
}

/**
 * Carga las miniaturas de primera y ultima pagina.
 */
async function cargarMiniaturas() {
    const urlPrimera = `${window.AppConfig.API_BASE_URL}/files/${estado.archivoId}/thumbnail/0`;
    const urlUltima = `${window.AppConfig.API_BASE_URL}/files/${estado.archivoId}/thumbnail/${estado.numPaginas - 1}`;

    elementos.thumbPrimera.src = urlPrimera;
    elementos.thumbUltima.src = urlUltima;
}

/**
 * Agrega un nuevo corte a la lista.
 */
function agregarCorte() {
    if (estado.cortes.length >= 20) {
        mostrarError('Maximo 20 cortes permitidos');
        return;
    }

    // Calcular rango por defecto
    let inicio = 1;
    if (estado.cortes.length > 0) {
        const ultimoCorte = estado.cortes[estado.cortes.length - 1];
        inicio = ultimoCorte.fin + 1;
    }

    if (inicio > estado.numPaginas) {
        mostrarError('No hay mas paginas para cortar');
        return;
    }

    const nuevoCorte = {
        id: Date.now(),
        inicio: inicio,
        fin: estado.numPaginas,
        nombre: `parte_${estado.cortes.length + 1}`
    };

    estado.cortes.push(nuevoCorte);
    renderizarCortes();
    actualizarBotonEjecutar();
}

/**
 * Elimina un corte de la lista.
 */
function eliminarCorte(corteId) {
    estado.cortes = estado.cortes.filter(c => c.id !== corteId);
    renderizarCortes();
    actualizarBotonEjecutar();
}

/**
 * Actualiza el rango de un corte.
 */
function actualizarCorte(corteId, campo, valor) {
    const corte = estado.cortes.find(c => c.id === corteId);
    if (!corte) return;

    valor = parseInt(valor) || 1;

    if (campo === 'inicio') {
        corte.inicio = Math.max(1, Math.min(valor, estado.numPaginas));
        if (corte.inicio > corte.fin) {
            corte.fin = corte.inicio;
        }
    } else if (campo === 'fin') {
        corte.fin = Math.max(1, Math.min(valor, estado.numPaginas));
        if (corte.fin < corte.inicio) {
            corte.inicio = corte.fin;
        }
    }

    renderizarCortes();
}

/**
 * Renderiza la lista de cortes en el DOM.
 */
function renderizarCortes() {
    elementos.listaCortes.innerHTML = estado.cortes.map((corte, index) => `
        <div class="cut-item" data-id="${corte.id}">
            <div class="cut-header">
                <span class="cut-title">Corte ${index + 1}</span>
                <span class="cut-pages">${corte.fin - corte.inicio + 1} paginas</span>
                ${estado.cortes.length > 1 ? `
                    <button class="btn-remove-cut" onclick="eliminarCorte(${corte.id})" title="Eliminar corte">
                        ×
                    </button>
                ` : ''}
            </div>
            <div class="cut-range">
                <span>Desde pagina</span>
                <input type="number"
                       value="${corte.inicio}"
                       min="1"
                       max="${estado.numPaginas}"
                       onchange="actualizarCorte(${corte.id}, 'inicio', this.value)"
                       onblur="actualizarMiniaturasCorte(${corte.id})">
                <span>hasta</span>
                <input type="number"
                       value="${corte.fin}"
                       min="1"
                       max="${estado.numPaginas}"
                       onchange="actualizarCorte(${corte.id}, 'fin', this.value)"
                       onblur="actualizarMiniaturasCorte(${corte.id})">
            </div>
            <div class="cut-thumbnails">
                <div class="cut-thumb">
                    <img id="thumb-corte-${corte.id}-inicio"
                         src="${window.AppConfig.API_BASE_URL}/files/${estado.archivoId}/thumbnail/${corte.inicio - 1}"
                         alt="Pagina ${corte.inicio}">
                    <p class="cut-thumb-label">Pag. ${corte.inicio}</p>
                </div>
                <div class="cut-thumb">
                    <img id="thumb-corte-${corte.id}-fin"
                         src="${window.AppConfig.API_BASE_URL}/files/${estado.archivoId}/thumbnail/${corte.fin - 1}"
                         alt="Pagina ${corte.fin}">
                    <p class="cut-thumb-label">Pag. ${corte.fin}</p>
                </div>
            </div>
        </div>
    `).join('');
}

/**
 * Actualiza las miniaturas de un corte especifico.
 */
function actualizarMiniaturasCorte(corteId) {
    const corte = estado.cortes.find(c => c.id === corteId);
    if (!corte) return;

    const imgInicio = document.getElementById(`thumb-corte-${corteId}-inicio`);
    const imgFin = document.getElementById(`thumb-corte-${corteId}-fin`);

    if (imgInicio) {
        imgInicio.src = `${window.AppConfig.API_BASE_URL}/files/${estado.archivoId}/thumbnail/${corte.inicio - 1}`;
    }
    if (imgFin) {
        imgFin.src = `${window.AppConfig.API_BASE_URL}/files/${estado.archivoId}/thumbnail/${corte.fin - 1}`;
    }
}

/**
 * Calcula cortes automaticos dividiendo en N partes iguales.
 */
function calcularCortesAutomaticos() {
    const numPartes = parseInt(elementos.numPartesAuto.value) || 2;

    if (numPartes < 2) {
        mostrarError('Minimo 2 partes');
        return;
    }
    if (numPartes > 20) {
        mostrarError('Maximo 20 partes');
        return;
    }
    if (numPartes > estado.numPaginas) {
        mostrarError(`No se puede dividir en ${numPartes} partes un documento de ${estado.numPaginas} paginas`);
        return;
    }

    // Calcular paginas por parte
    const paginasPorParte = Math.floor(estado.numPaginas / numPartes);
    const paginasExtra = estado.numPaginas % numPartes;

    estado.cortes = [];
    let paginaActual = 1;

    for (let i = 0; i < numPartes; i++) {
        const paginasEstaParte = paginasPorParte + (i < paginasExtra ? 1 : 0);
        const fin = paginaActual + paginasEstaParte - 1;

        estado.cortes.push({
            id: Date.now() + i,
            inicio: paginaActual,
            fin: fin,
            nombre: `parte_${i + 1}`
        });

        paginaActual = fin + 1;
    }

    renderizarCortes();
    actualizarBotonEjecutar();
    mostrarInfo(`Dividido en ${numPartes} partes iguales`);
}

/**
 * Actualiza el estado del boton ejecutar.
 */
function actualizarBotonEjecutar() {
    elementos.btnEjecutar.disabled = estado.cortes.length === 0 || estado.procesando;
}

/**
 * Ejecuta los cortes y descarga el resultado.
 */
async function ejecutarCortes() {
    if (estado.procesando) return;
    if (estado.cortes.length === 0) {
        mostrarError('Debe definir al menos un corte');
        return;
    }

    estado.procesando = true;
    actualizarBotonEjecutar();

    // Mostrar progreso
    elementos.progresoProceso.style.display = 'block';
    elementos.barraProceso.style.width = '0%';
    elementos.porcentajeProceso.textContent = '0%';
    elementos.textoProceso.textContent = 'Iniciando...';

    try {
        // Preparar datos de cortes
        const cortesData = estado.cortes.map((c, i) => ({
            inicio: c.inicio,
            fin: c.fin,
            nombre: `parte_${i + 1}`
        }));

        // Enviar peticion
        const respuesta = await fetch(`${window.AppConfig.API_BASE_URL}/convert/split`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                file_id: estado.archivoId,
                opciones: {
                    cortes: cortesData
                }
            })
        });

        const datos = await respuesta.json();

        if (!datos.success) {
            throw new Error(datos.error?.message || 'Error al iniciar el corte');
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
                actualizarBotonEjecutar();
                mostrarExito('Cortes completados. Iniciando descarga...');

                // Iniciar descarga
                window.PDFExport.descargarResultado(jobId);
            },
            (error) => {
                elementos.progresoProceso.style.display = 'none';
                estado.procesando = false;
                actualizarBotonEjecutar();
                mostrarError(error);
            }
        );

    } catch (error) {
        elementos.progresoProceso.style.display = 'none';
        estado.procesando = false;
        actualizarBotonEjecutar();
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

// Exponer funciones globales necesarias para onclick
window.eliminarCorte = eliminarCorte;
window.actualizarCorte = actualizarCorte;
window.actualizarMiniaturasCorte = actualizarMiniaturasCorte;
