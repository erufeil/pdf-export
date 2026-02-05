/**
 * JavaScript para la pagina de compresion de PDF.
 * Maneja la carga del archivo, opciones y compresion.
 */

// Estado global
const estado = {
    archivoId: null,
    nombreArchivo: '',
    numPaginas: 0,
    tamanoActual: 0,
    infoCompresion: null,
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
    tamanoActual: document.getElementById('tamano-actual'),
    numImagenes: document.getElementById('num-imagenes'),
    porcentajeImagenes: document.getElementById('porcentaje-imagenes'),
    panelOpciones: document.getElementById('panel-opciones'),
    customOptions: document.getElementById('custom-options'),
    dpiMaximo: document.getElementById('dpi-maximo'),
    calidadJpg: document.getElementById('calidad-jpg'),
    tamanoEstimado: document.getElementById('tamano-estimado'),
    reduccionEstimada: document.getElementById('reduccion-estimada'),
    btnComprimir: document.getElementById('btn-comprimir'),
    progresoProceso: document.getElementById('progreso-proceso'),
    barraProceso: document.getElementById('barra-proceso'),
    textoProceso: document.getElementById('texto-proceso'),
    porcentajeProceso: document.getElementById('porcentaje-proceso'),
    mensajeEstado: document.getElementById('mensaje-estado'),
    resultadoCard: document.getElementById('resultado-card'),
    resultadoOriginal: document.getElementById('resultado-original'),
    resultadoComprimido: document.getElementById('resultado-comprimido'),
    resultadoReduccion: document.getElementById('resultado-reduccion')
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
    elementos.btnComprimir.addEventListener('click', ejecutarCompresion);

    // Mostrar/ocultar opciones personalizadas
    document.querySelectorAll('input[name="nivel"]').forEach(radio => {
        radio.addEventListener('change', function() {
            elementos.customOptions.classList.toggle('visible', this.value === 'personalizada');
            actualizarEstimacion();
        });
    });

    // Actualizar estimacion cuando cambian opciones personalizadas
    elementos.dpiMaximo.addEventListener('change', actualizarEstimacion);
    elementos.calidadJpg.addEventListener('change', actualizarEstimacion);

    // Checkbox de escala de grises afecta estimacion
    document.getElementById('escala-grises').addEventListener('change', actualizarEstimacion);
}

/**
 * Obtiene las opciones seleccionadas.
 */
function obtenerOpciones() {
    const nivelSeleccionado = document.querySelector('input[name="nivel"]:checked');
    const nivel = nivelSeleccionado ? nivelSeleccionado.value : 'media';

    const opciones = {
        nivel: nivel,
        eliminar_metadatos: document.getElementById('eliminar-metadatos').checked,
        eliminar_anotaciones: document.getElementById('eliminar-anotaciones').checked,
        eliminar_bookmarks: document.getElementById('eliminar-bookmarks').checked,
        escala_grises: document.getElementById('escala-grises').checked
    };

    // Agregar opciones personalizadas si es necesario
    if (nivel === 'personalizada') {
        opciones.dpi_maximo = parseInt(elementos.dpiMaximo.value) || 120;
        opciones.calidad_jpg = parseInt(elementos.calidadJpg.value) || 75;
    }

    return opciones;
}

/**
 * Actualiza la estimacion de tamano.
 */
function actualizarEstimacion() {
    if (!estado.infoCompresion) return;

    const nivelSeleccionado = document.querySelector('input[name="nivel"]:checked');
    const nivel = nivelSeleccionado ? nivelSeleccionado.value : 'media';
    const escalaGrises = document.getElementById('escala-grises').checked;

    let tamanoEstimado, reduccion;

    if (nivel === 'personalizada') {
        // Estimar basado en valores personalizados
        const dpi = parseInt(elementos.dpiMaximo.value) || 120;
        const calidad = parseInt(elementos.calidadJpg.value) || 75;

        // Formula simple de estimacion
        const factorDpi = Math.min(1, dpi / 150);
        const factorCalidad = calidad / 100;
        const factorBase = 0.3 + (factorDpi * factorCalidad * 0.5);

        tamanoEstimado = estado.tamanoActual * factorBase;
        reduccion = ((estado.tamanoActual - tamanoEstimado) / estado.tamanoActual * 100);
    } else {
        const estimacion = estado.infoCompresion.estimaciones[nivel];
        tamanoEstimado = estimacion.tamano;
        reduccion = estimacion.reduccion;
    }

    // Ajustar si se usa escala de grises
    if (escalaGrises) {
        tamanoEstimado *= 0.7;
        reduccion = ((estado.tamanoActual - tamanoEstimado) / estado.tamanoActual * 100);
    }

    elementos.tamanoEstimado.textContent = `~${formatearTamano(tamanoEstimado)}`;
    elementos.reduccionEstimada.textContent = `Reduccion del ~${Math.round(reduccion)}%`;
}

