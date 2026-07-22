# API Reference — PDF Export & Import

> Referencia técnica completa para desarrolladores. Para la guía de usuario final, ver [NOTAS-USUARIO.md](NOTAS-USUARIO.md).

**Base URL:** `http://HOST:PORT/api/v1`

Todos los endpoints retornan JSON. Los endpoints de conversión son asíncronos (retornan `job_id`) salvo que se indique **Síncrono** explícitamente.

---

## Flujo general

```
POST /upload              →  file_id
POST /convert/...         →  job_id   (o resultado directo si es síncrono)
GET  /jobs/{job_id}       →  estado del trabajo
GET  /download/{job_id}   →  archivo resultante
```

## Formato de respuesta

**Éxito:**
```json
{
  "success": true,
  "data": { ... },
  "message": "descripción"
}
```

**Error:**
```json
{
  "success": false,
  "error": {
    "code": "CODIGO_ERROR",
    "message": "descripción humana"
  }
}
```

Los trabajos asíncronos retornan `job` en lugar de `data`:
```json
{
  "success": true,
  "job": { "id": "abc123" },
  "message": "Trabajo iniciado"
}
```

---

## 1. Infraestructura

### POST /upload — Subir archivo

Sube un archivo al servidor. Si el mismo archivo (nombre + tamaño + fecha de modificación) ya existe, retorna el existente sin volver a subirlo.

```bash
# Subida básica
curl -X POST http://localhost:5000/api/v1/upload \
  -F "archivo=@documento.pdf"

# Con metadatos para detección de duplicados
curl -X POST http://localhost:5000/api/v1/upload \
  -F "archivo=@documento.pdf" \
  -F "nombre=documento.pdf" \
  -F "tamano=204800" \
  -F "fecha_modificacion=2026-01-15T10:30:00"
```

**Respuesta:**
```json
{
  "success": true,
  "data": {
    "id": "a1b2c3d4",
    "nombre_original": "documento.pdf",
    "tamano_bytes": 204800,
    "num_paginas": 45,
    "fecha_subida": "2026-01-15T10:30:00",
    "ya_existia": false
  }
}
```

Extensiones aceptadas: `pdf`, `ndm2`, `json`, `jpg`, `jpeg`, `png`, `gif`, `bmp`, `tiff`, `tif`, `webp`, `svg`, `eps`, `xlsx`, `xls`, `epub`, `wav`, `mp3`, `mp4`, `m4a`.

---

### GET /files — Listar archivos disponibles

```bash
curl http://localhost:5000/api/v1/files
```

---

### GET /files/{id} — Info de un archivo

```bash
curl http://localhost:5000/api/v1/files/a1b2c3d4
```

---

### DELETE /files/{id} — Eliminar un archivo

```bash
curl -X DELETE http://localhost:5000/api/v1/files/a1b2c3d4
```

---

### DELETE /files — Eliminar todos los archivos

```bash
curl -X DELETE http://localhost:5000/api/v1/files
```

---

### GET /files/{id}/thumbnail/{page} — Miniatura de página

Retorna imagen PNG directamente. `page` es 0-indexed.

```bash
curl http://localhost:5000/api/v1/files/a1b2c3d4/thumbnail/0 --output pagina1.png
```

---

### POST /check-duplicate — Verificar duplicado sin subir

```bash
curl -X POST http://localhost:5000/api/v1/check-duplicate \
  -H "Content-Type: application/json" \
  -d '{"nombre": "doc.pdf", "tamano": 204800, "fecha_modificacion": "2026-01-15T10:30:00"}'
```

---

### GET /status — Estado del servicio

```bash
curl http://localhost:5000/api/v1/status
```

---

### GET /jobs/{job_id} — Estado de un trabajo

```bash
curl http://localhost:5000/api/v1/jobs/JOB_ID
```

**Respuesta:**
```json
{
  "success": true,
  "data": {
    "id": "JOB_ID",
    "estado": "completado",
    "progreso": 100,
    "nombre_archivo": "resultado.txt"
  }
}
```

Estados posibles: `pendiente` | `procesando` | `completado` | `error`

---

### GET /jobs/{job_id}/progress — Progreso SSE

Stream de eventos Server-Sent Events. Permite monitorear un trabajo sin hacer polling.

```bash
curl -N http://localhost:5000/api/v1/jobs/JOB_ID/progress
```

Eventos emitidos:
```
data: {"progreso": 25, "estado": "procesando"}

data: {"progreso": 100, "estado": "completado", "nombre_archivo": "resultado.pdf"}

: keepalive
```

