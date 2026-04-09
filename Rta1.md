# Propuesta de Mejoras — PDF-Export

> Análisis de la IA sobre funcionalidades que agregarían valor real al sistema.
> Ordenadas por impacto estimado vs. esfuerzo de implementación.

---

## GRUPO 1 — Alto impacto, esfuerzo bajo

Son mejoras que se pueden implementar en 1-2 sesiones y que el usuario nota de inmediato.

---

### MEJ-01 — OCR para PDFs escaneados

**Qué es:** Actualmente, si un PDF es una foto (escaneado), no se puede extraer texto. OCR (Reconocimiento Óptico de Caracteres) convierte esas imágenes en texto real.

**Impacto:** Los PDFs escaneados son muy comunes en oficinas. Esta mejora habilitaría los servicios de PDF a TXT, PDF a DOCX y PDF a CSV sobre documentos que hoy no funcionan.

**Cómo:** Agregar `pytesseract` (Python) + `tesseract-ocr` (sistema) al contenedor. Tesseract soporta español. Se agregaría como opción dentro de "PDF a TXT": un checkbox "Este PDF está escaneado — usar OCR".

**Esfuerzo:** Medio. Requiere instalar Tesseract en el Dockerfile y escribir ~50 líneas de integración.

---

### MEJ-02 — Protección con contraseña al PDF de salida

**Qué es:** Al comprimir, unir, cortar o convertir un PDF, agregar la opción de protegerlo con contraseña de apertura.

**Impacto:** Muy útil para distribuir documentos internos con acceso controlado.

**Cómo:** PyMuPDF soporta cifrado nativo: `doc.save(..., encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="...", user_pw="...")`. Se agrega un campo de contraseña opcional en los formularios relevantes.

**Esfuerzo:** Bajo. PyMuPDF ya tiene todo. Es principalmente UI + pasar el parámetro.

---

### MEJ-03 — Vista previa del resultado antes de descargar

**Qué es:** Antes de descargar el ZIP, mostrar una miniatura de la primera página del resultado.

**Impacto:** El usuario confirma visualmente que el resultado es correcto sin necesidad de descargar y abrir.

**Cómo:** Al completar un trabajo, el backend ya genera el archivo de salida. Se puede agregar un endpoint que retorne una miniatura del primer PDF del resultado. Aplica a: comprimir, rotar, cortar, reordenar, extraer páginas, unir.

**Esfuerzo:** Bajo. La función `generar_miniatura` ya existe. Solo hay que exponerla para el archivo de salida y actualizar la UI de descarga.

---

### MEJ-04 — Eliminar páginas en blanco automáticamente

**Qué es:** Opción en "PDF a TXT" y "PDF a DOCX" para detectar y omitir páginas que están en blanco o casi en blanco.

**Impacto:** Los PDFs escaneados suelen tener páginas en blanco intercaladas (reverso de hoja). Esto las elimina solo.

**Cómo:** PyMuPDF. Se analiza si el texto extraído de una página tiene menos de N caracteres y si el pixmap tiene variación de color menor a un umbral.

**Esfuerzo:** Bajo.

---

### MEJ-05 — Descarga directa sin ZIP cuando hay un solo archivo

**Qué es:** Cuando el resultado es un único archivo (ej: comprimir PDF, unir PDFs, PDF a DOCX), descargarlo directamente en lugar de empaquetar en ZIP.

**Impacto:** Menos fricción. El usuario recibe el archivo listo para usar sin tener que descomprimir.

**Cómo:** En el backend, si `len(archivos_resultado) == 1`, hacer `send_file` directo. Si son múltiples, hacer ZIP como hoy.

**Esfuerzo:** Bajo. Un condicional en cada servicio que siempre produce un solo archivo de salida.

---

## GRUPO 2 — Alto impacto, esfuerzo medio

Requieren más trabajo pero agregan capacidades significativas.

---

### MEJ-06 — Marca de agua (watermark)

**Qué es:** Agregar texto o imagen como marca de agua a todas las páginas de un PDF.

