# Guía de Usuario — PDF-Export

> Herramienta interna de conversión y manipulación de archivos PDF.
> Para uso en red local, sin registro ni contraseña.

---

## ¿Qué es PDF-Export?

Una herramienta web que corre en el servidor interno. Podés acceder desde cualquier navegador en la red. Permite convertir, cortar, unir, comprimir y manipular archivos PDF sin instalar nada en tu computadora.

**Los archivos se eliminan automáticamente después de 4 horas.**

---

## Cómo funciona en general

1. Entrás a la dirección del servidor desde el navegador
2. Elegís el servicio que necesitás
3. Subís el archivo (se carga automáticamente al seleccionarlo)
4. Configurás las opciones si las hay
5. Hacés clic en el botón de acción
6. El resultado se descarga automáticamente como archivo ZIP

**Si ya subiste un archivo antes y todavía no pasaron 4 horas, el sistema lo reconoce y no lo vuelve a subir.** Basta con que tenga el mismo nombre, fecha y tamaño.

---

## Servicios disponibles

---

### ✂️ Cortar PDF
**Divide un PDF en partes definiendo rangos de páginas.**

- Subís el PDF y se muestran vistas previas de cada corte
- Definís desde qué página hasta qué página va cada parte
- Podés agregar hasta 20 cortes distintos
- También podés decirle "dividir en N partes iguales" y lo calcula solo
- El resultado es un ZIP con un PDF por cada corte

**Útil para:** separar capítulos, distribuir secciones de un manual, extraer una parte de un informe largo.

---

### 📝 PDF a TXT
**Extrae el texto de un PDF como archivo de texto plano.**

Opciones disponibles:
- Remover números de página
- Remover encabezados repetidos (detecta texto que aparece en todas las páginas arriba)
- Remover pies de página repetidos
- Preservar saltos de párrafo
- Detectar columnas (para PDFs con diseño en dos columnas)

**Útil para:** copiar texto de un PDF para editar, procesar con IA, buscar dentro del contenido.

**Limitación:** PDFs escaneados (fotos de documentos) no tienen texto extraíble. El resultado saldrá vacío o con basura.

---

### 📄 PDF a DOCX
**Convierte un PDF a documento Word (.docx) intentando preservar el formato.**

Opciones:
- Preservar imágenes incrustadas
- Preservar tablas
- Preservar estilos de texto (negrita, cursiva, tamaños)
- Calidad de imágenes: Baja / Media / Alta / Original

**Útil para:** editar el contenido de un PDF en Word.

**Limitaciones conocidas:**
- PDFs escaneados generan un DOCX con imágenes, no con texto editable
- Diseños muy complejos (columnas, cajas de texto superpuestas) pueden no preservarse exactamente
- Tablas con celdas combinadas pueden no detectarse bien

---

### 🖼️ PDF a PNG
**Convierte cada página del PDF en una imagen PNG.**

Opciones:
- Calidad (DPI): 72 / 150 / 300 / 600
  - 72 DPI → imágenes pequeñas, baja calidad
  - 300 DPI → calidad de impresión
  - 600 DPI → altísima calidad, archivos grandes
- Rango de páginas: todas, un rango (ej: 3 a 10), o páginas específicas (ej: 1, 3, 7-12)

El resultado es un ZIP con un PNG por página.

**Útil para:** insertar páginas de un PDF en presentaciones, compartir páginas como imágenes, hacer capturas de alta calidad.

---

### 🖼️ PDF a JPG
**Igual que PDF a PNG pero en formato JPG (archivos más pequeños).**

Opciones adicionales respecto a PNG:
- Calidad JPG: 60% / 75% / 85% / 95%
  - Menor calidad → archivo más pequeño
  - Mayor calidad → mejor imagen pero más pesado

**Útil para:** cuando necesitás imágenes más livianas para enviar por mail o subir a sistemas con límite de tamaño.

---

### 📦 Comprimir PDF
**Reduce el tamaño del PDF sin cambiar su contenido.**

Niveles de compresión:
- **Baja:** mejor calidad, menor reducción (imágenes a 150 DPI)
- **Media:** equilibrado (120 DPI) — recomendado para la mayoría de los casos
- **Alta:** máxima reducción, calidad visiblemente menor (96 DPI)
- **Personalizada:** definís vos el DPI y el porcentaje de calidad

