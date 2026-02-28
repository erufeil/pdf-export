# CLAUDE-CODE.md — Patrones de implementación verificados

> Leer este archivo al inicio de cada sesión (instrucción en CLAUDE.md).
> Solo contiene patrones confirmados en el código real, no suposiciones.

---

## 1. Helpers de respuesta HTTP (`api/routes_convert.py` y `api/routes_files.py`)

```python
# SOLO 2 parámetros. Siempre devuelve HTTP 200.
respuesta_exitosa(data=None, mensaje="Operacion completada")
# Ejemplo:
return respuesta_exitosa({'job_id': trabajo_id}, 'Trabajo encolado')

# 3 parámetros. El status_code es el tercero (default 400).
respuesta_error(codigo: str, mensaje: str, status_code: int = 400)
# Ejemplo:
return respuesta_error('NOT_FOUND', 'Archivo no encontrado', 404)

# validar_archivo devuelve tupla (archivo_dict, None) o (None, respuesta_error)
archivo, error = validar_archivo(archivo_id)
if error:
    return error
```

---

## 2. Job Manager (`utils/job_manager.py`)

```python
# Encolar un trabajo — devuelve trabajo_id (str UUID)
trabajo_id = job_manager.encolar_trabajo(
    archivo_id=archivo_id,          # str UUID del archivo
    tipo_conversion='reorder',      # str — debe coincidir con procesador registrado
    parametros={'clave': valor}     # dict — se serializa a JSON internamente
)

# Actualizar progreso desde dentro del procesador
job_manager.actualizar_progreso(trabajo_id, 50, "Mensaje de estado")

# Registrar procesador al final del archivo services/mi_servicio.py
job_manager.registrar_procesador('tipo-conversion', funcion_procesadora)
```

---

## 3. File Manager (`utils/file_manager.py`)

```python
# Crear ZIP con máxima compresión
# archivos: lista de tuplas (ruta_str, nombre_dentro_del_zip)
ruta_zip = file_manager.crear_zip(archivos, nombre_zip)
# Devuelve: Path al ZIP en config.OUTPUT_FOLDER

# Generar miniatura PNG de una página (0-indexed)
png_bytes = file_manager.generar_miniatura(ruta_pdf: Path, pagina: int = 0)
# Devuelve: bytes PNG o None si falla

# Buscar duplicado
archivo = file_manager.buscar_archivo_duplicado(nombre, tamano, fecha_mod)
# Devuelve: dict del archivo o None
```

---

## 4. Models (`models.py`)

```python
# Obtener archivo por ID — devuelve dict o None
archivo = models.obtener_archivo(archivo_id)

# Obtener trabajo por ID — devuelve dict o None
trabajo = models.obtener_trabajo(trabajo_id)

# Actualizar trabajo — todos los parámetros son opcionales excepto trabajo_id
models.actualizar_trabajo(
    trabajo_id,
    estado='completado',    # 'pendiente'|'procesando'|'completado'|'error'|'cancelado'
    progreso=100,           # int 0-100
    mensaje='Listo',        # str
    ruta_resultado='/path'  # str
)
```

---

## 5. Patrón completo para crear un nuevo servicio

### `services/pdf_nuevo_servicio.py`
```python
import config, models
from utils import file_manager, job_manager
from pathlib import Path
import fitz

def procesar_nuevo_servicio(trabajo_id: str, archivo_id: str, parametros: dict) -> dict:
    archivo = models.obtener_archivo(archivo_id)
    if not archivo:
        raise ValueError("Archivo no encontrado")

    ruta_pdf = Path(archivo['ruta_archivo'])
    nombre_original = archivo['nombre_original']

    job_manager.actualizar_progreso(trabajo_id, 5, "Iniciando")

    # ... lógica ...

    job_manager.actualizar_progreso(trabajo_id, 95, "Comprimiendo")

    nombre_zip = f"{trabajo_id}_{Path(nombre_original).stem}_tipo.zip"
    archivos_para_zip = [(str(ruta_salida), ruta_salida.name.replace(f"{trabajo_id}_", ""))]
    ruta_zip = file_manager.crear_zip(archivos_para_zip, nombre_zip)

    # Limpiar temporales
    if ruta_salida.exists():
        ruta_salida.unlink()

    return {
        'ruta_resultado': str(ruta_zip),
        'mensaje': 'Conversión completada'
    }

# SIEMPRE al final del archivo — registra el procesador
job_manager.registrar_procesador('tipo-conversion', procesar_nuevo_servicio)
```

