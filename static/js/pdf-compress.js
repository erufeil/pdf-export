/**
 * pdf-compress.js — Etapa 32 (Comprimir PDF avanzado) v1.1.48
 * Gestiona subida, análisis, selección de opciones y compresión con 7 categorías.
 */
console.log('[pdf-compress v1.1.48] cargado');

const API = window.AppConfig?.API_BASE_URL || '/api/v1';

// ── Estado global ────────────────────────────────────────────────────────────
const estado = {
    archivoId: null,
    nombreArchivo: '',
    tamanoOriginal: 0,
    analisis: null,
    preset: 'estandar',
    procesando: false,
};

// ── Definición de presets (deben coincidir con PRESETS en pdf_compress.py) ──
const PRESETS = {
    ligero: {
        reimagenes: false, dpi: 150, calidad_jpeg: 85,
        grises: false, dedup_imagenes: false,
        subset_fuentes: false, dedup_fuentes: false,
        eliminar_xmp: true, eliminar_thumbnails: true, limpiar_basicos: false,
        garbage: true, comprimir_streams: true, dedup_objetos: true,
        eliminar_anotaciones: false, eliminar_js: true,
        aplanar_formularios: false, eliminar_adjuntos: false, eliminar_firmas: false,
        eliminar_marcadores: false, eliminar_ocg: false,
        linearizar: false,
    },
    estandar: {
        reimagenes: true, dpi: 150, calidad_jpeg: 85,
        grises: false, dedup_imagenes: false,
        subset_fuentes: false, dedup_fuentes: false,
        eliminar_xmp: true, eliminar_thumbnails: true, limpiar_basicos: false,
        garbage: true, comprimir_streams: true, dedup_objetos: true,
        eliminar_anotaciones: false, eliminar_js: true,
        aplanar_formularios: false, eliminar_adjuntos: false, eliminar_firmas: false,
        eliminar_marcadores: false, eliminar_ocg: false,
        linearizar: false,
    },
    agresivo: {
        reimagenes: true, dpi: 96, calidad_jpeg: 60,
        grises: false, dedup_imagenes: true,
        subset_fuentes: true, dedup_fuentes: true,
        eliminar_xmp: true, eliminar_thumbnails: true, limpiar_basicos: false,
        garbage: true, comprimir_streams: true, dedup_objetos: true,
        eliminar_anotaciones: true, eliminar_js: true,
        aplanar_formularios: false, eliminar_adjuntos: true, eliminar_firmas: false,
        eliminar_marcadores: false, eliminar_ocg: true,
        linearizar: false,
    },
    maximo: {
        reimagenes: true, dpi: 72, calidad_jpeg: 60,
        grises: true, dedup_imagenes: true,
        subset_fuentes: true, dedup_fuentes: true,
        eliminar_xmp: true, eliminar_thumbnails: true, limpiar_basicos: false,
        garbage: true, comprimir_streams: true, dedup_objetos: true,
        eliminar_anotaciones: true, eliminar_js: true,
        aplanar_formularios: false, eliminar_adjuntos: true, eliminar_firmas: false,
        eliminar_marcadores: false, eliminar_ocg: true,
        linearizar: true,
        bajar_version: true,
        usar_ghostscript: true,
    },
};

// Mapeo checkbox id → clave de opciones
const CHECKBOXES = {
    'reimagenes':           'reimagenes',
    'grises':               'grises',
    'dedup-imagenes':       'dedup_imagenes',
    'subset-fuentes':       'subset_fuentes',
    'dedup-fuentes':        'dedup_fuentes',
    'eliminar-xmp':         'eliminar_xmp',
    'eliminar-thumbnails':  'eliminar_thumbnails',
    'limpiar-basicos':      'limpiar_basicos',
    'garbage':              'garbage',
    'comprimir-streams':    'comprimir_streams',
    'dedup-objetos':        'dedup_objetos',
    'eliminar-anotaciones': 'eliminar_anotaciones',
    'eliminar-js':          'eliminar_js',
    'aplanar-formularios':  'aplanar_formularios',
    'eliminar-adjuntos':    'eliminar_adjuntos',
    'eliminar-firmas':      'eliminar_firmas',
    'eliminar-marcadores':  'eliminar_marcadores',
    'eliminar-ocg':         'eliminar_ocg',
    'linearizar':           'linearizar',
    'bajar-version':        'bajar_version',
    'usar-ghostscript':     'usar_ghostscript',
};