Opciones adicionales:
- Eliminar metadatos (autor, programa que lo creó, fechas de edición)
- Eliminar anotaciones (comentarios, marcas)
- Eliminar bookmarks (índice/marcadores del PDF)
- Convertir a escala de grises (elimina el color → reduce bastante el tamaño)

**Útil para:** reducir PDFs pesados antes de enviarlos por mail, subirlos a portales que tienen límite de tamaño.

---

### 🔍 Extraer imágenes de PDF
**Extrae todas las imágenes incrustadas en el PDF como archivos individuales.**

- Muestra cuántas imágenes encontró antes de descargar
- Podés elegir el formato de salida: Original / PNG / JPG
- Filtro de tamaño mínimo: ignorar imágenes menores a X píxeles (para no incluir iconos o decoraciones diminutas)

**Útil para:** recuperar fotos, gráficos o ilustraciones que están dentro de un PDF.

**Limitación:** solo extrae imágenes incrustadas como objetos independientes. No puede extraer imágenes que son parte de un PDF escaneado (que es una sola imagen grande de toda la página).

---

### 🔄 Rotar páginas
**Rota páginas individuales del PDF.**

- Muestra miniaturas de las páginas
- Hacés clic en una miniatura → rota 90° en sentido horario
- Seguís haciendo clic para seguir rotando (90° → 180° → 270° → 0°)
- Botones rápidos: rotar todas 90°, todas 180°, restaurar todo
- Funciona con PDFs de cualquier tamaño (para más de 20 páginas muestra paginación)

**Útil para:** corregir páginas que quedaron de costado al escanear.

---

### 🌐 HTML a PDF
**Convierte una página web a PDF.**

- Pegás la URL de la página
- Opciones de página: A4, Letter, Legal, A3
- Orientación: vertical u horizontal
- Márgenes: sin márgenes, normales, amplios
- Opción de incluir o no el fondo/colores de la página
- Opción de extraer solo el contenido principal (intenta eliminar menú, publicidades, footer)

**Útil para:** guardar artículos, documentación online, páginas web como PDF.

**Limitaciones:**
- Páginas que requieren estar logueado no van a funcionar
- Sitios con mucho JavaScript dinámico pueden no renderizarse bien
- Algunas páginas bloquean el acceso a bots

---

### 🔗 Unir PDFs
**Combina múltiples archivos PDF en uno solo.**

- Subís varios PDFs a la vez (drag & drop o selección múltiple)
- Los podés reordenar arrastrando antes de unir
- Opción de agregar marcadores (bookmarks) con el nombre de cada archivo original

**Útil para:** juntar partes de un informe, combinar formularios, armar un expediente.

---

### 📑 Extraer páginas específicas
**Extrae páginas puntuales de un PDF.**

Métodos de selección:
- Hacés clic en las miniaturas de las páginas que querés
- Escribís el rango: `1, 3, 5-10, 15`
- Botones de selección rápida: todas, ninguna, invertir, pares, impares

Formato de salida:
- Un único PDF con todas las páginas seleccionadas
- Un PDF separado por cada página

**Útil para:** sacar páginas específicas de un informe, separar anexos, armar un subconjunto de un documento.

---

### 🔀 Reordenar páginas
**Cambia el orden de las páginas con drag & drop.**

- Arrastrás las miniaturas para cambiar el orden
- Acciones rápidas: invertir orden, restaurar el original
- Para documentos grandes: vista de lista más compacta + campo para mover página X a posición Y

**Útil para:** corregir el orden de páginas escaneadas, reorganizar secciones.

---

### 📊 Migrar SQL (NDM2)
**Genera el orden correcto de migración de tablas de una base de datos.**

- Subís un archivo `.ndm2` (Navicat Data Modeler)
- El sistema analiza las claves foráneas (FK) y determina en qué orden hay que exportar/importar las tablas para respetar las dependencias
- El resultado es un archivo `.txt` con la lista ordenada

**Útil para:** migraciones de bases de datos donde el orden importa (tabla A antes que tabla B porque B depende de A).

---

### 📋 PDF a CSV (tablas)
**Extrae tablas de un PDF y las convierte a archivos CSV.**

- Detecta automáticamente cuántas tablas hay en el documento
- Opción de unificar tablas con la misma estructura en un solo archivo
- Configuración de separador: `;` (decimales con coma) o `,` (decimales con punto)
- Configuración de saltos de línea: CRLF (Windows) o LF (Unix)