### `api/routes_convert.py` — endpoint para el nuevo servicio
```python
@bp.route('/nuevo-servicio', methods=['POST'])
def convertir_nuevo_servicio():
    datos = request.get_json()
    if not datos:
        return respuesta_error('NO_DATA', 'No se enviaron datos')

    archivo_id = datos.get('file_id')
    archivo, error = validar_archivo(archivo_id)
    if error:
        return error

    trabajo_id = job_manager.encolar_trabajo(
        archivo_id=archivo_id,
        tipo_conversion='tipo-conversion',
        parametros={...}
    )
    return respuesta_exitosa({'job_id': trabajo_id}, 'Trabajo encolado')
```

### `app.py` — importar el nuevo servicio
```python
# Agregar a la línea de imports de servicios:
from services import ..., pdf_nuevo_servicio, ...
```

---

## 6. Patrón de upload en el frontend (JavaScript)

```javascript
// Campo de archivo SIEMPRE se llama 'archivo' (no 'file')
const formData = new FormData();
formData.append('archivo', file);          // ← campo obligatorio
formData.append('nombre', file.name);      // ← opcional pero recomendado
formData.append('tamano', file.size);      // ← para detección de duplicados
formData.append('fecha_modificacion', new Date(file.lastModified).toISOString());

const xhr = new XMLHttpRequest();
xhr.open('POST', `${API}/upload`);
xhr.onload = () => {
    const resp = JSON.parse(xhr.responseText);
    if (resp.success) {
        const a = resp.data;   // ← datos directamente en resp.data (NO resp.data.archivo)
        const id          = a.id;
        const numPaginas  = a.num_paginas;
        const nombre      = a.nombre_original;
        const tamano      = a.tamano_bytes;
        const yaExistia   = a.ya_existia;  // true si era duplicado
    }
};
xhr.send(formData);
```

---

## 7. Patrón de polling de jobs en el frontend (JavaScript)

```javascript
function esperarTrabajo(jobId) {
    const intervalo = setInterval(async () => {
        const r = await fetch(`${API}/jobs/${jobId}`);
        const data = await r.json();
        const job = data.data;

        // Campos disponibles en job:
        // job.estado:   'pendiente' | 'procesando' | 'completado' | 'error'
        // job.progreso: 0-100
        // job.mensaje:  string de estado

        barraProgreso.style.width = (job.progreso || 0) + '%';
        textoEstado.textContent = job.mensaje || 'Procesando...';

        if (job.estado === 'completado') {
            clearInterval(intervalo);
            window.location.href = `${API}/download/${jobId}`;
        } else if (job.estado === 'error') {
            clearInterval(intervalo);
            alert('Error: ' + job.mensaje);
        }
    }, 1500);  // polling cada 1500ms
}
```

---

## 8. Endpoint de miniaturas

```
GET /api/v1/files/{archivo_id}/thumbnail/{pagina}

- pagina: 1-indexed (la página 1 del PDF = thumbnail/1)
- Devuelve: imagen PNG directamente (Content-Type: image/png)
- Si falla: HTTP 404 o 500
```

```javascript
// Cargar miniatura en un <img>
img.src = `${API}/files/${archivoId}/thumbnail/${numPagina}`;

// O como blob para mayor control:
const r = await fetch(`${API}/files/${archivoId}/thumbnail/${numPagina}`);
if (r.ok) {
    const blob = await r.blob();
    img.src = URL.createObjectURL(blob);
}
```

---

## 9. Procesadores registrados en `app.py`

| Tipo (string)      | Servicio                        |
|--------------------|---------------------------------|
| `'split'`          | pdf_split                       |
| `'to-txt'`         | pdf_to_txt                      |
| `'to-docx'`        | pdf_to_docx                     |
| `'to-png'`         | pdf_to_images                   |
| `'to-jpg'`         | pdf_to_images                   |
| `'compress'`       | pdf_compress                    |
| `'extract-images'` | pdf_extract_images              |
| `'rotate'`         | pdf_rotate                      |
| `'from-html'`      | html_to_pdf                     |
| `'merge'`          | pdf_merge                       |
| `'extract-pages'`  | pdf_extract_pages               |
| `'reorder'`        | pdf_reorder                     |
| `'ndm-to-tables-seq'` | ndm_to_tables_seq            |
| `'scrape-url'`     | web_scraper                     |
| `'to-csv'`         | pdf_to_csv (pendiente)          |
| `'img-to-1pdf'`    | img_to_1pdf (pendiente)         |

---

## 10. Convención de nombres de archivos de salida

```
# Archivo individual:
{trabajo_id}_{nombre_original} - {descripcion}.{ext}

# ZIP de salida:
{trabajo_id}_{nombre_base_sin_ext}_{tipo}.zip

# Dentro del ZIP (sin el trabajo_id al inicio):
{nombre_original} - {descripcion}.{ext}
```

Padding de números: tantos dígitos como el total de elementos.
- 8 elementos → 1 dígito (1, 2, ..., 8)
- 15 elementos → 2 dígitos (01, 02, ..., 15)
- 100 elementos → 3 dígitos (001, 002, ..., 100)
