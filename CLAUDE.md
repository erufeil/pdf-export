## System Prompt:
Eres un asistente experto en desarrollo de sistemas web. Siempre guiate por CLAUDE.md como fuente de verdad.

## User Prompt:


## Objetivo General
Servicio de conversion de archivos PDF a distintos formatos, calidades o caracteristicas y algunas conversiones inversas, de otros formatos a PDF.


## STACK TECNOLÓGICO:
- Backend: Python 3.10+ con Flask
- Base de Datos: SQLite3
- Frontend: HTML5 + CSS3 + JavaScript Vanilla (sin frameworks)
- Sin Node.js ni herramientas de build

## Librerías Python: 
- PyMuPDF (fitz): manipulación general, rápido
- pdf2image + poppler: conversión a imágenes
- pdfminer.six: extracción de texto
- python-docx: generación de DOCX
- weasyprint

## REGLAS DE DESARROLLO:
- Código simple, legible y mantenible (prioridad máxima)
- Sin over-engineering: soluciones directas y eficientes
- Incluye comentarios explicativos en español
- Nombres de variables descriptivos en español
- Logging detallado para debugging
- Manejo robusto de errores de API (timeouts, rate limits)
- SQLite para persistencia (un solo archivo .db)
- Backend sirve archivos estáticos directamente
- Responsive design con CSS puro (sin frameworks CSS)
- Documentación online en español
- Frontend servido con Python:
El index.html para landing page debe estar en la carpeta principal, junto al config.js, para que cargue solo con https://IP:PORT y el resto del frontend en la carpeta static/
- ejemplo de archivo config.js que toma variables de entorno de docker:
window.AppConfig = {
    API_BASE_URL: '${BACKEND_PROTOCOL}://${BACKEND_HOST}:${BACKEND_PORT}/api/v1',
    timeout: ${TIMEOUT:-10000},
    retryAttempts: ${RETRY_ATTEMPTS:-3},
    configLoaded: true
};
- Nunca escribas el CLAUDE.md, propon el cambio y yo lo escribo.
- crea un README.md y mantenlo actualizado con la descripciones fundamentales de uso e instalacion para el Github

## PRINCIPIOS:
- Cada función debe tener un propósito claro y único
- Validación de datos en backend antes de guardar
- Interfaz intuitiva para usuarios no técnicos

## Arquitectura:
lenguaje: python
programacion: muy simple
landing page: index.html
Sistema operativo: ubuntu server 22.04.5 LTS
Contenedores: Docker


## Descripcion:
- el python sirve el endpoint y el index.html en el mismo contenedor
- todo lo que necesite el html sera simple sin librerias extra ni servicio de node.js
- usare una carpeta en servidor creada con git pull
- construire la imagen en servidor con docker build
- creare el contenedor con el docker compose
- logica de trabajo: recibe archivo, procesa, devuelve archivo de respuesta comprimido (.ZIP) a su maxima compresion posible.
- Carga del PDF de inmediato es seleccionado el archivo, tamaño maximo: 1Gb.
- el archivo cargado debe quedar en el servidor hasta 4 horas
- si entra otro usuario y selecciona para cargar el mismo archivo que ya esta cargado en el servidor no lo sube, retoma el que ya tiene cargado, basta con que coincidan: nombre, fecha y tamaño.
-Cola de trabajos: Para archivos grandes, mostrar progreso y notificar cuando termine
-Historial de conversiones: El usuario ve sus últimas conversiones (con las 4 horas de retención)
-Previsualización: Ver resultado antes de descargar (al menos primera página)
- API Key opcional: Para uso programático desde otras aplicaciones
- Limpieza automática: un proceso revisa cada hora y elimina archivos con más de 4 horas de antigüedad (cron dentro del contenedor o tarea programada de Python)
- Usuario unico, cualquier persona que entra tiene acceso a todo, es para usuarios internos y el control de acceso lo hare con nginx proxy manager


## Servicios

