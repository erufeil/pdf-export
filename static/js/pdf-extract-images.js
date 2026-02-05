/**
 * JavaScript para la pagina de extraccion de imagenes de PDF.
 * Maneja la carga del archivo, visualizacion de imagenes y extraccion.
 */

// Estado global
const estado = {
    archivoId: null,
    nombreArchivo: '',
    numPaginas: 0,
    imagenes: [],
    imagenesSeleccionadas: new Set(),
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
    resultadoAnalisis: document.getElementById('resultado-analisis'),
    totalImagenes: document.getElementById('total-imagenes'),
    galeriaImagenes: document.getElementById('galeria-imagenes'),
    galleryGrid: document.getElementById('gallery-grid'),
    galleryLoading: document.getElementById('gallery-loading'),
    panelOpciones: document.getElementById('panel-opciones'),
    tamanoMinimo: document.getElementById('tamano-minimo'),
    numSeleccionadas: document.getElementById('num-seleccionadas'),
    btnSeleccionarTodas: document.getElementById('btn-seleccionar-todas'),
    btnDeseleccionarTodas: document.getElementById('btn-deseleccionar-todas'),
    btnExtraer: document.getElementById('btn-extraer'),
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
    elementos.btnExtraer.addEventListener('click', ejecutarExtraccion);
    elementos.btnSeleccionarTodas.addEventListener('click', seleccionarTodas);
    elementos.btnDeseleccionarTodas.addEventListener('click', deseleccionarTodas);

    // Filtro de tamano
    elementos.tamanoMinimo.addEventListener('change', filtrarImagenes);
}

/**
 * Obtiene las opciones seleccionadas.
 */
function obtenerOpciones() {
    const formatoSeleccionado = document.querySelector('input[name="formato"]:checked');

    return {
        formato_salida: formatoSeleccionado ? formatoSeleccionado.value : 'original',
        tamano_minimo_px: parseInt(elementos.tamanoMinimo.value) || 50,
        imagenes_seleccionadas: estado.imagenesSeleccionadas.size > 0 ?
            Array.from(estado.imagenesSeleccionadas) : null
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
 * Carga la informacion del archivo y analiza imagenes.
 */
async function cargarArchivo(data) {
    estado.archivoId = data.id;
    estado.nombreArchivo = data.nombre_original;
    estado.numPaginas = data.num_paginas;

    // Mostrar info del archivo
    elementos.nombreArchivo.textContent = data.nombre_original;
    elementos.numPaginas.textContent = data.num_paginas;
    elementos.infoArchivo.style.display = 'block';

    if (data.ya_existia) {
        mostrarInfo('Archivo ya estaba en el servidor, se reutilizo');
    }

    // Analizar imagenes del PDF
    await analizarImagenes();
}

/**
 * Analiza las imagenes del PDF.
 */
async function analizarImagenes() {
    elementos.galeriaImagenes.style.display = 'block';
    elementos.galleryLoading.style.display = 'block';
    elementos.galleryGrid.innerHTML = '';

    try {
        const respuesta = await fetch(`${window.AppConfig.API_BASE_URL}/convert/extract-images/count`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                file_id: estado.archivoId
            })
        });

        const datos = await respuesta.json();

        if (!datos.success) {
            throw new Error(datos.error?.message || 'Error al analizar imagenes');
        }

        estado.imagenes = datos.data.imagenes || [];
        const totalImagenes = datos.data.total_imagenes || estado.imagenes.length;

        // Mostrar resultado del analisis
        elementos.totalImagenes.textContent = totalImagenes;
        elementos.resultadoAnalisis.style.display = 'block';

        if (totalImagenes === 0) {
            elementos.resultadoAnalisis.classList.add('no-images');
            elementos.galleryLoading.style.display = 'none';
            elementos.galleryGrid.innerHTML = '<p style="text-align: center; color: var(--color-text-light); padding: 20px;">No se encontraron imagenes en el documento</p>';
            return;
        }

        // Mostrar galeria
        elementos.galleryLoading.style.display = 'none';
        mostrarGaleria();

        // Mostrar panel de opciones
        elementos.panelOpciones.style.display = 'block';

        // Seleccionar todas por defecto
        seleccionarTodas();

    } catch (error) {
        elementos.galleryLoading.style.display = 'none';
        mostrarError(error.message);
    }
}

/**
 * Muestra la galeria de imagenes.
 */
