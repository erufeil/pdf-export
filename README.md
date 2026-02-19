# PDFexport

Servicio de conversion y manipulacion de archivos PDF. Aplicacion web autocontenida con backend Python/Flask y frontend HTML/CSS/JS vanilla.

## Caracteristicas

- **PDF a TXT**: Extrae texto plano, removiendo encabezados y pies de pagina
- **PDF a DOCX**: Convierte a documento Word preservando formato
- **PDF a PNG/JPG**: Convierte paginas a imagenes con DPI configurable
- **Comprimir PDF**: Reduce el tamanio con niveles de compresion seleccionables
- **Extraer imagenes**: Extrae imagenes incrustadas del PDF
- **Cortar PDF**: Divide el PDF en partes con hasta 20 cortes
- **Rotar PDF**: Rota paginas individuales o todas
- **HTML a PDF**: Convierte paginas web a PDF via URL
- **Unir PDFs**: Combina multiples PDFs en uno
- **Extraer paginas**: Extrae paginas especificas a PDF unico o separados
- **Reordenar paginas**: Cambia el orden de las paginas via drag & drop
- **Migrar SQL (NDM)**: Genera orden secuencial de migracion de tablas SQL a partir de archivos Navicat Data Modeler (.ndm2)

## Requisitos

- Docker y Docker Compose
- O Python 3.10+ con las dependencias del sistema

---

## Instalacion con Docker (Recomendado)

### 1. Clonar el repositorio

```bash
git clone https://github.com/ERF/PDFexport.git
cd PDFexport
```

### 2. Configurar variables de entorno

Las variables se pasan directamente en `docker-compose.yml`:

```yaml
environment:
  - PORT=5000
  - APP_VERSION=1.1.12     # version que aparece en el footer
  - FILE_RETENTION_HOURS=4  # horas de retencion de archivos
  - TIMEOUT=30000           # timeout en ms para peticiones del frontend
  - RETRY_ATTEMPTS=3
```

### 3. Construir y ejecutar

```bash
# Construir la imagen
docker build -t pdfexport .

# Ejecutar con docker-compose
docker-compose up -d
```

### 4. Acceder a la aplicacion

Abrir en el navegador: `http://localhost:5000`

### Actualizar a una nueva version

```bash
git pull
docker-compose down
docker build -t pdfexport .
docker-compose up -d
```

---

## Instalacion Manual (Desarrollo)

### 1. Instalar dependencias del sistema (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils libpango-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 fonts-liberation fonts-dejavu
```

### 2. Crear entorno virtual e instalar Python

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. En Windows: instalar poppler

Descargar zip de: https://github.com/oschwartz10612/poppler-windows/releases
Copiar la carpeta `bin` en `venv/poppler/`, quedando asi:

```
venv/
└── poppler/
    └── Library/
        └── bin/
            ├── pdftoppm.exe
            ├── pdfinfo.exe
            └── ...