**Útil para:** recuperar datos numéricos o tabulares de informes PDF para trabajarlos en Excel.

**Limitación:** no funciona con PDFs escaneados (las tablas tienen que ser texto real, no imagen).

---

### 🌐 Scraper Web
**Extrae el contenido de una página web en formato limpio para usar con IA.**

- Pegás la URL
- El sistema descarga la página y extrae solo el contenido relevante (elimina menú, publicidades, footer)
- El resultado incluye: metadatos (título, autor, fecha), contenido principal en Markdown o texto plano, información de contacto del footer, lista de links

**Útil para:** preparar contenido para procesar con ChatGPT u otra IA, guardar artículos limpios.

**Limitación:** no funciona con páginas que requieren login o que son 100% dinámicas (SPAs sin servidor).

---

### 🖼️ Imágenes a PDF
**Junta múltiples imágenes en un único PDF.**

- Subís imágenes de cualquier tipo (JPG, PNG, BMP, TIFF, WebP, etc.)
- Las podés reordenar antes de convertir
- El resultado es un PDF con una imagen por página

**Útil para:** convertir fotos de un documento escaneado en un solo PDF.

---

### 🔄 WEBP a PNG
**Convierte imágenes en formato WebP a PNG.**

WebP es el formato moderno de imágenes en la web que algunos programas todavía no abren. Este servicio las convierte a PNG estándar.

---

## Herramientas forenses

### 🔍 Metadatos PDF

**Extrae la información oculta de un archivo PDF.**

Muestra datos que no se ven al abrir el PDF normalmente: quién lo creó, con qué programa, cuándo fue modificado, si fue alterado desde su creación original, qué fuentes usa, si tiene formularios o firmas digitales, y sus permisos de impresión/copia.

- Detecta si el PDF fue modificado externamente (los IDs de documento difieren)
- Permite editar los metadatos básicos (título, autor, tema) y guardar un nuevo PDF

**Útil para:** verificar la autenticidad de documentos, auditorías, análisis forense.

---

### 🖼️ Metadatos Imagen

**Extrae toda la información técnica y forense de una imagen.**

Muestra datos EXIF de la cámara (modelo, apertura, velocidad, ISO), coordenadas GPS si las tiene, fecha y hora de captura, si fue editada en Photoshop (historial XMP), colores dominantes, hashes de integridad (SHA-256 y MD5), perfil de color ICC y más.

- Detecta si la imagen fue editada comparando el ID de documento con el ID de instancia
- Muestra el enlace de OpenStreetMap si la imagen tiene coordenadas GPS

**Útil para:** verificar dónde y cuándo se sacó una foto, detectar ediciones, análisis forense de imágenes.

---

## Límites y consideraciones

| Límite | Valor |
|--------|-------|
| Tamaño máximo de archivo | 2 GB |
| Tiempo de retención de archivos | 4 horas |
| Máximo de cortes en "Cortar PDF" | 20 |
| Máximo de páginas mostradas en rotación/reordenado | 20 por pantalla (paginado) |

---

## Preguntas frecuentes

**¿Tengo que instalar algo?**
No. Solo necesitás un navegador web y acceso a la red interna.

**¿Es seguro subir mis archivos?**
Los archivos se guardan temporalmente en el servidor interno y se eliminan automáticamente a las 4 horas. No salen de la red interna.

**El archivo tardó mucho en procesarse, ¿qué hago?**
Los archivos grandes pueden tardar. Podés volver a la página de inicio (botón "Tengo un PDF...") y ver el progreso del trabajo en la sección de trabajos activos.

**Convertí a DOCX pero el formato quedó mal, ¿qué hago?**
La conversión PDF → DOCX es imperfecta por naturaleza. El PDF es un formato de "presentación fija" y Word es de "flujo de texto". Cuanto más complejo el diseño original (columnas, cuadros, tablas), más diferencias vas a ver.

**El scraper no trae nada de la página que quiero.**
Puede ser que el sitio requiera login, que use JavaScript dinámico, o que bloquee los scrapers. En esos casos no hay solución desde esta herramienta.

**¿Puedo usar esto desde una aplicación propia?**
Sí, todos los servicios tienen endpoints de API. Consultá con el administrador del sistema para el acceso programático.