### Etapa 1. index.html: 
landing page de presentacion y menu de opciones, cada servicio tendra su pagina.html y su endpoint para ser usada desde otra API. Menu de servicios:
PDF a TXT: devuelve texto plano, remueve informacion de margenes: numero de pagina, pie de pagina, cabecera. 
PDF a DOCX
PDF a PNG: crea un PNG por cada pagina, calidad configurable
PDF a JPG: Alternativa a PNG (archivos más pequeños)
PDF a PDF de menor tamaño: compresion de imagenes con niveles de compresion seleccionables en porcentaje o DPI, optimizacion de PDF y reduccion de tamaño en todos sus elementos posibles
Extraccion de imagenes de PDF: extraccion de imagenes de un PDF
Cortar PDF:
Rotar PDF: crea miniaturas de las primeras 20 paginas y da la opcion de rotar alguna de a 90° en cada click (esta pensado para archivos chicos)
HTML a PDF: le pego la URL e intenta hacer un PDF solo del cuerpo (body) de la pagina web, intenta mantener lo mas fiel posible al sitio.
Unir PDF: combinar multiples PDF en uno solo.
Extraer paginas especificas: puede ser exportado a 1 unico PDF o todas por separado
Reordenar PDF: Drag & drop para cambiar orden
Debe tener la opcion de borrar todos los archivos cargados y los pdf creados y disponibles para descargar consecutivas.
Si hay actividades pendientes se ven en la landing page, cuando se aprieta 'ejecutar' en cualquier servicio se inicia el proceso pero el usuario vuelve a la landing page index.html y alli ve la evolucion del proceso y el archivo de descarga; aunque la descarga del proceso terminado se inicia automaticamente queda disponible por si se corta la conexion
Historial: debajo deberia haber un historial de archivos cargados y un historial de descargas.

### Etapa 2. Cortar PDF: 
quiero que cargue el pdf a separar en partes, y que mientras se carga me muestre una miniatura de la primera y ultima pagina en la seccion principal y en la seccion derecha el primer archivo a devolver en PDF con el numero de pagina 1 y ultimo (por ejemplo pagina numro 320) y que el usuario pueda editar cualquiera de los numeros de pagina de inicio y fin (por ejemplo inicia=3 y termina en 50 fin=50 ) y que actualice la imagen miniatura de esa pagina seleccionada por el usuario, que tenga la opcion de agregar otro corte y que si lo presiona 'agregaar' aparezca otro juego de imagenes miniaturas y otro juego de cortes desde la pagina de inicio=51 (la siguiente al termino anterior + 1) y fin=320 (ultima del documento) y con esto estaria generando un segundo archivo y asi hasta un maximo de 20 cortes; debe tener la opcion de generar 'N' cortes iguales y se calculan en forma automatica; y el boton de 'descargar' para ejecutar todos los cortes, comprimir el archivo e inicuar la descarga inmediatamente; debe poder volver a ingresar y ver los archivos cargados para seleccionarlos y no tener que cargarlos nuevamente; la imagenes miniaturas las debe hacer desde el front antes de subirlas, pero si el archivo coincide con el cargado en el servidor no cargarlo nuevamente.
### Etapa 3. PDF a TXT

**Página:** `static/pdf-to-txt.html`

**Descripción:** Convierte un PDF a texto plano, eliminando elementos de formato que no aportan al contenido principal.

**Interfaz de usuario:**
1. Zona de carga de archivo (drag & drop o seleccionar)
2. Opciones de extracción:
   - [ ] Remover números de página
   - [ ] Remover encabezados (detecta texto repetido en parte superior)
   - [ ] Remover pies de página (detecta texto repetido en parte inferior)
   - [ ] Preservar saltos de párrafo
   - [ ] Detectar columnas (para PDFs con múltiples columnas)
3. Vista previa del texto extraído (primeras 500 líneas)
4. Botón "Descargar TXT"

**Endpoint:** `POST /api/v1/convert/to-txt`

**Parámetros:**
```json
{
    "file_id": "uuid-del-archivo",
    "opciones": {
        "remover_numeros_pagina": true,
        "remover_encabezados": true,
        "remover_pies_pagina": true,
        "preservar_parrafos": true,
        "detectar_columnas": false
    }
}
```

**Lógica de detección de márgenes:**
- Encabezado: texto que aparece en los primeros 5% de cada página y se repite en >80% de las páginas
- Pie de página: texto en los últimos 5% de cada página que se repite
- Número de página: patrón numérico aislado que incrementa secuencialmente

---

### Etapa 4. PDF a DOCX

**Página:** `static/pdf-to-docx.html`

**Descripción:** Convierte un PDF a documento Word (.docx) intentando preservar el formato original.

