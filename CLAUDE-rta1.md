# CLAUDE-rta1.md — Análisis: MarkItDown vs PDFexport

> Repositorio analizado: `D:\Github\TMP Borrable\markitdown`
> Autor: Microsoft — Proyecto de extracción a Markdown para LLMs
> Fecha análisis: 2026-06-29

---

## 1. RESUMEN EJECUTIVO

MarkItDown es un **pipeline de conversión multimodal** diseñado específicamente para preparar documentos
para consumo por LLMs. No es solo un extractor de texto: preserva estructura lógica (tablas, listas,
encabezados) convirtiéndolo todo a Markdown. Sus PDF converters usan una estrategia híbrida
**pdfminer.six + pdfplumber** con múltiples fallbacks y soporte opcional de OCR via LLM Vision.

---

## 2. FORMATOS SOPORTADOS (19+ tipos)

| Categoría | Formatos |
|-----------|----------|
| Documentos | PDF, DOCX, PPTX, XLSX/XLS, EPUB, MSG (Outlook) |
| Web | HTML/XHTML, URLs arbitrarias, RSS, Wikipedia, YouTube |
| Imágenes | JPG, PNG (EXIF + LLM description) |
| Audio | WAV, MP3, MP4 (transcripción via SpeechRecognition) |
| Datos | CSV, JSON, XML, Jupyter Notebooks (IPYNB) |
| Comprimidos | ZIP (itera contenidos recursivamente) |
| Cloud (opcional) | Azure Document Intelligence, Azure Content Understanding |
| Plugin OCR | Añade OCR a PDF, DOCX, PPTX, XLSX via LLM Vision |

---

## 3. EXTRACCIÓN DE PDF — TÉCNICAS

### 3.1 Estrategia híbrida (archivo: `_pdf_converter.py`)

```
Fase 1 — pdfplumber (análisis estructural):
  Para cada página:
    → extract_words(x_tolerance=3, y_tolerance=3)
    → Detectar si la página tiene tablas (≥3 columnas, ≥20% filas alineadas)
    → Si tabla → formatear como Markdown pipe table
    → Si no tabla → extract_text() de pdfplumber

Fase 2 — decisión final:
  Si NINGUNA página tuvo tablas detectadas:
    → Descartar todo y usar pdfminer.high_level.extract_text() en el documento completo
    → pdfminer produce mejor espaciado para texto corrido (prosa)
  Si alguna página tuvo tablas:
    → Usar resultado combinado de pdfplumber
```

### 3.2 Detección de tablas (`_extract_form_content_from_words()`)

- Agrupa palabras extraídas por posición Y → filas
- Detecta columnas por alineación X con **tolerancia adaptativa** (percentil 70 de gaps)
- Criterios de validación:
  - ≥ 3 columnas, ≤ 10 columnas
  - densidad < 10 columnas/pulgada (evita falsos positivos en layout multi-columna)
  - ≥ 20% de filas alineadas como tabla
  - ancho de contenido > 55% de página
- Genera Markdown pipe tables con separador `|---|---|`

### 3.3 Librerías PDF usadas

| Librería | Versión mínima | Rol |
|----------|---------------|-----|
| **pdfminer.six** | ≥ 20251230 | Extracción de texto con buen espaciado |
| **pdfplumber** | ≥ 0.11.9 | Análisis estructural, extracción de tablas |
| **PyMuPDF** | ≥ 1.24.0 | Solo en plugin OCR, como fallback de último recurso |

### 3.4 OCR para PDFs escaneados (plugin `markitdown-ocr`)

```
Archivo: markitdown-ocr/_pdf_converter_with_ocr.py

Para cada página:
  1. Extrae imágenes incrustadas via pdfplumber.page.images
  2. Para cada imagen:
     a) Obtiene stream directo (.get_data())
     b) Fallback: renderiza región a 150 DPI
     c) Envía a LLM Vision (cualquier cliente OpenAI-compatible)
  3. Intercala texto e imágenes por posición Y (top-to-bottom)
  4. Marca con *[Image OCR]...[End OCR]*

Si el PDF está escaneado (texto vacío):
  → Renderiza TODAS las páginas a 300 DPI
  → OCR full-page via LLM Vision
```

---

## 4. QUÉ TIENE MEJOR QUE NUESTRO `page.get_text()`

| Aspecto | Nuestro PyMuPDF | MarkItDown |
|---------|----------------|------------|
| Texto plano | ✅ Rápido (0.6s/574 pág) | ✅ Similar |
| **Tablas formateadas** | ❌ Texto plano | ✅ Markdown pipe tables |
| **Preserva estructura lógica** | ❌ | ✅ (encabezados, listas, tablas) |
| **PDFs escaneados** | ❌ sin OCR | ✅ via plugin LLM Vision |
| **Imágenes incrustadas con OCR** | ❌ | ✅ plugin |
| Fallbacks encadenados | ❌ | ✅ pdfplumber → pdfminer → PyMuPDF |
| Output listo para LLMs | ❌ | ✅ (es el objetivo principal) |
| Transcripción de audio | ❌ | ✅ |
| Multiformat (19+ tipos) | ❌ solo PDF | ✅ |
| LLM Vision integration | ❌ | ✅ nativo |
| Gestión memoria por página | ❌ | ✅ `page.close()` explícito |