El servidor emite un comentario `: keepalive` cada 10 segundos cuando no hay cambios, para mantener la conexión TCP activa.

---

### GET /download/{job_id} — Descargar resultado

```bash
curl http://localhost:5000/api/v1/download/JOB_ID --output resultado.zip
```

---

## 2. Conversión PDF

### POST /convert/to-txt — PDF a texto plano

```bash
FILE_ID=$(curl -s -X POST http://localhost:5000/api/v1/upload \
  -F "archivo=@documento.pdf" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

JOB_ID=$(curl -s -X POST http://localhost:5000/api/v1/convert/to-txt \
  -H "Content-Type: application/json" \
  -d "{
    \"file_id\": \"$FILE_ID\",
    \"opciones\": {
      \"remover_numeros_pagina\": true,
      \"remover_encabezados\": true,
      \"remover_pies_pagina\": true,
      \"preservar_parrafos\": true,
      \"detectar_columnas\": false
    }
  }" | python3 -c "import sys,json; print(json.load(sys.stdin)['job']['id'])")

curl http://localhost:5000/api/v1/download/$JOB_ID --output documento.txt
```

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `remover_numeros_pagina` | bool | `true` | Elimina números de página |
| `remover_encabezados` | bool | `true` | Elimina texto repetido en parte superior |
| `remover_pies_pagina` | bool | `true` | Elimina texto repetido en parte inferior |
| `preservar_parrafos` | bool | `true` | Mantiene saltos de párrafo |
| `detectar_columnas` | bool | `false` | Maneja PDFs con múltiples columnas |

**Resultado:** TXT directo (sin ZIP).

---

### POST /convert/to-docx — PDF a Word

```bash
curl -X POST http://localhost:5000/api/v1/convert/to-docx \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "opciones": {
      "preservar_imagenes": true,
      "preservar_tablas": true,
      "preservar_estilos": true,
      "calidad_imagenes": "media"
    }
  }'
```

| Parámetro | Tipo | Opciones | Default |
|-----------|------|----------|---------|
| `preservar_imagenes` | bool | — | `true` |
| `preservar_tablas` | bool | — | `true` |
| `preservar_estilos` | bool | — | `true` |
| `calidad_imagenes` | string | `baja`, `media`, `alta`, `original` | `media` |

**Resultado:** DOCX directo (sin ZIP).

---

### POST /convert/to-png — PDF a imágenes PNG

```bash
# Todas las páginas a 150 DPI
curl -X POST http://localhost:5000/api/v1/convert/to-png \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "opciones": {"dpi": 150, "paginas": "all"}}'

# Rango de páginas
curl -X POST http://localhost:5000/api/v1/convert/to-png \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "opciones": {"dpi": 300, "paginas": "rango", "pagina_inicio": 3, "pagina_fin": 10}}'

# Páginas específicas
curl -X POST http://localhost:5000/api/v1/convert/to-png \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "opciones": {"dpi": 150, "paginas": "especificas", "paginas_especificas": "1,3,5-8"}}'
```

| Parámetro | Tipo | Opciones | Default |
|-----------|------|----------|---------|
| `dpi` | int | `72`, `150`, `300`, `600` | `150` |
| `paginas` | string | `all`, `rango`, `especificas` | `all` |
| `pagina_inicio` | int | número de página (base 1) | — |
| `pagina_fin` | int | número de página (base 1) | — |
| `paginas_especificas` | string | ej: `"1,3,5-10"` | `null` |

**Resultado:** ZIP con `documento - pagina 001.png`, `documento - pagina 002.png`, etc.

---

### POST /convert/to-jpg — PDF a imágenes JPG

```bash
curl -X POST http://localhost:5000/api/v1/convert/to-jpg \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "opciones": {"dpi": 150, "calidad": 85, "paginas": "all"}
  }'
```

| Parámetro | Tipo | Opciones | Default |
|-----------|------|----------|---------|
| `dpi` | int | `72`, `150`, `300`, `600` | `150` |
| `calidad` | int | `60`–`95` | `85` |
| `paginas` | string | `all`, `rango`, `especificas` | `all` |
| `pagina_inicio` | int | número de página (base 1) | — |
| `pagina_fin` | int | número de página (base 1) | — |
| `paginas_especificas` | string | ej: `"1,3,5-10"` | `null` |

**Resultado:** ZIP con imágenes JPG.

---