```

### 4. En Windows: instalar GTK3 (requerido por WeasyPrint)

Instalar MSYS2 desde: https://www.msys2.org/
Luego ejecutar en la consola MSYS2:

```shell
pacman -S mingw-w64-ucrt-x86_64-gtk3
```

Agregar al PATH de Windows:
```cmd
set PATH=C:\msys64\ucrt64\bin;%PATH%
```

### 5. Ejecutar la aplicacion

```bash
python app.py
```

---

## Configuracion

### Variables de entorno

| Variable | Descripcion | Default |
|----------|-------------|---------|
| `HOST` | IP donde escucha el servidor | `0.0.0.0` |
| `PORT` | Puerto del servidor | `5000` |
| `DEBUG` | Modo debug de Flask | `False` |
| `APP_VERSION` | Version de la app (aparece en footer) | valor de `config.py` |
| `FILE_RETENTION_HOURS` | Horas de retencion de archivos | `4` |
| `TIMEOUT` | Timeout de peticiones frontend (ms) | `30000` |
| `RETRY_ATTEMPTS` | Reintentos en caso de error | `3` |
| `MAX_FILE_SIZE` | Tamanio maximo de upload (bytes) | `1073741824` (1 GB) |
| `POPPLER_PATH` | Ruta a poppler en Windows | `None` |

### Versionado

La version visible en el footer se define en `config.py`:

```python
VERSION = os.getenv('APP_VERSION', '1.1.12')
```

Para cambiarla sin recompilar la imagen Docker, pasar la variable de entorno `APP_VERSION` en `docker-compose.yml`. Para cambiarla en el codigo, editar `config.py` y reconstruir la imagen.

---

## Estructura del Proyecto

```
PDFexport/
├── app.py                    # Aplicacion Flask principal
├── config.py                 # Configuracion Python (incluye VERSION)
├── config.js                 # Config frontend (generado por entrypoint)
├── entrypoint.py             # Genera config.js al iniciar el contenedor
├── index.html                # Landing page
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
│
├── api/
│   ├── routes_files.py       # Endpoints de archivos
│   ├── routes_convert.py     # Endpoints de conversion
│   └── routes_jobs.py        # Endpoints de trabajos y descarga
│
├── services/                 # Logica de cada conversion
│   ├── pdf_to_txt.py
│   ├── pdf_to_docx.py
│   ├── pdf_to_images.py      # PNG y JPG
│   ├── pdf_compress.py
│   ├── pdf_extract_images.py
│   ├── pdf_split.py
│   ├── pdf_rotate.py
│   ├── html_to_pdf.py
│   ├── pdf_merge.py
│   ├── pdf_extract_pages.py
│   ├── pdf_reorder.py
│   └── ndm_to_tables_seq.py  # Orden de migracion SQL
│
├── utils/
│   ├── file_manager.py
│   ├── job_manager.py
│   └── thumbnail.py
│
├── static/                   # Frontend de cada servicio
├── uploads/                  # Archivos subidos (limpieza cada 4h)
├── outputs/                  # Resultados de conversion (limpieza cada 4h)
└── data/
    └── pdfexport.db          # Base de datos SQLite
```

---

## Limites

- Tamanio maximo de archivo: **1 GB**
- Retencion de archivos: **4 horas** (configurable con `FILE_RETENTION_HOURS`)
- Formatos de entrada: `.pdf`, `.ndm2`, `.json`
- Maximo de cortes en "Cortar PDF": **20**

---

## Uso via API con curl

El flujo general es siempre el mismo:

1. **Subir el archivo** → obtenes un `file_id`
2. **Iniciar la conversion** → obtenes un `job_id`
3. **Consultar el estado** del trabajo hasta que este `completado`
4. **Descargar el resultado** usando el `job_id`

Reemplaza `http://localhost:5000` con la URL de tu servidor.

---

### 1. Subir un archivo

```bash
# Linux/Mac
curl -X POST http://localhost:5000/api/v1/upload \
  -F "archivo=@/ruta/al/archivo.pdf"

# Windows CMD (desde la carpeta donde esta el archivo)
curl -X POST http://localhost:5000/api/v1/upload -F "archivo=@nombre_archivo.pdf"

# Windows CMD (con ruta completa)
curl -X POST http://localhost:5000/api/v1/upload -F "archivo=@\"C:\Users\usuario\Downloads\archivo.pdf\""
```

Respuesta:
```json
{
  "success": true,
  "data": {
    "id": "abc123",
    "nombre_original": "archivo.pdf",
    "tamano_bytes": 2048000,
    "num_paginas": 45,
    "fecha_subida": "2026-02-19T10:30:00"
  }
}
```

> Si el mismo archivo (nombre + tamanio + fecha de modificacion) ya esta en el servidor, retorna el existente sin volver a subirlo.

---

### 2. Listar archivos disponibles

```bash
curl http://localhost:5000/api/v1/files
```