**Interfaz de usuario:**
1. Zona de carga de archivo
2. Opciones de conversión:
   - [ ] Preservar imágenes
   - [ ] Preservar tablas (intenta detectar tablas)
   - [ ] Preservar estilos de texto (negrita, cursiva, tamaños)
   - Calidad de imágenes: [Baja | Media | Alta | Original]
3. Vista previa de primera página (miniatura)
4. Botón "Convertir a DOCX"

**Endpoint:** `POST /api/v1/convert/to-docx`

**Parámetros:**
```json
{
    "file_id": "uuid-del-archivo",
    "opciones": {
        "preservar_imagenes": true,
        "preservar_tablas": true,
        "preservar_estilos": true,
        "calidad_imagenes": "media"
    }
}
```

**Limitaciones conocidas:**
- PDFs escaneados (solo imagen) generarán DOCX con imágenes, no texto
- Diseños muy complejos pueden no preservarse exactamente
- Tablas con celdas combinadas pueden no detectarse correctamente

---

### Etapa 5. PDF a PNG

**Página:** `static/pdf-to-png.html`

**Descripción:** Convierte cada página del PDF en una imagen PNG individual.

**Interfaz de usuario:**
1. Zona de carga de archivo
2. Configuración de calidad:
   - DPI: [72 | 150 | 300 | 600] (slider o selector)
   - Mostrar tamaño estimado del resultado según DPI seleccionado
3. Rango de páginas:
   - ( ) Todas las páginas
   - ( ) Rango: desde [__] hasta [__]
   - ( ) Páginas específicas: [1, 3, 5-10]
4. Vista previa de primera página con calidad seleccionada
5. Información: "X páginas → aproximadamente Y MB"
6. Botón "Convertir a PNG"

**Endpoint:** `POST /api/v1/convert/to-png`

**Parámetros:**
```json
{
    "file_id": "uuid-del-archivo",
    "opciones": {
        "dpi": 150,
        "paginas": "all",
        "paginas_especificas": null
    }
}
```

**Resultado:** ZIP con archivos `pagina_001.png`, `pagina_002.png`, etc.

---

### Etapa 6. PDF a JPG

**Página:** `static/pdf-to-jpg.html`

**Descripción:** Igual que PDF a PNG pero genera JPG con compresión configurable.

**Interfaz de usuario:**
1. Zona de carga de archivo
2. Configuración:
   - DPI: [72 | 150 | 300 | 600]
   - Calidad JPG: [60% | 75% | 85% | 95%] (slider)
   - Mostrar comparativa de tamaño: PNG vs JPG estimado
3. Rango de páginas (igual que PNG)
4. Vista previa con calidad seleccionada
5. Botón "Convertir a JPG"

**Endpoint:** `POST /api/v1/convert/to-jpg`

**Parámetros:**
```json
{
    "file_id": "uuid-del-archivo",
    "opciones": {
        "dpi": 150,
        "calidad": 85,
        "paginas": "all"
    }
}
```

---

### Etapa 7. PDF a PDF Comprimido

**Página:** `static/pdf-compress.html`

**Descripción:** Reduce el tamaño del PDF comprimiendo imágenes y optimizando estructura.

**Interfaz de usuario:**
1. Zona de carga de archivo
2. Mostrar tamaño actual: "Archivo: 45.2 MB"
3. Nivel de compresión:
   - ( ) Baja (mejor calidad, menor reducción) - imágenes a 150 DPI, calidad 90%
   - ( ) Media (equilibrado) - imágenes a 120 DPI, calidad 75%
   - ( ) Alta (máxima reducción) - imágenes a 96 DPI, calidad 60%
   - ( ) Personalizada:
     - DPI máximo de imágenes: [___]
     - Calidad de compresión: [___%]
4. Opciones adicionales:
   - [ ] Eliminar metadatos
   - [ ] Eliminar anotaciones
   - [ ] Eliminar bookmarks
   - [ ] Convertir colores a escala de grises
5. Estimación de resultado: "Tamaño estimado: ~12 MB (reducción del 73%)"
6. Botón "Comprimir PDF"

**Endpoint:** `POST /api/v1/convert/compress`