### POST /convert/to-csv — PDF a CSV (extracción de tablas)

```bash
curl -X POST http://localhost:5000/api/v1/convert/to-csv \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "opciones": {
      "unificar_iguales": true,
      "separador": ";",
      "saltos_linea": "CRLF"
    }
  }'
curl http://localhost:5000/api/v1/download/JOB_ID --output tablas.zip
```

| Parámetro | Tipo | Opciones | Default |
|-----------|------|----------|---------|
| `unificar_iguales` | bool | — | `true` |
| `separador` | string | `";"`, `","` | `";"` |
| `saltos_linea` | string | `"CRLF"`, `"LF"` | `"CRLF"` |

**Resultado:** ZIP con un CSV por tabla detectada.

---

### POST /convert/to-md — PDF a Markdown

```bash
curl -X POST http://localhost:5000/api/v1/convert/to-md \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "opciones": {}}'
curl http://localhost:5000/api/v1/download/JOB_ID --output documento.md
```

**Resultado:** MD directo (sin ZIP).

---

## 3. Edición PDF

### POST /convert/split — Cortar PDF

```bash
# Cortes definidos manualmente (máximo 20)
curl -X POST http://localhost:5000/api/v1/convert/split \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "opciones": {
      "cortes": [
        {"inicio": 1, "fin": 50},
        {"inicio": 51, "fin": 100}
      ]
    }
  }'

# N partes iguales
curl -X POST http://localhost:5000/api/v1/convert/split \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "opciones": {"num_partes": 4}}'
```

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `cortes` | array | Lista de `{"inicio": N, "fin": M}`. Máximo 20 cortes. |
| `num_partes` | int | Alternativa a `cortes`: divide en N partes iguales |

**Resultado:** ZIP con PDFs parciales (`documento - pag. 001 - 050.pdf`, etc.).

---

### POST /convert/merge — Unir PDFs

```bash
curl -X POST http://localhost:5000/api/v1/convert/merge \
  -H "Content-Type: application/json" \
  -d '{
    "archivos": [
      {"file_id": "FILE_ID_1", "orden": 1},
      {"file_id": "FILE_ID_2", "orden": 2},
      {"file_id": "FILE_ID_3", "orden": 3}
    ],
    "opciones": {"agregar_marcadores": true}
  }'
curl http://localhost:5000/api/v1/download/JOB_ID --output unificado.pdf
```

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `archivos` | array | — | Lista de `{"file_id": "...", "orden": N}`. El orden define la secuencia. |
| `agregar_marcadores` | bool | `true` | Agrega bookmarks con el nombre de cada archivo |

**Resultado:** PDF directo.

---

### POST /convert/rotate — Rotar páginas (Síncrono)

```bash
# Páginas específicas
curl -X POST http://localhost:5000/api/v1/convert/rotate \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "rotaciones": {"1": 90, "3": 180, "5": 270}}'

# Todas las páginas
curl -X POST http://localhost:5000/api/v1/convert/rotate \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "rotaciones": {}, "rotar_todas": 90}'
curl http://localhost:5000/api/v1/download/JOB_ID --output rotado.pdf
```

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `rotaciones` | objeto | Clave: número de página (string). Valor: `90`, `180` o `270` |
| `rotar_todas` | int | Rotación para todas las páginas: `90`, `180` o `270` |

**Resultado:** PDF directo.

---

### POST /convert/reorder — Reordenar páginas (Síncrono)

```bash
# [3, 1, 2] → la página 3 queda primera, luego la 1, luego la 2
curl -X POST http://localhost:5000/api/v1/convert/reorder \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "nuevo_orden": [3, 1, 2, 5, 4, 6]}'
curl http://localhost:5000/api/v1/download/JOB_ID --output reordenado.pdf
```

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `nuevo_orden` | array | Lista completa de números de página en el nuevo orden deseado |

**Resultado:** PDF directo.

---

### POST /convert/extract-pages — Extraer páginas

```bash
# Un único PDF con las páginas seleccionadas
curl -X POST http://localhost:5000/api/v1/convert/extract-pages \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "paginas": [1, 3, 5, 8], "formato_salida": "unico"}'

# Un PDF por página (en ZIP)
curl -X POST http://localhost:5000/api/v1/convert/extract-pages \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "paginas": [1, 3, 5], "formato_salida": "separados"}'
```

| Parámetro | Tipo | Opciones | Descripción |
|-----------|------|----------|-------------|
| `paginas` | array | lista de ints | Números de página a extraer (base 1) |
| `formato_salida` | string | `unico`, `separados` | PDF único o un PDF por página |

