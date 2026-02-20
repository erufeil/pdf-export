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
- beautifulsoup4: parsing HTML (scraper)
- trafilatura: extracción de contenido principal de páginas web (scraper)
- markdownify: conversión HTML → Markdown (scraper)
- lxml: parser HTML rápido requerido por beautifulsoup4 y trafilatura


## Otras Librerías / programas
poppler:
    poppler-windows: https://github.com/oschwartz10612/poppler-windows/releases
    linux: RUN apt-get update && apt-get install -y poppler-utils


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

## CONVENCION DE NOMBRES PARA ARCHIVOS DE SALIDA:

Los archivos generados por cualquier servicio de conversion deben mantener el nombre original del archivo de entrada (incluyendo la extension) y agregar un sufijo descriptivo con numeracion consistente.

### Formato general:
```
{nombre_original_con_extension} - {tipo} {numero_con_padding}.{extension_salida}
```

### Reglas:

1. **Nombre base**: Siempre usar el nombre original completo del archivo, incluyendo su extension (ej: "libro.pdf", no solo "libro")

2. **Separador**: Usar " - " (espacio, guion, espacio) entre el nombre base y el sufijo

3. **Tipo de sufijo**: Depende del servicio:
   - Conversion a imagenes por pagina: "pagina"
   - Extraccion de imagenes: "imagen"
   - Corte de PDF: "pag. {inicio} - {fin}"

4. **Padding del numero**:
   - El numero debe tener tantos digitos como el total de elementos del documento
   - Si el documento tiene 100 paginas → usar 3 digitos (001, 002, ..., 100)
   - Si el documento tiene 15 paginas → usar 2 digitos (01, 02, ..., 15)
   - Si el documento tiene 8 imagenes → usar 1 digito (1, 2, ..., 8)

### Ejemplos:

| Servicio | Archivo entrada | Total elementos | Archivo salida |
|----------|-----------------|-----------------|----------------|
| PDF a PNG | libro.pdf | 100 paginas | libro.pdf - pagina 003.png |
| PDF a JPG | manual.pdf | 15 paginas | manual.pdf - pagina 08.jpg |
| Extraer imagenes | documento.pdf | 25 imagenes | documento.pdf - imagen 12.png |
| Cortar PDF | reporte.pdf | 320 paginas | reporte.pdf - pag. 051 - 100.pdf |

### Archivos ZIP de salida:

El nombre del archivo ZIP tambien debe ser descriptivo:
```
{trabajo_id}_{nombre_base_sin_extension}_{tipo_conversion}.zip
```

Ejemplos:
- `abc123_libro_png.zip`
- `def456_manual_jpg.zip`
- `ghi789_documento_imagenes.zip`
- `jkl012_reporte_cortes.zip`

---

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

### Etapa 14. Generar el orden secuencial de migracion de tablas SQL

## Nombre del boton para index.html
                        <div class="card-icon">NDM</div>
                        <h3>Migrar SQL</h3>
                        <p>Ordenar Tablas p/export</p>

## Objetivo
Debe generar el orden secuencial de migracion de tablas de bases de datos SQL teniendo en cuenta las PK y FK.
Teniendo: una tabla A: pk y otra tabla B: pk y fk_tabla_A. Como la fk_tabla_A es foranea en tabla B la tabla A debe ir primero y tabla B segunda por que tabla B depende de tabla A.

## Estructura del archivo fuente
Formato: Navicat Data Modeler (versión 2), JSON
Fuente: ArchivoUploaded.ndm2

## Mapa de rutas del JSON
El archivo .ndm2 tiene esta jerarquía (simplificada):
json_ndm = importar-json("ArchivoUploaded.ndm2")

json_ndm                              ← raíz del archivo
├── server
│   └── schemas[]                     ← lista de esquemas (usamos el primero)
│       ├── name                      ← nombre de la base de datos
│       └── tables[]                  ← lista de tablas (se recorre completa)
│           ├── name                  ← nombre de la tabla
│           └── foreignKeys[]         ← lista de FKs (puede estar vacía)
│               ├── referenceSchema   ← base de datos de la tabla referenciada
│               └── referenceTable    ← nombre de la tabla referenciada