---

### 3. Obtener miniatura de una pagina

```bash
# Miniatura de la pagina 1 del archivo con id "abc123"
curl http://localhost:5000/api/v1/files/abc123/thumbnail/1 \
  --output miniatura.png
```

---

### 4. Eliminar un archivo

```bash
curl -X DELETE http://localhost:5000/api/v1/files/abc123
```

```bash
# Eliminar todos los archivos
curl -X DELETE http://localhost:5000/api/v1/files
```

---

### 5. Consultar estado del servicio

```bash
curl http://localhost:5000/api/v1/status
```

---

### Conversiones

Todos los endpoints de conversion devuelven un `job_id`. Luego se consulta el estado y se descarga el resultado.

#### Consultar estado de un trabajo

```bash
curl http://localhost:5000/api/v1/jobs/JOB_ID
```

Respuesta cuando esta listo:
```json
{
  "success": true,
  "data": {
    "id": "JOB_ID",
    "estado": "completado",
    "progreso": 100,
    "nombre_archivo": "resultado.zip"
  }
}
```

#### Descargar el resultado

```bash
curl http://localhost:5000/api/v1/download/JOB_ID \
  --output resultado.zip
```

---

### 6. PDF a TXT

```bash
# Paso 1: subir
FILE_ID=$(curl -s -X POST http://localhost:5000/api/v1/upload \
  -F "archivo=@documento.pdf" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

# Paso 2: convertir
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

# Paso 3: descargar cuando este listo
curl http://localhost:5000/api/v1/download/$JOB_ID --output documento.zip
```

Parametros disponibles:

| Parametro | Tipo | Descripcion | Default |
|-----------|------|-------------|---------|
| `remover_numeros_pagina` | bool | Elimina numeros de pagina | `true` |
| `remover_encabezados` | bool | Elimina texto repetido en parte superior | `true` |
| `remover_pies_pagina` | bool | Elimina texto repetido en parte inferior | `true` |
| `preservar_parrafos` | bool | Mantiene saltos de parrafo | `true` |
| `detectar_columnas` | bool | Maneja PDFs con multiples columnas | `false` |

---

### 7. PDF a DOCX

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

Parametros disponibles:

| Parametro | Tipo | Opciones | Default |
|-----------|------|----------|---------|
| `preservar_imagenes` | bool | - | `true` |
| `preservar_tablas` | bool | - | `true` |
| `preservar_estilos` | bool | negrita, cursiva, tamanios | `true` |
| `calidad_imagenes` | string | `baja`, `media`, `alta`, `original` | `media` |

---

### 8. PDF a PNG

```bash
# Todas las paginas a 150 DPI
curl -X POST http://localhost:5000/api/v1/convert/to-png \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "opciones": {
      "dpi": 150,
      "paginas": "all",
      "paginas_especificas": null
    }
  }'

# Solo un rango de paginas
curl -X POST http://localhost:5000/api/v1/convert/to-png \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "opciones": {
      "dpi": 300,
      "paginas": "rango",
      "pagina_inicio": 3,
      "pagina_fin": 10
    }
  }'

# Paginas especificas
curl -X POST http://localhost:5000/api/v1/convert/to-png \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "opciones": {
      "dpi": 150,
      "paginas": "especificas",
      "paginas_especificas": "1,3,5-8"
    }
  }'
```

Parametros disponibles:

| Parametro | Tipo | Opciones | Default |
|-----------|------|----------|---------|
| `dpi` | int | `72`, `150`, `300`, `600` | `150` |
| `paginas` | string | `all`, `rango`, `especificas` | `all` |
| `pagina_inicio` | int | numero de pagina | - |
| `pagina_fin` | int | numero de pagina | - |
| `paginas_especificas` | string | ej: `"1,3,5-10"` | `null` |

Resultado: archivo ZIP con `documento.pdf - pagina 001.png`, `documento.pdf - pagina 002.png`, etc.

---