/**
 * Formatea tamano en bytes a texto legible.
 */
function formatearTamano(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
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
    elementos.infoArchivo.style.display = 'block';

    if (data.ya_existia) {
        mostrarInfo('Archivo ya estaba en el servidor, se reutilizo');
    }

    // Obtener info de compresion
    try {
        const respuesta = await fetch(`${window.AppConfig.API_BASE_URL}/convert/compress/info?file_id=${estado.archivoId}`);
        const datos = await respuesta.json();

        if (datos.success) {
            estado.infoCompresion = datos.data;
            estado.tamanoActual = datos.data.tamano_actual;

            // Actualizar UI con info de compresion
            elementos.tamanoActual.textContent = datos.data.tamano_actual_texto;
            elementos.numImagenes.textContent = datos.data.total_imagenes;
            elementos.porcentajeImagenes.textContent = datos.data.porcentaje_imagenes + '%';

            // Actualizar estimaciones en las opciones
            const est = datos.data.estimaciones;
            document.getElementById('estimate-baja').textContent = `Resultado: ~${est.baja.tamano_texto}`;
            document.getElementById('estimate-media').textContent = `Resultado: ~${est.media.tamano_texto}`;
            document.getElementById('estimate-alta').textContent = `Resultado: ~${est.alta.tamano_texto}`;

            // Actualizar estimacion
            actualizarEstimacion();
        }
    } catch (error) {
        console.error('Error obteniendo info de compresion:', error);
    }

    // Mostrar panel de opciones
    elementos.panelOpciones.style.display = 'block';
    elementos.btnComprimir.disabled = false;
}

/**
 * Ejecuta la compresion del PDF.
 */
async function ejecutarCompresion() {
    if (estado.procesando || !estado.archivoId) return;

    estado.procesando = true;
    elementos.btnComprimir.disabled = true;
    elementos.resultadoCard.style.display = 'none';

    // Mostrar progreso
    elementos.progresoProceso.style.display = 'block';
    elementos.barraProceso.style.width = '0%';
    elementos.porcentajeProceso.textContent = '0%';
    elementos.textoProceso.textContent = 'Iniciando...';

    try {
        // Enviar peticion
        const respuesta = await fetch(`${window.AppConfig.API_BASE_URL}/convert/compress`, {
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
            throw new Error(datos.error?.message || 'Error al iniciar compresion');
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
            (jobId, resultado) => {
                // Completado
                elementos.progresoProceso.style.display = 'none';
                estado.procesando = false;
                elementos.btnComprimir.disabled = false;

                // Mostrar resultado si hay info disponible
                mostrarResultado(resultado);

                // Iniciar descarga
                window.PDFExport.descargarResultado(jobId);
            },
            (error) => {
                elementos.progresoProceso.style.display = 'none';
                estado.procesando = false;
                elementos.btnComprimir.disabled = false;
                mostrarError(error);
            }
        );

    } catch (error) {
        elementos.progresoProceso.style.display = 'none';
        estado.procesando = false;
        elementos.btnComprimir.disabled = false;
        mostrarError(error.message);
    }
}

/**
 * Muestra el resultado de la compresion.
 */
function mostrarResultado(resultado) {
    // Parsear mensaje si tiene info de reduccion
    if (resultado && resultado.mensaje) {
        const match = resultado.mensaje.match(/(\d+(?:\.\d+)?\s*[KMGT]?B)\s*->\s*(\d+(?:\.\d+)?\s*[KMGT]?B)\s*\(reduccion del (\d+(?:\.\d+)?)%\)/i);

        if (match) {
            elementos.resultadoOriginal.textContent = match[1];
            elementos.resultadoComprimido.textContent = match[2];
            elementos.resultadoReduccion.textContent = `-${match[3]}%`;
            elementos.resultadoCard.style.display = 'block';
        }
    }

    mostrarExito('PDF comprimido correctamente. Iniciando descarga...');
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