Acceso en Python:

esquema           = json_ndm["server"]["schemas"][0]
nombre_db         = esquema["name"]                        → "MASVIDADIGNA"
lista_tablas      = esquema["tables"]                      → [tabla1, tabla2, ...]
  ┗ por cada tabla en lista_tablas:
      nombre_tabla  = tabla["name"]                        → "T_USUARIOS"
      lista_fks     = tabla["foreignKeys"]                 → [{fk1}, {fk2}] o []
        ┗ por cada fk en lista_fks:
            db_fk     = fk["referenceSchema"]              → "MASVIDADIGNA"
            tabla_fk  = fk["referenceTable"]               → "T_INSCRIPCIONES_MVD"

## Logica de programacion

**Página:** `static/ndm-to-tables-seq.html`
**Descripción:** Analiza archivo ndm2 y devuelve secuencia logica de migracion de tablas.
**Endpoint:** `POST /api/v1/convert/ndm-to-tables-seq`
**Parámetros:**
```json
{
    "file_id": "uuid-del-archivo",
    "opciones": {
        "formato_salida": "original",
        "sin_comprimir": true
    }
}
```
 
1. importa el json y define variables: nombre_db_principal_json, orden_de_migracion, notas_al_pie, control_cambios=0, max_iteraciones = 1000
2. extrae los nombres de las tablas
3. ordena segun algoritmo
4. devolver archivo .TXT en texto plano compatible con notepad de windows

## Algoritmo:

### Extraccion y 1er orden: sin FK primero con FK despues
Extrae el nombre de la tabla de json_ndm["server"]["schemas"]["name"] en la variable nombre_db_principal_json.
Recorre la clave json_ndm["server"]["schemas"]["tables"]["name"] y json_ndm["server"]["schemas"]["tables"]["foreignKeys"] de cada "tables" extrayendo el valor de cada clave en las variables nombre_tabla_json y fk_tabla_json respectivamente. 
En cada iteración arma una lista llamada orden_de_migracion con los nombres de las tablas pero antes revisa: si fk_tabla_json == [] entonces agrega nombre_tabla_json al comienzo de orden_de_migracion, caso contrario al final.
max_iteraciones = len(orden_de_migracion)

## Orden de prioridad

1. Recorre la lista orden_de_migracion de principio a fin, extrayendo cada
   elemento en nombre_tabla_lista y su posición en posicion_tabla_lista.

2. Para cada nombre_tabla_lista, busca su entrada correspondiente en el JSON
   (donde nombre_tabla_json == nombre_tabla_lista) y extrae fk_tabla_json.

   2.1. Si fk_tabla_json == [] (sin foreign keys), pasa al siguiente elemento
        de orden_de_migracion.

   2.2. Si tiene foreign keys, recorre cada FK dentro de fk_tabla_json
        extrayendo "referenceSchema" en db_tabla_fk y "referenceTable"
        en tabla_fk.

        2.2.a. Si db_tabla_fk != nombre_db_principal_json, agrega en
               notas_al_pie: 'WARNING: {tabla_fk} pertenece a la base
               de datos {db_tabla_fk}' y continúa con punto 2.2.b.

        2.2.b. Busca la posición de tabla_fk en orden_de_migracion y
               la guarda en posicion_tabla_fk.
               Si posicion_tabla_fk > posicion_tabla_lista entonces:
               borra nombre_tabla_lista de orden_de_migracion, lo inserta
               en posicion_tabla_fk y marca control_cambios = 1.
               Caso contrario, continúa.

   2.3. Una vez recorridas todas las FK de este elemento, pasa al siguiente
        elemento de orden_de_migracion.

3. Una vez recorrida toda la lista, evalúa control_cambios:

   3.1. Si control_cambios == 0, termina y continúa con la devolución
        de la lista.

   3.2. Si control_cambios == 1:
        iteraciones += 1
        Si iteraciones >= max_iteraciones, agrega en notas_al_pie:
        'WARNING: Posible dependencia circular detectada' y termina.
        Caso contrario, coloca control_cambios = 0 y vuelve al paso 1.