### 9. PDF a JPG

```bash
curl -X POST http://localhost:5000/api/v1/convert/to-jpg \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "opciones": {
      "dpi": 150,
      "calidad": 85,
      "paginas": "all",
      "paginas_especificas": null
    }
  }'
```

Parametros disponibles:

| Parametro | Tipo | Opciones | Default |
|-----------|------|----------|---------|
| `dpi` | int | `72`, `150`, `300`, `600` | `150` |
| `calidad` | int | `60` a `95` | `85` |
| `paginas` | string | `all`, `rango`, `especificas` | `all` |
| `pagina_inicio` | int | numero de pagina | - |
| `pagina_fin` | int | numero de pagina | - |
| `paginas_especificas` | string | ej: `"1,3,5-10"` | `null` |

---

### 10. Comprimir PDF

```bash
# Nivel predefinido
curl -X POST http://localhost:5000/api/v1/convert/compress \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "opciones": {
      "nivel": "media",
      "eliminar_metadatos": true,
      "eliminar_anotaciones": false,
      "eliminar_bookmarks": false,
      "escala_grises": false
    }
  }'

# Compresion personalizada
curl -X POST http://localhost:5000/api/v1/convert/compress \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "opciones": {
      "nivel": "personalizada",
      "dpi_maximo": 100,
      "calidad_jpg": 70,
      "eliminar_metadatos": true,
      "eliminar_anotaciones": true,
      "eliminar_bookmarks": false,
      "escala_grises": true
    }
  }'
```

Parametros disponibles:

| Parametro | Tipo | Opciones / Descripcion | Default |
|-----------|------|------------------------|---------|
| `nivel` | string | `baja` (150dpi/90%), `media` (120dpi/75%), `alta` (96dpi/60%), `personalizada` | `media` |
| `dpi_maximo` | int | Solo para nivel `personalizada` | `120` |
| `calidad_jpg` | int | Solo para nivel `personalizada`, rango 1-100 | `75` |
| `eliminar_metadatos` | bool | Elimina autor, titulo, etc. | `true` |
| `eliminar_anotaciones` | bool | Elimina comentarios y marcas | `false` |
| `eliminar_bookmarks` | bool | Elimina marcadores | `false` |
| `escala_grises` | bool | Convierte todo a blanco y negro | `false` |

---

### 11. Extraer imagenes del PDF

```bash
# Extraer todas las imagenes en formato original
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

# Extraer solo imagenes especificas en PNG
curl -X POST http://localhost:5000/api/v1/convert/extract-images \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "opciones": {
      "formato_salida": "png",
      "imagenes_seleccionadas": ["img_1", "img_3", "img_5"],
      "tamano_minimo_px": 200
    }
  }'
```

Parametros disponibles:

| Parametro | Tipo | Opciones | Default |
|-----------|------|----------|---------|
| `formato_salida` | string | `original`, `png`, `jpg` | `original` |
| `imagenes_seleccionadas` | array/null | lista de IDs de imagen o `null` para todas | `null` |
| `tamano_minimo_px` | int | filtra imagenes mas pequenias (ignora iconos) | `100` |

Resultado: ZIP con `documento.pdf - imagen 01.png`, `documento.pdf - imagen 02.jpg`, etc.

---

### 12. Cortar PDF

```bash
# Cortar en partes definidas manualmente
curl -X POST http://localhost:5000/api/v1/convert/split \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "opciones": {
      "cortes": [
        {"inicio": 1, "fin": 50},
        {"inicio": 51, "fin": 100},
        {"inicio": 101, "fin": 150}
      ]
    }
  }'

# Cortar en N partes iguales
curl -X POST http://localhost:5000/api/v1/convert/split \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "opciones": {
      "num_partes": 5
    }
  }'
```

Parametros disponibles:

Ambos parametros van dentro de `opciones`:

