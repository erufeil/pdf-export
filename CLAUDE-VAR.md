# CLAUDE-VAR.md — Contratos de API, esquemas y valores

> Leer este archivo al inicio de cada sesión (instrucción en CLAUDE.md).
> Valores exactos verificados en el código. No asumir — consultar aquí.

---

## 1. Esquema de base de datos SQLite (`data/pdfexport.db`)

### Tabla `archivos`
| Columna            | Tipo    | Notas                                      |
|--------------------|---------|--------------------------------------------|
| `id`               | TEXT PK | UUID v4                                    |
| `nombre_original`  | TEXT    | Nombre con extensión tal como lo subió el usuario |
| `nombre_guardado`  | TEXT    | `{uuid}.pdf` — nombre en disco            |
| `tamano_bytes`     | INTEGER |                                            |
| `fecha_modificacion` | TEXT  | ISO format — fecha del archivo original    |
| `num_paginas`      | INTEGER | 0 para no-PDF                              |
| `hash_archivo`     | TEXT    | MD5 del contenido                          |
| `fecha_subida`     | TEXT    | ISO format — momento del upload            |
| `ruta_archivo`     | TEXT    | Ruta absoluta en disco                     |

### Tabla `trabajos`
| Columna            | Tipo    | Notas                                      |
|--------------------|---------|--------------------------------------------|
| `id`               | TEXT PK | UUID v4                                    |
| `archivo_id`       | TEXT FK | Referencia a `archivos.id` (puede ser NULL para scrape) |
| `tipo_conversion`  | TEXT    | Ver tabla de procesadores en CLAUDE-CODE.md |
| `estado`           | TEXT    | `'pendiente'` \| `'procesando'` \| `'completado'` \| `'error'` \| `'cancelado'` |
| `progreso`         | INTEGER | 0–100                                      |
| `mensaje`          | TEXT    | Texto de estado para mostrar al usuario    |
| `parametros`       | TEXT    | JSON serializado                           |
| `ruta_resultado`   | TEXT    | Ruta absoluta al ZIP de salida             |
| `fecha_creacion`   | TEXT    | ISO format                                 |
| `fecha_inicio`     | TEXT    | ISO format — cuando empieza a procesar     |
| `fecha_fin`        | TEXT    | ISO format — cuando termina               |

---

## 2. Endpoints de archivos

### `POST /api/v1/upload`

**Request** — `multipart/form-data`:
```
archivo           : File    ← campo OBLIGATORIO, nombre siempre 'archivo'
nombre            : string  ← nombre original (opcional, fallback a archivo.filename)
tamano            : int     ← tamaño en bytes (para detección de duplicados)
fecha_modificacion: string  ← ISO format (para detección de duplicados)
```

**Response exitosa** — `resp.data` contiene:
```json
{
  "id": "uuid-v4",
  "nombre_original": "documento.pdf",
  "nombre_guardado": "uuid.pdf",
  "tamano_bytes": 1048576,
  "num_paginas": 45,
  "ruta": "/ruta/absoluta/uploads/uuid.pdf",
  "ya_existia": false
}
```

---

### `GET /api/v1/files`

**Response exitosa** — `resp.data` es un array:
```json
[
  {
    "id": "uuid-v4",
    "nombre_original": "documento.pdf",
    "tamano_bytes": 1048576,
    "num_paginas": 45,
    "fecha_subida": "2024-01-15T10:30:00"
  }
]
```

---

### `GET /api/v1/files/{id}`

**Response exitosa** — `resp.data` contiene:
```json
{
  "id": "uuid-v4",
  "nombre_original": "documento.pdf",
  "tamano_bytes": 1048576,
  "num_paginas": 45,
  "fecha_subida": "2024-01-15T10:30:00",
  "fecha_modificacion": "2024-01-10T08:00:00"
}
```

---

### `GET /api/v1/files/{id}/thumbnail/{pagina}`

- `pagina`: **1-indexed** (página 1 = `/thumbnail/1`)
- Response: imagen PNG binaria directa (`Content-Type: image/png`)
- Error: HTTP 404/500 con JSON `{ success: false, error: {...} }`

---

### `GET /api/v1/download/{job_id}`

- Descarga directa del ZIP de resultado
- Response: archivo ZIP binario
- Nombre del ZIP incluido en `Content-Disposition`

---

## 3. Endpoints de conversión — formato estándar

**Request** — todos usan `Content-Type: application/json`:
```json
{
  "file_id": "uuid-del-archivo",
  "opciones": { ... }
}
```

**Response exitosa** — `resp.data` contiene:
```json
{
  "job_id": "uuid-del-trabajo"
}
```

**Response de error**:
```json
{
  "success": false,
  "error": {
    "code": "CODIGO_ERROR",
    "message": "Descripción legible del error"
  }
}
```

---

## 4. Endpoints de trabajos

### `GET /api/v1/jobs/{id}`

**Response exitosa** — `resp.data` contiene:
```json
{
  "id": "uuid-v4",
  "archivo_id": "uuid-archivo",
  "tipo_conversion": "to-png",
  "estado": "procesando",
  "progreso": 45,
  "mensaje": "Convirtiendo página 3 de 10",
  "fecha_creacion": "2024-01-15T10:30:00",
  "fecha_inicio": "2024-01-15T10:30:01",
  "fecha_fin": null,
  "nombre_archivo": "documento.pdf"
}
```