**Resultado:** PDF directo (`unico`) o ZIP (`separados`).

---

### POST /convert/compress — Comprimir PDF

```bash
# Análisis previo (Síncrono)
curl -X POST http://localhost:5000/api/v1/convert/compress/analyze \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID"}'

# Comprimir con preset
curl -X POST http://localhost:5000/api/v1/convert/compress \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "opciones": {"preset": "estandar"}}'

# Preset máximo con Ghostscript (PDFs con fuentes emoji COLR)
curl -X POST http://localhost:5000/api/v1/convert/compress \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "opciones": {"preset": "maximo", "usar_ghostscript": true}}'

# Personalizado (todos los parámetros)
curl -X POST http://localhost:5000/api/v1/convert/compress \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "opciones": {
      "preset": "personalizado",
      "reimagenes": true, "dpi": 96, "calidad_jpeg": 60,
      "grises": false, "dedup_imagenes": true,
      "subset_fuentes": true, "dedup_fuentes": true,
      "eliminar_xmp": true, "eliminar_thumbnails": true,
      "garbage": true, "comprimir_streams": true, "dedup_objetos": true,
      "eliminar_anotaciones": false, "eliminar_js": true,
      "eliminar_adjuntos": false, "eliminar_marcadores": false,
      "eliminar_ocg": false, "linearizar": false,
      "usar_ghostscript": false, "bajar_version": false
    }
  }'
curl http://localhost:5000/api/v1/download/JOB_ID --output comprimido.pdf
```

Presets: `ligero` | `estandar` | `agresivo` | `maximo` | `personalizado`

| Parámetro | Tipo | Default (estándar) | Descripción |
|-----------|------|--------------------|-------------|
| `preset` | string | `'estandar'` | Preset a aplicar |
| `reimagenes` | bool | `true` | Recomprimir imágenes embebidas |
| `dpi` | int | `150` | DPI máximo para imágenes |
| `calidad_jpeg` | int | `85` | Calidad JPEG resultante (60–95) |
| `grises` | bool | `false` | Convertir imágenes a escala de grises |
| `dedup_imagenes` | bool | `true` | Deduplicar imágenes idénticas |
| `subset_fuentes` | bool | `false` | Subconjunto de fuentes (solo glifos usados) |
| `dedup_fuentes` | bool | `true` | Deduplicar fuentes |
| `eliminar_xmp` | bool | `true` | Eliminar stream de metadatos XMP |
| `eliminar_thumbnails` | bool | `true` | Eliminar thumbnails embebidos |
| `garbage` | bool | `true` | Eliminar objetos huérfanos |
| `comprimir_streams` | bool | `true` | Comprimir streams con Deflate |
| `dedup_objetos` | bool | `true` | Deduplicar objetos |
| `eliminar_anotaciones` | bool | `false` | Eliminar anotaciones |
| `eliminar_js` | bool | `false` | Eliminar JavaScript embebido |
| `eliminar_marcadores` | bool | `false` | Eliminar bookmarks |
| `linearizar` | bool | `false` | Fast Web View (linearización) |
| `bajar_version` | bool | `false` | Reescribir en PDF 1.4 vía Ghostscript |
| `usar_ghostscript` | bool | `false` | Rasterizar fuentes COLR/emoji con GS |

**Resultado:** PDF directo.

> `usar_ghostscript` y `bajar_version` requieren Ghostscript en PATH. El contenedor Docker ya lo incluye. Si no está disponible, el paso se omite silenciosamente.

---

## 4. Extracción

### POST /convert/extract-images — Extraer imágenes del PDF

```bash
curl -X POST http://localhost:5000/api/v1/convert/extract-images \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "opciones": {
      "formato_salida": "original",
      "imagenes_seleccionadas": null,
      "tamano_minimo_px": 100
    }
  }'
curl http://localhost:5000/api/v1/download/JOB_ID --output imagenes.zip
```

| Parámetro | Tipo | Opciones | Default |
|-----------|------|----------|---------|
| `formato_salida` | string | `original`, `png`, `jpg` | `original` |
| `imagenes_seleccionadas` | array\|null | lista de IDs de imagen o `null` para todas | `null` |
| `tamano_minimo_px` | int | filtra imágenes más pequeñas | `100` |

**Resultado:** ZIP con imágenes (`documento - imagen 01.png`, etc.).

---