| Parametro | Tipo | Descripcion |
|-----------|------|-------------|
| `cortes` | array | Lista de objetos `{"inicio": N, "fin": M}`. Maximo 20 cortes. |
| `num_partes` | int | Alternativa a `cortes`: divide el PDF en N partes iguales |

Resultado: ZIP con `documento.pdf - pag. 001 - 050.pdf`, `documento.pdf - pag. 051 - 100.pdf`, etc.

---

### 13. Rotar PDF

```bash
# Rotar paginas especificas
curl -X POST http://localhost:5000/api/v1/convert/rotate \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "rotaciones": {
      "1": 90,
      "3": 180,
      "5": 270
    }
  }'

# Rotar todas las paginas 90 grados
curl -X POST http://localhost:5000/api/v1/convert/rotate \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "rotaciones": {},
    "rotar_todas": 90
  }'
```

Parametros disponibles:

| Parametro | Tipo | Descripcion |
|-----------|------|-------------|
| `rotaciones` | objeto | Clave: numero de pagina (string). Valor: grados (`90`, `180`, `270`) |
| `rotar_todas` | int | Rotacion para todas las paginas: `90`, `180` o `270` |

---

### 14. HTML a PDF

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
```

Parametros disponibles:

| Parametro | Tipo | Opciones | Default |
|-----------|------|----------|---------|
| `url` | string | URL completa incluyendo `https://` | requerido |
| `tamano_pagina` | string | `A4`, `Letter`, `Legal`, `A3` | `A4` |
| `orientacion` | string | `vertical`, `horizontal` | `vertical` |
| `margenes` | string | `sin_margenes`, `normales`, `amplios` | `normales` |
| `incluir_fondo` | bool | Incluye colores e imagenes de fondo | `true` |
| `solo_contenido` | bool | Intenta remover navegacion y publicidad | `false` |

> Timeout de 30 segundos. Paginas con login o JavaScript pesado pueden no renderizar correctamente.

---

### 15. Unir PDFs

```bash
# Primero subir cada archivo y obtener sus file_id
curl -X POST http://localhost:5000/api/v1/convert/merge \
  -H "Content-Type: application/json" \
  -d '{
    "archivos": [
      {"file_id": "FILE_ID_1", "orden": 1},
      {"file_id": "FILE_ID_2", "orden": 2},
      {"file_id": "FILE_ID_3", "orden": 3}
    ],
    "opciones": {
      "agregar_marcadores": true
    }
  }'
```

Parametros disponibles:

| Parametro | Tipo | Descripcion |
|-----------|------|-------------|
| `archivos` | array | Lista de `{"file_id": "...", "orden": N}`. El orden determina la secuencia en el PDF final. |
| `agregar_marcadores` | bool | Agrega marcadores (bookmarks) con el nombre de cada archivo original |

---

### 16. Extraer paginas especificas

```bash
# Exportar a un unico PDF
curl -X POST http://localhost:5000/api/v1/convert/extract-pages \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "paginas": [1, 3, 5, 6, 7, 8, 9, 10, 15],
    "formato_salida": "unico"
  }'

# Exportar cada pagina en un PDF separado
curl -X POST http://localhost:5000/api/v1/convert/extract-pages \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "paginas": [1, 3, 5, 6, 7, 8, 9, 10, 15],
    "formato_salida": "separados"
  }'
```

Parametros disponibles:

| Parametro | Tipo | Opciones | Descripcion |
|-----------|------|----------|-------------|
| `paginas` | array | lista de enteros | Numeros de pagina a extraer (base 1) |
| `formato_salida` | string | `unico`, `separados` | Un solo PDF o un PDF por pagina |

---

### 17. Reordenar paginas

```bash
# El array nuevo_orden indica la posicion final de cada pagina
# Ejemplo: [3, 1, 2] significa que la pagina 3 va primero, luego la 1, luego la 2
curl -X POST http://localhost:5000/api/v1/convert/reorder \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "nuevo_orden": [3, 1, 2, 5, 4, 6, 7, 8]
  }'
```