## Formato del archivo a devolver:
Nombre: 'Orden_secuencial_migracion_SQL_ERF.txt'
Formato: texto plano para notepad de windows
Presentacion:
Titulo: Orden migracion de {nombre_db_principal_json}
Cuerpo: orden_de_migracion en formato de lista:
1. Tabla1
2. Tabla2
3. Tabla3
...
Pie del documento: notas_al_pie

### Nota de la IA: 
El algoritmo es un "Topological Sort". Lo que describís es esencialmente un ordenamiento topológico de un grafo dirigido (tablas = nodos, FK = aristas). Python tiene graphlib.TopologicalSorter desde Python 3.9 que hace exactamente esto y detecta ciclos automáticamente. Libreria que no usaremos e implementaremos este algoritmo.

---

### Etapa 15. Extraer Tablas de PDF a CSV

## Nombre del boton para index.html
<div class="card-icon">CSV</div>
<h3>PDF a CSV</h3>
<p>Extraer tablas a CSV</p>

**Página:** `static/pdf-to-csv.html`

**Endpoint:** `POST /api/v1/convert/to-csv`

## Objetivo
Detecta y extrae todas las tablas del PDF generando un archivo CSV por cada tabla encontrada, comprimidos en ZIP.

Solo importa el contenido alfanumerico de la tabla.

## Nombre de archivos de salida
- Formato General del CSV:
Tomando como titulo_de_la_tabla a la oracion con letra mas grande antes de la tabla buscando hasta 15 renglones antes (fallback texto en negrita antes de la tabla hasta 15 renglones)

Designar al nombre del archivo como : `tabla_pag{N}_{M}_{titulo_de_la_tabla}` (página número N, tabla número M en esa página, primeros 20 caracteres de titulo_de_la_tabla).

- Con tablas unificadas del CSV: `tabla_pag{N}_{M}_unificada`

- ZIP: `{nombre_base}_csv.zip`



**Interfaz de usuario:**
1. Zona de carga de archivo
2. Análisis automático al cargar:
   - "Se encontraron X Tablas en el documento"
   - "Algunas Parecen ser la misma tabla en varias hojas: SI/NO"   
   - "Encoding: [utf-8-bom]"
   - "WARNING: No hay tablas"
3. Opciones:
   - [ ] Unificar tablas iguales en un solo archivo
   - Separador de Valores: [;] (decimales con coma) - [,] (decimales con punto)
   - Saltos de línea: [CRLF] (Windows) - [LF] (Unix) 
4. Botón "Extraer Tablas a CSV" (desactivado si no hay tablas detectadas)

**Parámetros:**
```json
{
    "file_id": "uuid-del-archivo",
    "opciones": {
        "unificar_iguales": true,
        "separador": ";",
        "saltos_línea": "CRLF"
    }
}
```
**Librería:** pdfplumber (agregar a requirements.txt) como primera opción, con fallback a PyMuPDF si no tiene tablas con líneas claras. Habría que agregar pdfplumber al requirements.txt.

## Notas de implementación
- PDFs escaneados (solo imagen): informar al usuario que no hay tablas extraíbles
- Detección de "mismo esquema": mismas cabeceras en mismo orden (normalizado: strip + lowercase)
- opcion "unificar_iguales": si las tablas tienen las mismas cabeceras unificarlas en un solo archivo sin repetir cabecera (comparar strings de cada nombre sin espacios). Si el orden de las columnas difiere no unificar

---

### Etapa 16. Web Scraper de Contenido

## Nombre del boton para index.html
                        <div class="card-icon">SCR</div>
                        <h3>Scraper Web</h3>
                        <p>Extraer contenido para IA</p>

**Página:** `static/web-scraper.html`

**Descripción:** Extrae contenido estructurado de una URL para procesamiento con IA o inserción manual en documentos. Genera un TXT organizado en secciones: metadatos del header, cuerpo principal en Markdown o texto plano, información de contacto del footer y lista de links.

## Objetivo
Scrapear una página web y devolver su contenido de forma limpia y estructurada, eliminando navegación, publicidad y elementos decorativos. Ideal para procesar artículos, documentación y noticias con una IA o para copiar manualmente a DOCX.