function mostrarGaleria() {
    const tamanoMinimo = parseInt(elementos.tamanoMinimo.value) || 50;
    elementos.galleryGrid.innerHTML = '';

    const imagenesFiltradas = estado.imagenes.filter(img =>
        img.ancho >= tamanoMinimo && img.alto >= tamanoMinimo
    );

    if (imagenesFiltradas.length === 0) {
        elementos.galleryGrid.innerHTML = '<p style="text-align: center; color: var(--color-text-light); padding: 20px;">No hay imagenes que cumplan con el filtro de tamano</p>';
        return;
    }

    imagenesFiltradas.forEach((imagen, index) => {
        const item = document.createElement('div');
        item.className = 'image-item';
        item.dataset.id = imagen.id || index;

        // Crear miniatura (placeholder si no hay preview)
        const thumbnailUrl = imagen.thumbnail ||
            `${window.AppConfig.API_BASE_URL}/files/${estado.archivoId}/image/${imagen.id || index}`;

        item.innerHTML = `
            <img class="image-thumbnail" src="${thumbnailUrl}"
                 alt="Imagen ${index + 1}"
                 onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><rect fill=%22%23f0f0f0%22 width=%22100%22 height=%22100%22/><text x=%2250%22 y=%2255%22 text-anchor=%22middle%22 fill=%22%23999%22 font-size=%2214%22>IMG</text></svg>'">
            <div class="image-info">${imagen.ancho}x${imagen.alto} ${imagen.formato || ''}</div>
        `;

        item.addEventListener('click', () => toggleSeleccion(item, imagen.id || index));

        elementos.galleryGrid.appendChild(item);
    });
}

/**
 * Filtra las imagenes por tamano.
 */
function filtrarImagenes() {
    mostrarGaleria();
    actualizarContadorSeleccion();
}

/**
 * Alterna la seleccion de una imagen.
 */
function toggleSeleccion(item, id) {
    if (estado.imagenesSeleccionadas.has(id)) {
        estado.imagenesSeleccionadas.delete(id);
        item.classList.remove('selected');
    } else {
        estado.imagenesSeleccionadas.add(id);
        item.classList.add('selected');
    }
    actualizarContadorSeleccion();
}

/**
 * Selecciona todas las imagenes visibles.
 */
function seleccionarTodas() {
    const items = elementos.galleryGrid.querySelectorAll('.image-item');
    items.forEach(item => {
        const id = item.dataset.id;
        estado.imagenesSeleccionadas.add(id);
        item.classList.add('selected');
    });
    actualizarContadorSeleccion();
}

/**
 * Deselecciona todas las imagenes.
 */
function deseleccionarTodas() {
    const items = elementos.galleryGrid.querySelectorAll('.image-item');
    items.forEach(item => {
        item.classList.remove('selected');
    });
    estado.imagenesSeleccionadas.clear();
    actualizarContadorSeleccion();
}

/**
 * Actualiza el contador de imagenes seleccionadas.
 */
function actualizarContadorSeleccion() {
    const count = estado.imagenesSeleccionadas.size;
    elementos.numSeleccionadas.textContent = count;
    elementos.btnExtraer.disabled = count === 0;
}

/**
 * Ejecuta la extraccion de imagenes.
 */
async function ejecutarExtraccion() {
    if (estado.procesando || !estado.archivoId) return;
    if (estado.imagenesSeleccionadas.size === 0) {
        mostrarError('Selecciona al menos una imagen para extraer');
        return;
    }

    estado.procesando = true;
    elementos.btnExtraer.disabled = true;

    // Mostrar progreso
    elementos.progresoProceso.style.display = 'block';
    elementos.barraProceso.style.width = '0%';
    elementos.porcentajeProceso.textContent = '0%';
    elementos.textoProceso.textContent = 'Iniciando...';

    try {
        // Enviar peticion
        const respuesta = await fetch(`${window.AppConfig.API_BASE_URL}/convert/extract-images`, {
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
                elementos.btnExtraer.disabled = false;
                mostrarExito('Imagenes extraidas correctamente. Iniciando descarga...');

                // Iniciar descarga
                window.PDFExport.descargarResultado(jobId);
            },
            (error) => {
                elementos.progresoProceso.style.display = 'none';
                estado.procesando = false;
                elementos.btnExtraer.disabled = false;
                mostrarError(error);
            }
        );

    } catch (error) {
        elementos.progresoProceso.style.display = 'none';
        estado.procesando = false;
        elementos.btnExtraer.disabled = false;
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