Parametros disponibles:

| Parametro | Tipo | Descripcion |
|-----------|------|-------------|
| `nuevo_orden` | array | Lista completa de numeros de pagina en el nuevo orden deseado |

---

### 18. Migrar SQL (NDM - Navicat Data Modeler)

Genera el orden secuencial correcto de migracion de tablas SQL respetando dependencias de FK.
Acepta archivos `.ndm2` (Navicat Data Modeler v2) o `.json` con la misma estructura.

```bash
# Paso 1: subir el archivo .ndm2
curl -X POST http://localhost:5000/api/v1/upload \
  -F "archivo=@modelo.ndm2"

# Paso 2: generar el orden de migracion
curl -X POST http://localhost:5000/api/v1/convert/ndm-to-tables-seq \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "FILE_ID",
    "opciones": {
      "formato_salida": "original",
      "sin_comprimir": true
    }
  }'

# Paso 3: descargar el TXT resultante
curl http://localhost:5000/api/v1/download/JOB_ID \
  --output Orden_secuencial_migracion_SQL.txt
```

Parametros disponibles:

| Parametro | Tipo | Descripcion |
|-----------|------|-------------|
| `formato_salida` | string | `original` (unico valor soportado actualmente) |
| `sin_comprimir` | bool | `true`: devuelve TXT directamente sin ZIP |

El archivo resultante contiene:
- Titulo con el nombre de la base de datos
- Lista numerada de tablas en orden de migracion (primero las que no tienen FK, luego las que dependen de otras)
- Notas al pie con advertencias de dependencias circulares o FK a otras bases de datos

---

### Flujo completo de ejemplo en un script bash

```bash
#!/bin/bash
# Ejemplo: subir un PDF y convertirlo a TXT

BASE_URL="http://localhost:5000/api/v1"
ARCHIVO="mi_documento.pdf"

echo "Subiendo $ARCHIVO..."
RESPUESTA_UPLOAD=$(curl -s -X POST "$BASE_URL/upload" -F "archivo=@$ARCHIVO")
FILE_ID=$(echo $RESPUESTA_UPLOAD | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "file_id: $FILE_ID"

echo "Iniciando conversion a TXT..."
RESPUESTA_JOB=$(curl -s -X POST "$BASE_URL/convert/to-txt" \
  -H "Content-Type: application/json" \
  -d "{\"file_id\": \"$FILE_ID\", \"opciones\": {\"remover_numeros_pagina\": true, \"remover_encabezados\": true, \"remover_pies_pagina\": true}}")
JOB_ID=$(echo $RESPUESTA_JOB | python3 -c "import sys,json; print(json.load(sys.stdin)['job']['id'])")
echo "job_id: $JOB_ID"

echo "Esperando resultado..."
while true; do
  ESTADO=$(curl -s "$BASE_URL/jobs/$JOB_ID" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['estado'])")
  echo "  Estado: $ESTADO"
  if [ "$ESTADO" = "completado" ] || [ "$ESTADO" = "error" ]; then
    break
  fi
  sleep 2
done

if [ "$ESTADO" = "completado" ]; then
  echo "Descargando resultado..."
  curl -s "$BASE_URL/download/$JOB_ID" --output "${ARCHIVO%.pdf}.zip"
  echo "Listo: ${ARCHIVO%.pdf}.zip"
else
  echo "Error en la conversion"
fi
```

---

## Tecnologias

- **Backend**: Python 3.10+, Flask
- **Base de datos**: SQLite3
- **Frontend**: HTML5, CSS3, JavaScript vanilla (sin frameworks)
- **PDF**: PyMuPDF (fitz), pdf2image, pdfminer.six, python-docx
- **HTML a PDF**: WeasyPrint
- **Imagenes**: pdf2image + poppler
- **Contenedor**: Docker (imagen multi-stage para menor tamanio)

## Licencia

MIT License