## Stack de librerías (por capa)
- **HTTP:** `requests` (ya en requirements)
- **Parsing HTML:** `beautifulsoup4` + `lxml`
- **Extracción de contenido principal:** `trafilatura` (estado del arte en "boilerplate removal", elimina nav/ads/sidebar automáticamente, detecta fecha/autor)
- **HTML → Markdown:** `markdownify` (preserva links, negritas, listas, tablas)

**Interfaz de usuario:**
1. Campo de URL: [https://________________________]
2. Botón "Previsualizar" (llamada sincrona, muestra tabs con resultado parcial)
3. Tabs de preview: Metadatos | Contenido | Footer | Links
4. Opciones:
   - Formato del cuerpo: [Markdown (ideal para IA) | Texto plano]
   - Secciones a incluir: [x] Metadatos [x] Contenido [x] Footer [x] Links
5. Botón "Extraer y Descargar ZIP"

**Endpoint principal:** `POST /api/v1/convert/scrape-url`

**Endpoint de preview (sincrono):** `POST /api/v1/convert/scrape-url/preview`

**Parámetros:**
```json
{
    "url": "https://ejemplo.com/articulo",
    "opciones": {
        "formato_salida": "markdown",
        "incluir_metadatos": true,
        "incluir_contenido": true,
        "incluir_footer": true,
        "incluir_links": true
    }
}
```

## Estructura del TXT generado
```
================================================================================
METADATOS
================================================================================
Titulo:      El titulo del articulo
URL:         https://ejemplo.com/articulo
Sitio:       ejemplo.com
Fecha:       2024-01-15
Autor:       Juan Perez
Descripcion: Resumen de 160 caracteres...

================================================================================
CONTENIDO PRINCIPAL (Markdown)
================================================================================
## Titulo del articulo

Primer parrafo del contenido limpio...

### Subtitulo

Mas contenido con **texto en negrita** y [links](https://url.com)...

================================================================================
FOOTER / CONTACTO
================================================================================
Correos:    contacto@empresa.com, info@empresa.com
Telefonos:  +54 11 1234-5678
Texto del footer: Empresa SRL | Av. Corrientes 1234, CABA

================================================================================
LINKS (N encontrados)
================================================================================
- Titulo del link: https://url.com
```

## Logica de extraccion de metadatos
Prioridades (de mayor a menor):
- Titulo: og:title > title tag
- URL: canonical link > og:url > URL original
- Fecha: article:published_time > meta date > time[itemprop=datePublished]
- Autor: article:author > meta author > span[itemprop=author] > a[rel=author]
- Descripcion: og:description > meta description

## Logica de extraccion del footer
- Busca etiquetas `<footer>` y elementos con id/class que contengan "footer", "contact", "contacto", "about", "pie"
- Aplica regex para emails: `[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}`
- Aplica regex para telefonos: números con >= 7 dígitos

**Consideraciones:**
- Timeout de 30 segundos para descargar la página
- Funciona mejor con artículos, blogs, noticias y documentación
- Páginas con login obligatorio o 100% dinámicas (SPA sin SSR) no funcionarán
- El archivo resultado es un ZIP con un TXT (CRLF, compatible Notepad Windows)

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
| 14 | Migrar SQL (NDM2) | Media | json stdlib |
| 15 | PDF a CSV (tablas) | Media | pdfplumber, PyMuPDF |
| 16 | Web Scraper de Contenido | Media | beautifulsoup4, trafilatura, markdownify |

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
| `POST` | `/api/v1/convert/scrape-url` | Scrapear URL → TXT estructurado (Etapa 16) |
| `POST` | `/api/v1/convert/scrape-url/preview` | Vista previa sincrona del scraping |

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
| 14 | Migrar SQL (NDM2) | Media | json stdlib |
| 15 | PDF a CSV (tablas) | Media | pdfplumber, PyMuPDF |
| 16 | Web Scraper de Contenido | Media | beautifulsoup4, trafilatura, markdownify |

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
| `POST` | `/api/v1/convert/scrape-url` | Scrapear URL → TXT estructurado (Etapa 16) |
| `POST` | `/api/v1/convert/scrape-url/preview` | Vista previa sincrona del scraping |

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