**Ventaja clave de MarkItDown:** detecta y convierte tablas automáticamente a Markdown.
Para texto corrido, `pdfminer.six` produce mejor espaciado inter-palabra que `fitz.get_text()`.

**Ventaja clave nuestra:** PyMuPDF es significativamente más rápido, permite recomprimir imágenes,
manipular el PDF en memoria, extraer hashes de fuentes, etc. MarkItDown es read-only.

---

## 5. INNOVACIONES TÉCNICAS RELEVANTES

### 5.1 Tolerancia adaptativa de columnas
En lugar de un valor fijo, calcula el percentil 70 de los gaps entre palabras de cada fila
para determinar la separación óptima de columnas. Esto funciona bien con tablas de distintas densidades.

### 5.2 Detección MasterFormat (listas vs tablas)
Detecta numeraciones parciales como `.1`, `.2`, `.10` al inicio de línea y las trata como
**ítems de lista**, no como filas de tabla. Post-procesamiento las reúne con el siguiente párrafo.

### 5.3 Sistema de plugins con prioridad
- Plugins se registran via `entry_points(group="markitdown.plugin")`
- Pueden asignarse prioridad negativa (-1.0) para reemplazar converters built-in sin tocar el core
- Plugin OCR se registra a -1.0 → ejecuta antes del converter PDF built-in

### 5.4 Fallbacks encadenados para PDFs
```
pdfplumber (estructura) → pdfminer (texto) → PyMuPDF (rendering) → string vacía
```
Cada fallback activa solo si el anterior falla o retorna vacío.

---

## 6. OPORTUNIDADES PARA NUESTRO PROYECTO

### Alta prioridad (fácil de implementar)

**A. Usar `pdfminer.six` para extracción de texto en lugar de/además de `page.get_text()`**
- `pdfminer.high_level.extract_text()` produce mejor espaciado inter-palabra en prosa
- Especialmente útil para `pdf_to_txt.py` (Etapa 3)
- Instalación: `pdfminer.six` ya está en nuestro stack

**B. Incorporar `pdfplumber` para detección básica de tablas en `pdf_to_csv.py`**
- pdfplumber ya está en nuestro stack
- `page.extract_table()` nativo detecta tablas simples sin implementar el algoritmo complejo
- Mejor fallback que nuestro pdfminer actual en pdfs con tablas

**C. Detección de "PDF escaneado" en metadatos**
- Si `page.get_text()` retorna cadena vacía o muy corta → el PDF probablemente es imagen
- Reportar en `/metadata/extract` como `pdf_escaneado: true`
- Útil para el usuario antes de intentar extraer texto

### Media prioridad (nueva funcionalidad)

**D. Nuevo servicio: PDF → Markdown (Etapa nueva)**
- Usar estrategia híbrida pdfminer+pdfplumber de MarkItDown
- Preservar tablas como pipe tables Markdown
- Output: `.md` directo (sin ZIP)
- Mucho más útil que PDF→TXT para uso con LLMs

**E. Transcripción de audio (si hay demanda)**
- SpeechRecognition ya es una dependencia de Python estándar
- Formatos: WAV, MP3

### Baja prioridad (requiere infraestructura)

**F. OCR via LLM Vision para PDFs escaneados**
- Requiere configurar cliente OpenAI/Azure o Ollama local
- Solo tiene sentido si el usuario tiene acceso a un LLM con vision

---

## 7. DEPENDENCIAS CLAVE DE MARKITDOWN

```toml
# Core (siempre)
beautifulsoup4, requests, markdownify, magika~=0.6.1
charset-normalizer, defusedxml

# PDF (opcional, lo que nos importa)
pdfminer.six>=20251230
pdfplumber>=0.11.9

# Office
mammoth~=1.11.0     # DOCX → HTML (mejor que python-docx para conversión)
python-pptx, pandas, openpyxl, xlrd

# Multimedia
pydub, SpeechRecognition, youtube-transcript-api

# Azure (opcional, billable)
azure-ai-documentintelligence, azure-ai-contentunderstanding
```

---

## 8. CONCLUSIÓN

MarkItDown no reemplaza nuestro stack — resuelve un problema diferente: convertir documentos
a Markdown estructurado para consumo por LLMs. Nosotros manipulamos PDFs (comprimir, rotar, extraer).

**Lo más valioso para incorporar:**
1. `pdfminer.six` como alternativa a `page.get_text()` en extracción de texto (mejor prosa)
2. `pdfplumber.page.extract_table()` para detección de tablas en `pdf_to_csv.py`
3. Detección de "PDF escaneado" (caracteres = 0) como dato forense en metadatos
4. Un servicio futuro PDF→Markdown usando la estrategia híbrida pdfminer+pdfplumber

El algoritmo de detección de tablas de MarkItDown (tolerancia adaptativa + criterios multi-condición)
es significativamente más sofisticado que lo que tenemos. Vale la pena revisarlo si implementamos
extracción estructurada de tablas.