## 5. Creación desde otros formatos

### POST /convert/from-html — URL a PDF (Síncrono)

```bash
curl -X POST http://localhost:5000/api/v1/convert/from-html \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://ejemplo.com/pagina",
    "opciones": {
      "tamano_pagina": "A4",
      "orientacion": "vertical",
      "margenes": "normales",
      "incluir_fondo": true,
      "solo_contenido": false
    }
  }'
curl http://localhost:5000/api/v1/download/JOB_ID --output pagina.pdf
```

| Parámetro | Tipo | Opciones | Default |
|-----------|------|----------|---------|
| `url` | string | URL completa con `https://` | requerido |
| `tamano_pagina` | string | `A4`, `Letter`, `Legal`, `A3` | `A4` |
| `orientacion` | string | `vertical`, `horizontal` | `vertical` |
| `margenes` | string | `sin_margenes`, `normales`, `amplios` | `normales` |
| `incluir_fondo` | bool | Incluye colores e imágenes de fondo | `true` |
| `solo_contenido` | bool | Intenta quitar navegación y publicidad | `false` |

**Resultado:** PDF directo. Timeout de 30 segundos. Páginas con login o JS pesado pueden no renderizar.

---

### POST /convert/img-to-1pdf — Imágenes a PDF (Síncrono)

```bash
# Subir cada imagen primero
curl -X POST http://localhost:5000/api/v1/upload -F "archivo=@foto1.jpg"
# guardar el file_id de cada upload

curl -X POST http://localhost:5000/api/v1/convert/img-to-1pdf \
  -H "Content-Type: application/json" \
  -d '{
    "archivos": [
      {"file_id": "FILE_ID_1", "orden": 1},
      {"file_id": "FILE_ID_2", "orden": 2}
    ],
    "opciones": {"tamano_pagina": "A4", "margen": 0}
  }'
curl http://localhost:5000/api/v1/download/JOB_ID --output resultado.pdf
```

| Parámetro | Tipo | Opciones | Default |
|-----------|------|----------|---------|
| `tamano_pagina` | string | `natural`, `A4`, `A4H`, `A3`, `A3H`, `letter`, `letterH` | `natural` |
| `margen` | int | `0`, `15`, `30` (puntos) | `0` |

Formatos de imagen aceptados: JPG, JPEG, PNG, GIF, BMP, TIFF, WEBP.

**Resultado:** PDF directo.

---

### POST /convert/webp-to-png — WEBP a PNG (Síncrono)

```bash
curl -X POST http://localhost:5000/api/v1/convert/webp-to-png \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID"}'
curl http://localhost:5000/api/v1/download/JOB_ID --output imagen.png
```

Sin parámetros adicionales. Si el WEBP es animado, extrae el primer frame.

**Resultado:** PNG directo.

---

### POST /convert/svg-to-png — SVG a PNG (Síncrono)

```bash
curl -X POST http://localhost:5000/api/v1/convert/svg-to-png \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "opciones": {"escala": 2}}'
curl http://localhost:5000/api/v1/download/JOB_ID --output imagen.png
```

| Parámetro | Tipo | Opciones | Default |
|-----------|------|----------|---------|
| `escala` | int | `1`, `2`, `3`, `4` | `2` |

**Resultado:** PNG directo.

---

### POST /convert/eps-to-png — EPS a PNG (Síncrono)

Requiere Ghostscript instalado (`gs` en PATH). El contenedor Docker ya lo incluye.

```bash
curl -X POST http://localhost:5000/api/v1/convert/eps-to-png \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "opciones": {"escala": 2}}'
curl http://localhost:5000/api/v1/download/JOB_ID --output imagen.png
```

| Parámetro | Tipo | Opciones | Default |
|-----------|------|----------|---------|
| `escala` | int | `1`, `2`, `3`, `4` | `2` |

**Resultado:** PNG directo.

---

### POST /convert/xlsx-to-csv — Excel a CSV (Síncrono)

```bash
curl -X POST http://localhost:5000/api/v1/upload -F "archivo=@datos.xlsx"

curl -X POST http://localhost:5000/api/v1/convert/xlsx-to-csv \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "opciones": {"separador": ";", "saltos_linea": "CRLF"}}'
curl http://localhost:5000/api/v1/download/JOB_ID --output datos.csv
```

| Parámetro | Tipo | Opciones | Default |
|-----------|------|----------|---------|
| `separador` | string | `";"`, `","` | `";"` |
| `saltos_linea` | string | `"CRLF"`, `"LF"` | `"CRLF"` |