// ── Inicialización ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    inicializarDropZone();
    inicializarPresets();
    inicializarCheckboxes();
    inicializarAppVersion();
    document.getElementById('btn-cambiar').addEventListener('click', reiniciar);
    document.getElementById('btn-comprimir').addEventListener('click', ejecutarCompresion);
});

function inicializarAppVersion() {
    const el = document.getElementById('app-version');
    if (el && window.AppConfig?.APP_VERSION) {
        el.textContent = 'v' + window.AppConfig.APP_VERSION;
    }
}

function inicializarDropZone() {
    if (window.PDFExport?.DropZone) {
        new window.PDFExport.DropZone(document.getElementById('zona-carga'), {
            onFile: manejarArchivo,
            acceptedTypes: ['application/pdf', '.pdf'],
        });
    } else {
        // Fallback manual
        const zona = document.getElementById('zona-carga');
        zona.addEventListener('click', () => {
            const inp = document.createElement('input');
            inp.type = 'file'; inp.accept = '.pdf';
            inp.onchange = e => { if (e.target.files[0]) manejarArchivo(e.target.files[0]); };
            inp.click();
        });
        zona.addEventListener('dragover', e => { e.preventDefault(); zona.classList.add('drag-over'); });
        zona.addEventListener('dragleave', () => zona.classList.remove('drag-over'));
        zona.addEventListener('drop', e => {
            e.preventDefault(); zona.classList.remove('drag-over');
            if (e.dataTransfer.files[0]) manejarArchivo(e.dataTransfer.files[0]);
        });
    }
}

function inicializarPresets() {
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const p = btn.dataset.preset;
            estado.preset = p;
            document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            if (p !== 'personalizado') {
                aplicarPreset(p);
            }
            actualizarEstimacion();
        });
    });
}

function inicializarCheckboxes() {
    // Mostrar/ocultar controles inline de imágenes
    document.getElementById('reimagenes').addEventListener('change', function () {
        document.getElementById('ctrl-imagenes').style.display = this.checked ? 'flex' : 'none';
        if (estado.preset !== 'personalizado') _cambiarAPersonalizado();
        actualizarEstimacion();
    });

    // Todos los demás checkboxes → cambiar a personalizado + recalcular
    Object.keys(CHECKBOXES).forEach(id => {
        if (id === 'reimagenes') return; // ya está arriba
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', () => {
                if (estado.preset !== 'personalizado') _cambiarAPersonalizado();
                actualizarEstimacion();
            });
        }
    });

    // Selects de DPI y calidad
    ['dpi', 'calidad-jpeg'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', () => {
            if (estado.preset !== 'personalizado') _cambiarAPersonalizado();
            actualizarEstimacion();
        });
    });
}

function _cambiarAPersonalizado() {
    estado.preset = 'personalizado';
    document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
    document.querySelector('.preset-btn[data-preset="personalizado"]').classList.add('active');
}


// ── Subida de archivo ────────────────────────────────────────────────────────
async function manejarArchivo(file) {
    // Validar PDF
    if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
        mostrarMensaje('Solo se aceptan archivos PDF.', 'error');
        return;
    }

    ocultarTodo();
    mostrar('progreso-carga');

    if (window.PDFExport?.FileUploader) {
        const uploader = new window.PDFExport.FileUploader({
            onProgress: pct => {
                document.getElementById('barra-subida').style.width = pct + '%';
                document.getElementById('pct-subida').textContent = pct + '%';
            },
            onComplete: data => {
                ocultar('progreso-carga');
                analizarArchivo(data);
            },
            onError: err => {
                ocultar('progreso-carga');
                mostrar('zona-carga');
                mostrarMensaje(err, 'error');
            },
        });
        try { await uploader.subirArchivo(file); }
        catch (e) { ocultar('progreso-carga'); mostrar('zona-carga'); mostrarMensaje(e.message, 'error'); }
    } else {
        // Fallback fetch
        const fd = new FormData();
        fd.append('archivo', file);
        fd.append('nombre', file.name);
        fd.append('tamano', file.size);
        fd.append('fecha_modificacion', new Date(file.lastModified).toISOString());
        try {
            const r = await fetch(`${API}/upload`, { method: 'POST', body: fd });
            const j = await r.json();
            ocultar('progreso-carga');
            if (j.success) analizarArchivo(j.data);
            else { mostrar('zona-carga'); mostrarMensaje(j.error?.message || 'Error al subir', 'error'); }
        } catch (e) {
            ocultar('progreso-carga'); mostrar('zona-carga'); mostrarMensaje(e.message, 'error');
        }
    }
}