**Estados posibles**: `pendiente` → `procesando` → `completado` | `error` | `cancelado`

---

### `GET /api/v1/jobs`

**Response exitosa** — `resp.data` es un array de trabajos (mismo formato que arriba).

---

## 5. Parámetros específicos por conversión

### `POST /api/v1/convert/to-txt`
```json
{
  "file_id": "uuid",
  "opciones": {
    "remover_numeros_pagina": true,
    "remover_encabezados": true,
    "remover_pies_pagina": true,
    "preservar_parrafos": true,
    "detectar_columnas": false
  }
}
```

### `POST /api/v1/convert/to-png` / `to-jpg`
```json
{
  "file_id": "uuid",
  "opciones": {
    "dpi": 150,
    "calidad": 85,
    "paginas": "all",
    "paginas_especificas": null
  }
}
```

### `POST /api/v1/convert/compress`
```json
{
  "file_id": "uuid",
  "opciones": {
    "nivel": "media",
    "dpi_maximo": 120,
    "calidad_jpg": 75,
    "eliminar_metadatos": true,
    "eliminar_anotaciones": false,
    "eliminar_bookmarks": false,
    "escala_grises": false
  }
}
```

### `POST /api/v1/convert/split`
```json
{
  "file_id": "uuid",
  "cortes": [
    {"inicio": 1, "fin": 50},
    {"inicio": 51, "fin": 100}
  ]
}
```

### `POST /api/v1/convert/rotate`
```json
{
  "file_id": "uuid",
  "rotaciones": {
    "1": 90,
    "3": 180,
    "5": 270
  }
}
```

### `POST /api/v1/convert/extract-pages`
```json
{
  "file_id": "uuid",
  "paginas": [1, 3, 5, 6, 7, 8, 9, 10, 15],
  "formato_salida": "unico"
}
```
- `formato_salida`: `"unico"` (un PDF) | `"separados"` (un PDF por página)

### `POST /api/v1/convert/reorder`
```json
{
  "file_id": "uuid",
  "nuevo_orden": [3, 1, 2, 5, 4, 6, 7, 8]
}
```
- `nuevo_orden`: array de números de página **1-indexed** en el nuevo orden

### `POST /api/v1/convert/merge`
```json
{
  "archivos": [
    {"file_id": "uuid-1", "orden": 1},
    {"file_id": "uuid-2", "orden": 2}
  ],
  "opciones": {
    "agregar_marcadores": true
  }
}
```

### `POST /api/v1/convert/extract-images`
```json
{
  "file_id": "uuid",
  "opciones": {
    "formato_salida": "original",
    "imagenes_seleccionadas": ["img_1", "img_3"],
    "tamano_minimo_px": 100
  }
}
```

### `POST /api/v1/convert/from-html`
```json
{
  "url": "https://ejemplo.com/pagina",
  "opciones": {
    "tamano_pagina": "A4",
    "orientacion": "vertical",
    "margenes": "normales",
    "incluir_fondo": true,
    "solo_contenido": false
  }
}
```

### `POST /api/v1/convert/scrape-url`
```json
{
  "url": "https://ejemplo.com/articulo",
  "opciones": {
    "formato_salida": "markdown",
    "eliminar_enlaces": false,
    "incluir_metadatos": true,
    "incluir_contenido": true,
    "incluir_footer": true,
    "incluir_links": true
  }
}
```

### `POST /api/v1/convert/ndm-to-tables-seq`
```json
{
  "file_id": "uuid",
  "opciones": {
    "sin_comprimir": true
  }
}
```

---

## 6. Configuración (`config.py`)

| Variable                  | Descripción                              |
|---------------------------|------------------------------------------|
| `config.UPLOAD_FOLDER`    | `Path` a carpeta `uploads/`              |
| `config.OUTPUT_FOLDER`    | `Path` a carpeta `outputs/`              |
| `config.DATABASE_PATH`    | `Path` a `data/pdfexport.db`             |
| `config.MAX_CONTENT_LENGTH` | 1 GB (1073741824 bytes)                |
| `config.FILE_RETENTION_HOURS` | 4 horas                            |
| `config.THUMBNAIL_DPI`    | DPI para miniaturas (default bajo)       |
| `config.ALLOWED_EXTENSIONS` | Set con extensiones permitidas         |

---

## 7. Respuesta estándar completa

```json
{
  "success": true,
  "data": { ... },
  "message": "Operacion completada"
}
```

```json
{
  "success": false,
  "error": {
    "code": "CODIGO_MAYUSCULAS",
    "message": "Descripción del error para el usuario"
  }
}
```

### Códigos de error comunes
| Código                | Significado                         |
|-----------------------|-------------------------------------|
| `NO_DATA`             | Body del request vacío o no JSON    |
| `MISSING_FILE_ID`     | Falta el campo `file_id`            |
| `FILE_NOT_FOUND`      | El `file_id` no existe en la BD     |
| `NO_FILE`             | No se envió campo `archivo` en form |
| `INVALID_EXTENSION`   | Extensión no permitida              |
| `SAVE_ERROR`          | Error al guardar en disco           |
| `NOT_IMPLEMENTED`     | Etapa aún no desarrollada (501)     |