**Opciones:**
- Texto diagonal (ej: "CONFIDENCIAL", "BORRADOR", nombre de empresa)
- Imagen (logo) en esquina
- Configuración de opacidad, tamaño, posición

**Impacto:** Muy pedida en entornos corporativos para documentos en circulación.

**Cómo:** PyMuPDF permite insertar texto e imágenes con transparencia sobre páginas existentes.

**Esfuerzo:** Medio. La lógica de aplicación es directa; la UI de configuración tiene más trabajo (posición, opacidad, previsualización).

---

### MEJ-07 — Numerar páginas

**Qué es:** Agregar numeración de páginas a un PDF que no la tiene, o renumerar uno existente.

**Opciones:**
- Posición: arriba/abajo, izquierda/centro/derecha
- Formato: "Página 1 de 20", "1", "- 1 -"
- Número de inicio
- Páginas a excluir (ej: tapa, índice)

**Impacto:** Útil para documentos formales que necesitan numeración antes de distribuir.

**Cómo:** PyMuPDF puede insertar texto en coordenadas específicas en cada página.

**Esfuerzo:** Medio.

---

### MEJ-08 — Comparar dos PDFs (diff visual)

**Qué es:** Subís dos versiones de un documento y el sistema genera un PDF que resalta las diferencias: texto agregado en verde, eliminado en rojo.

**Impacto:** Muy útil para revisar contratos, informes o manuales con cambios entre versiones.

**Cómo:** Extraer texto por página con posición (PyMuPDF), comparar (difflib), generar anotaciones de color sobre el documento base.

**Esfuerzo:** Medio-alto. La parte difícil es hacer la comparación posicional (que el texto resaltado aparezca en el lugar correcto de la página).

---

### MEJ-09 — PDF a Excel (XLSX)

**Qué es:** Similar a PDF a CSV pero generando directamente un archivo Excel con formato.

**Ventaja sobre CSV:** Múltiples tablas en distintas hojas del mismo archivo, formato de celda preservado, anchos de columna ajustados.

**Cómo:** `openpyxl` para generar el XLSX. La detección de tablas ya existe con `pdfplumber`.

**Esfuerzo:** Medio. La detección ya está. Solo hay que cambiar el formato de salida.

---

### MEJ-10 — Historial persistente por usuario/sesión

**Qué es:** Actualmente los trabajos se borran a las 4 horas. Un historial de las últimas N conversiones (nombre de archivo, tipo de conversión, fecha) que persiste más tiempo, aunque el archivo ya no esté disponible.

**Impacto:** El usuario puede saber "¿cuándo convertí ese informe?", "¿qué opciones usé la última vez?".

**Cómo:** Guardar en SQLite el registro de cada conversión con metadatos (sin el archivo). La UI muestra el historial al pie del index.

**Esfuerzo:** Medio. La BD ya está. Es agregar una tabla más y mostrar los datos.

---

## GRUPO 3 — Impacto específico, para casos de uso avanzados

Menos prioritarias pero útiles para usuarios técnicos o casos especiales.

---

### MEJ-11 — Convertir PDF a PDF/A (archivado)

**Qué es:** PDF/A es el estándar ISO para archivado a largo plazo. Algunos sistemas legales y gubernamentales lo requieren.

**Cómo:** Ghostscript puede hacer esta conversión. Requiere agregar Ghostscript al Dockerfile.

**Esfuerzo:** Medio. La herramienta existe, hay que integrarla.

---

### MEJ-12 — Extraer metadatos del PDF

**Qué es:** Mostrar y permitir editar los metadatos de un PDF: autor, título, tema, palabras clave, fecha de creación, programa que lo generó.

**Impacto:** Útil para documentación formal o cuando querés saber de dónde viene un PDF.

**Cómo:** `doc.metadata` en PyMuPDF. La edición también es directa.

**Esfuerzo:** Bajo-medio.

---

### MEJ-13 — Modo batch: procesar múltiples archivos a la vez

**Qué es:** Subir 10 PDFs y aplicarles el mismo proceso a todos (ej: comprimir todos, o convertir todos a TXT).