async function analizarArchivo(data) {
    console.log('[compress] analizarArchivo inicio, id:', data?.id);
    estado.archivoId = data.id;
    estado.nombreArchivo = data.nombre_original;
    estado.tamanoOriginal = data.tamano_bytes;

    mostrar('progreso-analisis');

    try {
        const r = await fetch(`${API}/convert/compress/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_id: estado.archivoId }),
        });
        const j = await r.json();
        console.log('[compress] analyze response:', j?.success, 'data keys:', j?.data ? Object.keys(j.data) : null);
        if (j.success && j.data) {
            estado.analisis = j.data;
        } else {
            console.warn('[compress] Analyze sin datos:', j);
            estado.analisis = null;
        }
    } catch (e) {
        console.error('[compress] Error en petición de análisis:', e);
        estado.analisis = null;
    } finally {
        ocultar('progreso-analisis');
    }

    console.log('[compress] mostrando paneles...');
    // Siempre mostrar la UI, con o sin análisis
    try { mostrarPanelInfo(data, estado.analisis); } catch (e) { console.error('[compress] mostrarPanelInfo:', e); }
    try { aplicarPreset(estado.preset); } catch (e) { console.error('[compress] aplicarPreset:', e); }
    try { actualizarEstimacion(); } catch (e) { console.error('[compress] actualizarEstimacion:', e); }
    mostrar('panel-info');
    mostrar('panel-opciones');
    console.log('[compress] panel-info hidden:', document.getElementById('panel-info')?.hidden, 'panel-opciones hidden:', document.getElementById('panel-opciones')?.hidden);

    if (!estado.analisis) {
        mostrarMensaje('Análisis no disponible — se usarán valores por defecto.', 'info');
    }
}

function mostrarPanelInfo(data, analisis) {
    document.getElementById('nom-archivo').textContent = data.nombre_original;
    document.getElementById('num-paginas').textContent = data.num_paginas || '—';
    document.getElementById('tam-original').textContent = formatBytes(data.tamano_bytes);

    if (analisis) {
        const img = analisis.imagenes;
        document.getElementById('chip-imagenes').textContent =
            `${img.total} (${img.porcentaje_del_pdf}%)`;
        document.getElementById('chip-fuentes').textContent =
            `${analisis.fuentes.total} (${analisis.fuentes.embebidas} emb.)`;
        document.getElementById('chip-meta').textContent =
            analisis.metadatos.tiene_xmp ? 'XMP presente' : 'Sin XMP';
        document.getElementById('chip-anot').textContent =
            `${analisis.interactivo.anotaciones}`;
        document.getElementById('chip-marc').textContent =
            `${analisis.navegacion.marcadores}`;
        document.getElementById('chip-adj').textContent =
            `${analisis.interactivo.adjuntos}`;

        // Mostrar badges de ahorro en cada categoría
        const mapaBadges = {
            'sav-imagenes':   analisis.imagenes.ahorro_estimado_pct,
            'sav-fuentes':    analisis.fuentes.ahorro_estimado_pct,
            'sav-meta':       analisis.metadatos.ahorro_estimado_pct,
            'sav-estructura': analisis.estructura.ahorro_estimado_pct,
            'sav-interactivo':analisis.interactivo.ahorro_estimado_pct,
            'sav-navegacion': analisis.navegacion.ahorro_estimado_pct,
            'sav-transmision':analisis.optimizacion.ahorro_estimado_pct,
        };
        Object.entries(mapaBadges).forEach(([id, pct]) => {
            const el = document.getElementById(id);
            if (el && pct > 0) {
                el.textContent = `~${pct}%`;
                el.classList.add('visible');
            }
        });
    }
}


// ── Presets → checkboxes ─────────────────────────────────────────────────────
function aplicarPreset(nombre) {
    const p = PRESETS[nombre];
    if (!p) return;

    Object.entries(CHECKBOXES).forEach(([elId, key]) => {
        const el = document.getElementById(elId);
        if (el && !el.disabled && key in p) {
            el.checked = p[key];
        }
    });

    // Controles inline de imágenes
    const dpiEl = document.getElementById('dpi');
    const calEl = document.getElementById('calidad-jpeg');
    if (dpiEl && p.dpi) dpiEl.value = String(p.dpi);
    if (calEl && p.calidad_jpeg) calEl.value = String(p.calidad_jpeg);

    // Mostrar/ocultar ctrl-imagenes
    const ctrl = document.getElementById('ctrl-imagenes');
    if (ctrl) ctrl.style.display = p.reimagenes ? 'flex' : 'none';
}


// ── Estimación de ahorro ─────────────────────────────────────────────────────
function actualizarEstimacion() {
    const an = estado.analisis;
    if (!an) {
        document.getElementById('est-pct').textContent = '—';
        return;
    }

    let pct = 0;

    if (document.getElementById('reimagenes')?.checked ||
        document.getElementById('grises')?.checked) {
        const factorDpi = Math.min(1, parseInt(document.getElementById('dpi')?.value || 150) / 150);
        const factorCal = parseInt(document.getElementById('calidad-jpeg')?.value || 85) / 100;
        const ratio = 1 - (factorDpi * factorCal * 0.85); // reducción relativa
        pct += Math.round(an.imagenes.porcentaje_del_pdf * ratio);
        if (document.getElementById('grises')?.checked) pct += Math.round(an.imagenes.porcentaje_del_pdf * 0.15);
    }

    if (document.getElementById('subset-fuentes')?.checked ||
        document.getElementById('dedup-fuentes')?.checked) {
        pct += an.fuentes.ahorro_estimado_pct;
    }

    if (document.getElementById('garbage')?.checked ||
        document.getElementById('comprimir-streams')?.checked) {
        pct += an.estructura.ahorro_estimado_pct;
    }

    if (document.getElementById('eliminar-xmp')?.checked ||
        document.getElementById('eliminar-thumbnails')?.checked) {
        pct += an.metadatos.ahorro_estimado_pct;
    }

    if (document.getElementById('eliminar-anotaciones')?.checked ||
        document.getElementById('eliminar-adjuntos')?.checked) {
        pct += an.interactivo.ahorro_estimado_pct;
    }

    if (document.getElementById('eliminar-marcadores')?.checked ||
        document.getElementById('eliminar-ocg')?.checked) {
        pct += an.navegacion.ahorro_estimado_pct;
    }

    pct = Math.max(1, Math.min(92, pct));

    const tamFinal = Math.round(estado.tamanoOriginal * (1 - pct / 100));
    document.getElementById('est-pct').textContent = `~${pct}% menos`;
    document.getElementById('est-tamano-txt').textContent =
        `${formatBytes(estado.tamanoOriginal)} → ~${formatBytes(tamFinal)}`;
}


// ── Leer opciones del formulario ─────────────────────────────────────────────
function leerOpciones() {
    const opts = { preset: estado.preset };

    Object.entries(CHECKBOXES).forEach(([elId, key]) => {
        const el = document.getElementById(elId);
        if (el && !el.disabled) opts[key] = el.checked;
    });

    opts.dpi          = parseInt(document.getElementById('dpi')?.value || '150');
    opts.calidad_jpeg = parseInt(document.getElementById('calidad-jpeg')?.value || '85');

    return opts;
}


// ── Compresión ────────────────────────────────────────────────────────────────
async function ejecutarCompresion() {
    if (estado.procesando || !estado.archivoId) return;

    estado.procesando = true;
    document.getElementById('btn-comprimir').disabled = true;
    ocultar('resultado-card');
    ocultar('msg-estado');

    mostrar('progreso-proceso');
    _setProgreso(0, 'Iniciando...');

    try {
        const r = await fetch(`${API}/convert/compress`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_id: estado.archivoId, opciones: leerOpciones() }),
        });
        const j = await r.json();
        if (!j.success) throw new Error(j.error?.message || 'Error al iniciar compresión');

        const jobId = j.data.job_id;
        monitorearTrabajo(jobId);

    } catch (e) {
        _finProceso();
        mostrarMensaje(e.message, 'error');
    }
}

function monitorearTrabajo(jobId) {
    if (window.PDFExport?.monitorearProgreso) {
        window.PDFExport.monitorearProgreso(
            jobId,
            (pct, msg) => _setProgreso(pct, msg),
            (id, resultado) => {
                _finProceso();
                mostrarResultado(resultado);
                window.PDFExport.descargarResultado(id);
            },
            (err) => { _finProceso(); mostrarMensaje(err, 'error'); }
        );
        return;
    }

    // Fallback polling manual
    const intervalo = setInterval(async () => {
        try {
            const r = await fetch(`${API}/jobs/${jobId}`);
            const j = await r.json();
            if (!j.success) return;
            const job = j.data;

            _setProgreso(job.progreso || 0, job.mensaje || 'Procesando...');

            if (job.estado === 'completado') {
                clearInterval(intervalo);
                _finProceso();
                mostrarResultado({ mensaje: job.mensaje });
                window.location.href = `${API}/download/${jobId}`;
            } else if (job.estado === 'error') {
                clearInterval(intervalo);
                _finProceso();
                mostrarMensaje(job.mensaje || 'Error en la compresión', 'error');
            }
        } catch (e) {
            clearInterval(intervalo);
            _finProceso();
            mostrarMensaje(e.message, 'error');
        }
    }, 1500);
}

function _setProgreso(pct, msg) {
    document.getElementById('barra-proceso').style.width = pct + '%';
    document.getElementById('pct-proceso').textContent = pct + '%';
    document.getElementById('txt-proceso').textContent = msg;
}

function _finProceso() {
    estado.procesando = false;
    document.getElementById('btn-comprimir').disabled = false;
    ocultar('progreso-proceso');
}


// ── Resultado ────────────────────────────────────────────────────────────────
function mostrarResultado(resultado) {
    // El servicio devuelve tamano_original, tamano_final y reduccion_pct en el mensaje
    // También puede venir en el objeto resultado si monitorearProgreso lo provee
    const orig = resultado?.tamano_original || estado.tamanoOriginal;
    const final = resultado?.tamano_final;
    const pct = resultado?.reduccion_pct;

    if (final && pct !== undefined) {
        document.getElementById('res-original').textContent = formatBytes(orig);
        document.getElementById('res-final').textContent = formatBytes(final);
        document.getElementById('res-reduccion').textContent = `–${pct}%`;
        mostrar('resultado-card');
    } else if (resultado?.mensaje) {
        // Parsear del mensaje "X → Y (Z% reducción)"
        const m = resultado.mensaje.match(/([^\s]+)\s*→\s*([^\s]+)\s*\(([0-9.]+)%/);
        if (m) {
            document.getElementById('res-original').textContent = m[1];
            document.getElementById('res-final').textContent = m[2];
            document.getElementById('res-reduccion').textContent = `–${m[3]}%`;
            mostrar('resultado-card');
        }
    }

    mostrarMensaje('PDF comprimido. Descargando...', 'success');
}


// ── Acorde ón ────────────────────────────────────────────────────────────────
function toggleCat(bodyId, header) {
    const body = document.getElementById(bodyId);
    const isOpen = body.classList.toggle('open');
    header.classList.toggle('open', isOpen);
}


// ── Helpers de UI ────────────────────────────────────────────────────────────
function mostrar(id) {
    const el = document.getElementById(id);
    if (el) el.hidden = false;
}

function ocultar(id) {
    const el = document.getElementById(id);
    if (el) el.hidden = true;
}

function ocultarTodo() {
    ['zona-carga','panel-info','panel-opciones','progreso-carga',
     'progreso-analisis','progreso-proceso','msg-estado','resultado-card']
        .forEach(ocultar);
}

function mostrarMensaje(texto, tipo) {
    const el = document.getElementById('msg-estado');
    el.textContent = texto;
    el.className = `status-message ${tipo}`;
    el.hidden = false;
    setTimeout(() => { el.hidden = true; }, tipo === 'error' ? 7000 : 4000);
}

function reiniciar() {
    estado.archivoId = null;
    estado.analisis = null;
    estado.procesando = false;
    ocultarTodo();
    mostrar('zona-carga');
    // Limpiar chips
    ['chip-imagenes','chip-fuentes','chip-meta','chip-anot','chip-marc','chip-adj']
        .forEach(id => { const el = document.getElementById(id); if (el) el.textContent = '—'; });
    // Resetear badges
    ['sav-imagenes','sav-fuentes','sav-meta','sav-estructura','sav-interactivo','sav-navegacion','sav-transmision']
        .forEach(id => { const el = document.getElementById(id); if (el) { el.textContent = ''; el.classList.remove('visible'); } });
    // Preset a estándar
    estado.preset = 'estandar';
    document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
    document.querySelector('.preset-btn[data-preset="estandar"]').classList.add('active');
    aplicarPreset('estandar');
    document.getElementById('est-pct').textContent = '—';
    document.getElementById('est-tamano-txt').textContent = '';
}

function formatBytes(bytes) {
    if (window.formatBytes) return window.formatBytes(bytes);
    if (!bytes) return '0 B';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
    return (bytes / 1073741824).toFixed(2) + ' GB';
}