**Parámetros:**
```json
{
    "file_id": "uuid-del-archivo",
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

---

### Etapa 8. Extracción de Imágenes de PDF

**Página:** `static/pdf-extract-images.html`

**Descripción:** Extrae todas las imágenes incrustadas en el PDF como archivos individuales.

**Interfaz de usuario:**
1. Zona de carga de archivo
2. Análisis automático al cargar:
   - "Se encontraron X imágenes en el documento"
   - Mostrar galería de miniaturas de las imágenes encontradas
3. Opciones:
   - Formato de salida: [Original | PNG | JPG]
   - [ ] Seleccionar todas
   - Checkboxes individuales para cada imagen
4. Filtros:
   - Tamaño mínimo: [___] px (para ignorar iconos pequeños)
5. Botón "Extraer Seleccionadas" o "Extraer Todas"

**Endpoint:** `POST /api/v1/convert/extract-images`

**Parámetros:**
```json
{
    "file_id": "uuid-del-archivo",
    "opciones": {
        "formato_salida": "original",
        "imagenes_seleccionadas": ["img_1", "img_3", "img_5"],
        "tamano_minimo_px": 100
    }
}
```

**Resultado:** ZIP con imágenes nombradas `imagen_001.png`, `imagen_002.jpg`, etc.

---

### Etapa 9. Rotar PDF

**Página:** `static/pdf-rotate.html`

**Descripción:** Permite rotar páginas individuales del PDF.

**Interfaz de usuario:**
1. Zona de carga de archivo
2. Grilla de miniaturas (primeras 20 páginas):
   ```
   [Pág 1]  [Pág 2]  [Pág 3]  [Pág 4]
   [Pág 5]  [Pág 6]  [Pág 7]  [Pág 8]
   ...
   ```
3. Cada miniatura muestra:
   - Imagen de la página
   - Número de página
   - Indicador de rotación actual (0°, 90°, 180°, 270°)
   - Click en la miniatura → rota 90° en sentido horario
4. Acciones rápidas:
   - [Rotar todas 90°] [Rotar todas 180°] [Restaurar]
5. Si el PDF tiene más de 20 páginas:
   - Paginador: [< Anterior] Páginas 1-20 de 45 [Siguiente >]
   - O selector de rango
6. Botón "Aplicar Rotaciones y Descargar"

**Endpoint:** `POST /api/v1/convert/rotate`

**Parámetros:**
```json
{
    "file_id": "uuid-del-archivo",
    "rotaciones": {
        "1": 90,
        "3": 180,
        "5": 270
    }
}
```

---

### Etapa 10. HTML a PDF

**Página:** `static/html-to-pdf.html`

**Descripción:** Convierte una página web a PDF capturando su contenido visual.

**Interfaz de usuario:**
1. Campo de URL: [https://________________________]
2. Botón "Vista Previa" (carga preview antes de convertir)
3. Opciones:
   - Tamaño de página: [A4 | Letter | Legal | A3]
   - Orientación: [Vertical | Horizontal]
   - Márgenes: [Sin márgenes | Normales | Amplios]
   - [ ] Incluir fondo/colores de fondo
   - [ ] Solo contenido principal (intenta remover navegación, ads, footer)
4. Vista previa del resultado (primera página)
5. Botón "Convertir a PDF"

**Endpoint:** `POST /api/v1/convert/from-html`

**Parámetros:**
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

**Consideraciones:**
- Timeout de 30 segundos para cargar la página
- Algunas páginas con JavaScript pesado pueden no renderizar correctamente
- Páginas que requieren login no funcionarán

---

### Etapa 11. Unir PDFs

**Página:** `static/pdf-merge.html`

**Descripción:** Combina múltiples archivos PDF en uno solo.

**Interfaz de usuario:**
1. Zona de carga múltiple (drag & drop varios archivos)
2. Lista de archivos cargados:
   ```
   ☰ documento1.pdf (15 páginas, 2.3 MB) [🗑️]
   ☰ documento2.pdf (8 páginas, 1.1 MB)  [🗑️]
   ☰ documento3.pdf (22 páginas, 5.4 MB) [🗑️]
   ```
   - ☰ = handle para drag & drop y reordenar
   - 🗑️ = eliminar de la lista
3. Información: "Total: 45 páginas, ~8.8 MB"
4. Opciones:
   - [ ] Agregar marcadores con nombre de cada archivo
5. Botón "Unir PDFs"

**Endpoint:** `POST /api/v1/convert/merge`

**Parámetros:**
```json
{
    "archivos": [
        {"file_id": "uuid-1", "orden": 1},
        {"file_id": "uuid-2", "orden": 2},
        {"file_id": "uuid-3", "orden": 3}
    ],
    "opciones": {
        "agregar_marcadores": true
    }
}
```

---

### Etapa 12. Extraer Páginas Específicas

**Página:** `static/pdf-extract-pages.html`

**Descripción:** Extrae páginas específicas de un PDF.

**Interfaz de usuario:**
1. Zona de carga de archivo
2. Visualización de miniaturas (similar a Rotar)
3. Métodos de selección:
   - Click en miniaturas para seleccionar/deseleccionar
   - Campo de texto: "Páginas: [1, 3, 5-10, 15]"
   - [Seleccionar todas] [Deseleccionar todas] [Invertir selección]
   - [Pares] [Impares]
4. Formato de salida:
   - ( ) Un único PDF con las páginas seleccionadas
   - ( ) Archivos separados (un PDF por página)
5. Resumen: "5 páginas seleccionadas"
6. Botón "Extraer Páginas"

**Endpoint:** `POST /api/v1/convert/extract-pages`

**Parámetros:**
```json
{
    "file_id": "uuid-del-archivo",
    "paginas": [1, 3, 5, 6, 7, 8, 9, 10, 15],
    "formato_salida": "unico"
}
```

---

### Etapa 13. Reordenar Páginas

**Página:** `static/pdf-reorder.html`

**Descripción:** Permite cambiar el orden de las páginas mediante drag & drop.

**Interfaz de usuario:**
1. Zona de carga de archivo
2. Grilla de miniaturas arrastrables:
   ```
   [1] [2] [3] [4]
   [5] [6] [7] [8]
   ```
   - Drag & drop para mover páginas
   - Visual feedback durante el arrastre
3. Acciones rápidas:
   - [Invertir orden]
   - [Restaurar orden original]
   - [Mover seleccionadas al inicio]
   - [Mover seleccionadas al final]
4. Para documentos grandes (>20 páginas):
   - Vista de lista compacta como alternativa
   - Campo: "Mover página [__] a posición [__]"
5. Botón "Aplicar Nuevo Orden"

**Endpoint:** `POST /api/v1/convert/reorder`

**Parámetros:**
```json
{
    "file_id": "uuid-del-archivo",
    "nuevo_orden": [3, 1, 2, 5, 4, 6, 7, 8]
}
```

---

## Resumen de Etapas

| Etapa | Servicio | Complejidad | Dependencias |
|-------|----------|-------------|--------------|
| 1 | Landing page + estructura base | Media | Flask, SQLite |
| 2 | Cortar PDF | Alta | PyMuPDF |
| 3 | PDF a TXT | Media | pdfminer.six |
| 4 | PDF a DOCX | Alta | python-docx, PyMuPDF |
| 5 | PDF a PNG | Baja | pdf2image, poppler |
| 6 | PDF a JPG | Baja | pdf2image, poppler |
| 7 | Comprimir PDF | Media | PyMuPDF |
| 8 | Extraer imágenes | Media | PyMuPDF |
| 9 | Rotar PDF | Baja | PyMuPDF |
| 10 | HTML a PDF | Media | weasyprint |
| 11 | Unir PDFs | Baja | PyMuPDF |
| 12 | Extraer páginas | Baja | PyMuPDF |
| 13 | Reordenar páginas | Media | PyMuPDF |

---

## Estructura de Carpetas Propuesta

```
PDFexport/
├── app.py                    # Aplicación Flask principal
├── config.py                 # Configuración
├── config.js                 # Config del frontend (generado)
├── index.html                # Landing page
├── requirements.txt          # Dependencias Python
├── Dockerfile
├── docker-compose.yml
├── CLAUDE.md
├── README.md
├── planificacion1.md
│
├── api/
│   ├── __init__.py
│   ├── routes_files.py       # Endpoints de archivos
│   ├── routes_convert.py     # Endpoints de conversión
│   └── routes_jobs.py        # Endpoints de trabajos
│
├── services/
│   ├── __init__.py
│   ├── pdf_to_txt.py
│   ├── pdf_to_docx.py
│   ├── pdf_to_images.py      # PNG y JPG
│   ├── pdf_compress.py
│   ├── pdf_extract_images.py
│   ├── pdf_split.py          # Cortar
│   ├── pdf_rotate.py
│   ├── html_to_pdf.py
│   ├── pdf_merge.py
│   ├── pdf_extract_pages.py
│   └── pdf_reorder.py
│
├── utils/
│   ├── __init__.py
│   ├── file_manager.py       # Gestión de archivos
│   ├── job_manager.py        # Cola de trabajos
│   └── thumbnail.py          # Generación de miniaturas
│
├── static/
│   ├── css/
│   │   └── styles.css
│   ├── js/
│   │   ├── common.js         # Funciones compartidas
│   │   ├── upload.js         # Lógica de carga
│   │   └── [servicio].js     # JS específico por servicio
│   ├── pdf-to-txt.html
│   ├── pdf-to-docx.html
│   ├── pdf-to-png.html
│   ├── pdf-to-jpg.html
│   ├── pdf-compress.html
│   ├── pdf-extract-images.html
│   ├── pdf-split.html
│   ├── pdf-rotate.html
│   ├── html-to-pdf.html
│   ├── pdf-merge.html
│   ├── pdf-extract-pages.html
│   └── pdf-reorder.html
│
├── uploads/                  # Archivos subidos (temporal)
├── outputs/                  # Archivos procesados (temporal)
└── data/
    └── pdfexport.db          # Base de datos SQLite