**Resultado:** CSV directo (1 hoja) o ZIP (N hojas).

---

### POST /convert/img-to-txt — Imagen a texto con OCR

Requiere Tesseract instalado. El contenedor Docker ya lo incluye.

```bash
curl -X POST http://localhost:5000/api/v1/convert/img-to-txt \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "opciones": {"idioma": "spa"}}'
curl http://localhost:5000/api/v1/download/JOB_ID --output texto.txt
```

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `idioma` | string | `"spa"` | Código Tesseract: `"spa"`, `"eng"`, `"por"`, etc. |

**Resultado:** TXT directo.

---

## 6. Conversión a Markdown

### POST /convert/excel-to-md — Excel a Markdown

```bash
curl -X POST http://localhost:5000/api/v1/convert/excel-to-md \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "opciones": {}}'
curl http://localhost:5000/api/v1/download/JOB_ID --output datos.md
```

**Resultado:** MD directo.

---

### POST /convert/epub-to-md — EPUB a Markdown

```bash
curl -X POST http://localhost:5000/api/v1/convert/epub-to-md \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID", "opciones": {}}'
curl http://localhost:5000/api/v1/download/JOB_ID --output libro.md
```

**Resultado:** MD directo.

---

### POST /convert/youtube-to-md — Subtítulos de YouTube a Markdown

```bash
curl -X POST http://localhost:5000/api/v1/convert/youtube-to-md \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "opciones": {"idioma": "es"}
  }'
curl http://localhost:5000/api/v1/download/JOB_ID --output subtitulos.md
```

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `url` | string | — | URL del video de YouTube |
| `idioma` | string | `"es"` | Idioma preferido de los subtítulos |

Requiere que el video tenga subtítulos disponibles. Si la IP está bloqueada por YouTube, configurar `YOUTUBE_RELAY_URL` o `YOUTUBE_PROXY_URL` en el entorno.

**Resultado:** MD directo.

---

### POST /convert/wikipedia-to-md — Wikipedia a Markdown

```bash
curl -X POST http://localhost:5000/api/v1/convert/wikipedia-to-md \
  -H "Content-Type: application/json" \
  -d '{"entrada": "Python (lenguaje de programación)", "lang": "es"}'
# Con URL completa:
curl -X POST http://localhost:5000/api/v1/convert/wikipedia-to-md \
  -H "Content-Type: application/json" \
  -d '{"entrada": "https://en.wikipedia.org/wiki/Python_(programming_language)", "lang": "en"}'
curl http://localhost:5000/api/v1/download/JOB_ID --output articulo.md
```

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `entrada` | string | — | URL de Wikipedia o nombre de artículo |
| `lang` | string | `"es"` | Código de idioma: `es`, `en`, `fr`, `de`, `pt`, `it`, `nl`, `pl`, `ru`, `ja`, `zh`, `ar` |

Si `entrada` es una URL de Wikipedia, `lang` se extrae de la URL automáticamente.

**Resultado:** MD directo (sin ZIP).

---

### POST /token-count — Contador de Tokens *(Síncrono)*

```bash
curl -X POST http://localhost:5000/api/v1/token-count \
  -H "Content-Type: application/json" \
  -d '{"texto": "Hola mundo. Este es un ejemplo de texto para contar tokens."}'
```

**Respuesta:**
```json
{
  "success": true,
  "data": {
    "tokens": 14,
    "palabras": 11,
    "caracteres": 61,
    "bytes": 62,
    "encoding": "cl100k_base"
  },
  "message": "Conteo completado"
}
```

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `texto` | string | Texto a analizar (requerido) |

**Notas:**
- Síncrono — no genera `job_id`, responde inmediatamente
- Encoding `cl100k_base`: GPT-4, GPT-3.5-turbo, Claude (aproximado)
- Error 503 si tiktoken no puede cargar el vocabulario en primer uso

---

### POST /convert/scrape-url — Web Scraper

```bash
# Asíncrono: genera archivo descargable
curl -X POST http://localhost:5000/api/v1/convert/scrape-url \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://ejemplo.com/articulo",
    "opciones": {
      "formato_salida": "markdown",
      "incluir_metadatos": true,
      "incluir_contenido": true,
      "incluir_footer": false,
      "incluir_links": false
    }
  }'
curl http://localhost:5000/api/v1/download/JOB_ID --output contenido.zip

# Preview síncrono: solo en respuesta JSON, sin generar archivo
curl -X POST http://localhost:5000/api/v1/convert/scrape-url/preview \
  -H "Content-Type: application/json" \
  -d '{"url": "https://ejemplo.com/articulo", "opciones": {"formato_salida": "markdown"}}'
```