**Impacto:** Ahorra tiempo cuando hay muchos archivos del mismo tipo.

**Cómo:** El backend ya tiene cola de trabajos. Habría que agregar soporte para "trabajo batch" que encadena múltiples archivos con los mismos parámetros.

**Esfuerzo:** Medio-alto. Requiere cambios en la arquitectura de jobs y en la UI.

---

### MEJ-14 — Notificación cuando termina un proceso largo

**Qué es:** Para conversiones que tardan mucho (PDF grande a PNG a 600 DPI, por ejemplo), una notificación visual aunque el usuario cambie de pestaña.

**Opciones:**
- Notificación del navegador (Web Notifications API) — funciona si el usuario da permiso
- Badge en el tab del navegador (title tag dinámico: "✓ Listo — PDF-Export")
- Sonido corto de alerta

**Cómo:** JS puro. La Notifications API ya está soportada en todos los navegadores modernos.

**Esfuerzo:** Bajo. Es puramente frontend.

---

### MEJ-15 — Firma digital básica con imagen

**Qué es:** Insertar una imagen de firma (PNG con fondo transparente) en una posición específica del PDF, en la página y posición que el usuario elija.

**Impacto:** Útil para firmar documentos internos sin imprimirlos.

**Cómo:** PyMuPDF puede insertar imágenes en coordenadas precisas. La UI necesitaría permitir al usuario hacer clic en la miniatura de la página para posicionar la firma.

**Esfuerzo:** Medio. La parte más compleja es la UI de posicionamiento.

---

## Resumen por prioridad

| # | Mejora | Impacto | Esfuerzo | Prioridad |
|---|--------|---------|----------|-----------|
| MEJ-05 | Descarga directa sin ZIP (1 archivo) | Alto | Bajo | ⭐⭐⭐⭐⭐ |
| MEJ-01 | OCR para PDFs escaneados | Muy alto | Medio | ⭐⭐⭐⭐⭐ |
| MEJ-02 | Contraseña al PDF de salida | Alto | Bajo | ⭐⭐⭐⭐ |
| MEJ-03 | Vista previa del resultado | Alto | Bajo | ⭐⭐⭐⭐ |
| MEJ-04 | Eliminar páginas en blanco | Medio | Bajo | ⭐⭐⭐⭐ |
| MEJ-14 | Notificación al terminar | Medio | Bajo | ⭐⭐⭐⭐ |
| MEJ-06 | Marca de agua | Alto | Medio | ⭐⭐⭐⭐ |
| MEJ-07 | Numerar páginas | Medio | Medio | ⭐⭐⭐ |
| MEJ-09 | PDF a Excel (XLSX) | Medio | Medio | ⭐⭐⭐ |
| MEJ-12 | Editar metadatos del PDF | Medio | Bajo-medio | ⭐⭐⭐ |
| MEJ-10 | Historial persistente | Medio | Medio | ⭐⭐⭐ |
| MEJ-15 | Firma digital con imagen | Medio | Medio | ⭐⭐⭐ |
| MEJ-08 | Comparar dos PDFs (diff) | Alto | Alto | ⭐⭐ |
| MEJ-11 | PDF a PDF/A | Específico | Medio | ⭐⭐ |
| MEJ-13 | Batch (múltiples archivos) | Medio | Alto | ⭐⭐ |

---

## Mi recomendación de orden de implementación

Si tuviese que elegir las próximas 5 cosas a implementar, en este orden:

1. **MEJ-05** — Descarga directa sin ZIP: una línea de backend y el usuario lo nota inmediatamente. Muy fácil, muy visible.
2. **MEJ-14** — Notificación al terminar: solo JS, no toca el backend. El usuario puede irse a otra pestaña sin perder el resultado.
3. **MEJ-04** — Eliminar páginas en blanco: muy pedido, muy simple, se integra en servicios existentes.
4. **MEJ-02** — Contraseña al PDF de salida: PyMuPDF lo soporta nativamente, UI simple, agrega valor corporativo real.
5. **MEJ-01** — OCR: el salto cualitativo más grande. PDFs escaneados son la mitad de los documentos de una oficina.