```

## API Endpoints

### Endpoints Base

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/` | Landing page (index.html) |
| `GET` | `/api/v1/status` | Estado del servicio y estadísticas |

### Endpoints de Archivos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/v1/upload` | Subir archivo PDF (multipart/form-data) |
| `GET` | `/api/v1/files` | Listar archivos disponibles (subidos en últimas 4h) |
| `GET` | `/api/v1/files/{id}` | Obtener info de un archivo específico |
| `GET` | `/api/v1/files/{id}/thumbnail/{page}` | Obtener miniatura de una página |
| `DELETE` | `/api/v1/files/{id}` | Eliminar un archivo |
| `DELETE` | `/api/v1/files` | Eliminar todos los archivos del usuario |

### Endpoints de Conversión

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/v1/convert/to-txt` | PDF a TXT |
| `POST` | `/api/v1/convert/to-docx` | PDF a DOCX |
| `POST` | `/api/v1/convert/to-png` | PDF a PNG (todas las páginas) |
| `POST` | `/api/v1/convert/to-jpg` | PDF a JPG (todas las páginas) |
| `POST` | `/api/v1/convert/compress` | Comprimir PDF |
| `POST` | `/api/v1/convert/extract-images` | Extraer imágenes del PDF |
| `POST` | `/api/v1/convert/split` | Cortar PDF en partes |
| `POST` | `/api/v1/convert/rotate` | Rotar páginas del PDF |
| `POST` | `/api/v1/convert/from-html` | HTML/URL a PDF |
| `POST` | `/api/v1/convert/merge` | Unir múltiples PDFs |
| `POST` | `/api/v1/convert/extract-pages` | Extraer páginas específicas |
| `POST` | `/api/v1/convert/reorder` | Reordenar páginas |

### Endpoints de Trabajos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/v1/jobs` | Listar trabajos (pendientes, en proceso, completados) |
| `GET` | `/api/v1/jobs/{id}` | Estado de un trabajo específico |
| `GET` | `/api/v1/jobs/{id}/progress` | Progreso en tiempo real (Server-Sent Events) |
| `DELETE` | `/api/v1/jobs/{id}` | Cancelar un trabajo |

### Endpoints de Descarga

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/v1/download/{job_id}` | Descargar resultado (ZIP) |
| `GET` | `/api/v1/downloads` | Historial de descargas disponibles |

---

## Respuestas Estándar de la API

### Respuesta exitosa
```json
{
    "success": true,
    "data": { ... },
    "message": "Operación completada"
}
```

### Respuesta de error
```json
{
    "success": false,
    "error": {
        "code": "FILE_TOO_LARGE",
        "message": "El archivo excede el límite de 1GB"
    }
}
```

### Respuesta de trabajo iniciado
```json
{
    "success": true,
    "job": {
        "id": "uuid-del-trabajo",
        "status": "pending",
        "progress": 0,
        "created_at": "2024-01-15T10:30:00Z"
    }
}
```
..
.