| Parámetro | Tipo | Opciones | Default |
|-----------|------|----------|---------|
| `url` | string | URL completa con `https://` | requerido |
| `formato_salida` | string | `"markdown"`, `"texto"` | `"markdown"` |
| `incluir_metadatos` | bool | título, URL, fecha, autor | `true` |
| `incluir_contenido` | bool | cuerpo principal de la página | `true` |
| `incluir_footer` | bool | emails, teléfonos y texto del footer | `true` |
| `incluir_links` | bool | lista de todos los enlaces | `true` |

**Resultado (asíncrono):** ZIP con archivo MD o TXT.

---

## 7. Análisis forense

### POST /metadata/extract — Extraer metadatos PDF (Síncrono)

```bash
curl -X POST http://localhost:5000/api/v1/metadata/extract \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID"}'
```

**Respuesta:**
```json
{
  "success": true,
  "data": {
    "titulo": "Mi Documento",
    "autor": "Juan Pérez",
    "creador": "Adobe Acrobat 2023",
    "productor": "GPL Ghostscript 10.0",
    "fecha_creacion": "2026-01-10T09:30:00",
    "fecha_modificacion": "2026-01-15T11:00:00",
    "num_paginas": 45,
    "version_pdf": "1.7",
    "encriptado": false,
    "permisos": {
      "imprimir": true,
      "copiar": true,
      "modificar": false,
      "anotar": true
    },
    "fuentes": [
      {"nombre": "Arial", "tipo": "TrueType", "embebida": true, "subconjunto": false}
    ],
    "ids_documentos": ["3A5F8A2B...", "7C1D4E9F..."],
    "xmp": "<x:xmpmeta>...</x:xmpmeta>",
    "contenido_texto": "Primeras líneas del contenido textual del documento..."
  }
}
```

---

### PUT /metadata/edit — Editar metadatos PDF

```bash
curl -X PUT http://localhost:5000/api/v1/metadata/edit \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "metadatos": {
      "titulo": "Nuevo Título",
      "autor": "Juan Pérez",
      "asunto": "Informe Q1 2026",
      "palabras_clave": "informe, finanzas, Q1"
    }
  }'
curl http://localhost:5000/api/v1/download/JOB_ID --output modificado.pdf
```

**Resultado:** PDF directo con los metadatos actualizados.

---

### POST /img-metadata/extract — Extraer metadatos de imagen (Síncrono)

```bash
curl -X POST http://localhost:5000/api/v1/img-metadata/extract \
  -H "Content-Type: application/json" \
  -d '{"file_id": "FILE_ID"}'
```

**Respuesta:**
```json
{
  "success": true,
  "data": {
    "formato": "JPEG",
    "modo_color": "RGB",
    "dimensiones": {"ancho": 4032, "alto": 3024},
    "dpi": [72.0, 72.0],
    "fecha_captura": "2025-12-01T15:30:00",
    "camara": {"marca": "Apple", "modelo": "iPhone 15 Pro"},
    "gps": {
      "latitud": -34.6037,
      "longitud": -58.3816,
      "altitud_m": 25.4
    },
    "hashes": {
      "md5": "d41d8cd98f00b204e9800998ecf8427e",
      "sha256": "e3b0c44298fc1c149afb..."
    },
    "colores_dominantes": [
      {"hex": "#3A5F8A", "porcentaje": 28.4},
      {"hex": "#F2E8D0", "porcentaje": 21.1}
    ]
  }
}
```

---

## 8. Migración SQL

### POST /convert/ndm-to-tables-seq — NDM a orden de migración SQL

Genera el orden secuencial de migración de tablas SQL respetando dependencias de FK.
Acepta `.ndm2` (Navicat Data Modeler v2) o `.json` con la misma estructura.

```bash
curl -X POST http://localhost:5000/api/v1/upload -F "archivo=@modelo.ndm2"

curl -X POST http://localhost:5000/api/v1/convert/ndm-to-tables-seq \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "opciones": {"formato_salida": "original", "sin_comprimir": true}
  }'
curl http://localhost:5000/api/v1/download/JOB_ID --output orden_migracion.txt
```

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `formato_salida` | string | `"original"` | Único valor soportado actualmente |
| `sin_comprimir` | bool | `true` | `true`: retorna TXT directo sin ZIP |

El TXT resultante contiene la lista numerada de tablas en orden de migración, comenzando por las que no tienen FK, con notas sobre dependencias circulares.

---

## 9. Notepad compartido

Almacenamiento de texto colaborativo en tiempo real. El `slug` identifica el documento (3–50 chars: letras minúsculas, números, guión, guión bajo).

### GET /notepad/{slug} — Obtener o crear notepad

Crea el notepad automáticamente si no existe. Registra la IP como visitante activo.

```bash
curl http://localhost:5000/api/v1/notepad/mi-proyecto-2026
```

**Respuesta:**
```json
{
  "success": true,
  "data": {
    "slug": "mi-proyecto-2026",
    "contenido": "# Notas del proyecto\n...",
    "version": 42,
    "crc32": 3141592653,
    "fecha_modificacion": "2026-07-15T10:30:00",
    "visitantes": [
      {"ip": "192.168.1.10", "es_yo": true},
      {"ip": "192.168.1.25", "es_yo": false}
    ]
  }
}
```

---

### PUT /notepad/{slug} — Guardar contenido completo

Reemplaza el contenido íntegro (last-write-wins). Para edición colaborativa usar `/lines`.

```bash
curl -X PUT http://localhost:5000/api/v1/notepad/mi-proyecto-2026 \
  -H "Content-Type: application/json" \
  -d '{"contenido": "# Contenido nuevo\nLínea 2\nLínea 3"}'
```

**Respuesta:** incluye `version`, `crc32`, `fecha_modificacion`, `visitantes`.

---

### PUT /notepad/{slug}/lines — Aplicar deltas de líneas

Edición atómica a nivel de línea. Más eficiente que reemplazar el contenido completo; permite edición colaborativa con protección de 3 segundos por línea.

```bash
# Editar línea 3 (índice 2), insertar en posición 5, eliminar línea 8 (índice 7)
curl -X PUT http://localhost:5000/api/v1/notepad/mi-proyecto-2026/lines \
  -H "Content-Type: application/json" \
  -d '{
    "deltas": [
      {"n": 2, "texto": "línea 3 modificada"},
      {"n": 5, "op": "insert", "texto": "nueva línea insertada"},
      {"n": 7, "op": "delete"}
    ]
  }'
```

| Campo delta | Tipo | Descripción |
|-------------|------|-------------|
| `n` | int | Índice de línea (base 0) |
| `texto` | string | Contenido de la línea (para edits e inserts) |
| `op` | string | `"insert"` o `"delete"`. Ausente = editar línea existente |

Orden de aplicación en el servidor: edits primero, luego inserts (ascendente), luego deletes (descendente).

**Respuesta:**
```json
{
  "success": true,
  "data": {
    "version": 43,
    "crc32": 987654321,
    "visitantes": [...]
  }
}
```

---

### DELETE /notepad/{slug} — Eliminar notepad

```bash
curl -X DELETE http://localhost:5000/api/v1/notepad/mi-proyecto-2026
```

---

## Apéndice: Flujo completo en un script bash

```bash
#!/bin/bash
# Subir un PDF y convertirlo a TXT

BASE_URL="http://localhost:5000/api/v1"
ARCHIVO="documento.pdf"

echo "Subiendo $ARCHIVO..."
FILE_ID=$(curl -s -X POST "$BASE_URL/upload" -F "archivo=@$ARCHIVO" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "  file_id: $FILE_ID"

echo "Iniciando conversión..."
JOB_ID=$(curl -s -X POST "$BASE_URL/convert/to-txt" \
  -H "Content-Type: application/json" \
  -d "{\"file_id\": \"$FILE_ID\", \"opciones\": {\"remover_encabezados\": true, \"remover_pies_pagina\": true}}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['job']['id'])")
echo "  job_id: $JOB_ID"

echo "Esperando resultado..."
while true; do
  ESTADO=$(curl -s "$BASE_URL/jobs/$JOB_ID" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['estado'])")
  echo "  estado: $ESTADO"
  [ "$ESTADO" = "completado" ] || [ "$ESTADO" = "error" ] && break
  sleep 2
done

if [ "$ESTADO" = "completado" ]; then
  curl -s "$BASE_URL/download/$JOB_ID" --output "${ARCHIVO%.pdf}.txt"
  echo "Listo: ${ARCHIVO%.pdf}.txt"
else
  echo "Error en la conversión"
fi
```
