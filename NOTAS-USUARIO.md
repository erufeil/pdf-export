# NOTAS-USUARIO.md
## Comunicación directa de la IA al dueño del proyecto

> Este archivo es para vos, no para el programador.
> Aquí registro decisiones, advertencias, recomendaciones y el estado actual
> en lenguaje claro, sin jerga técnica innecesaria.
> La IA lo actualiza al final de cada sesión productiva.

---

## ESTADO ACTUAL DEL PROYECTO

**Última actualización:** 27/02/2026

### Etapas implementadas y funcionando

| # | Servicio | Página | Estado |
|---|---------|--------|--------|
| 1 | Landing page + estructura base | `index.html` | ✅ Completo |
| 2 | Cortar PDF | `pdf-split.html` | ✅ Completo |
| 3 | PDF a TXT | `pdf-to-txt.html` | ✅ Completo |
| 4 | PDF a DOCX | `pdf-to-docx.html` | ✅ Completo |
| 5 | PDF a PNG | `pdf-to-png.html` | ✅ Completo |
| 6 | PDF a JPG | `pdf-to-jpg.html` | ✅ Completo |
| 7 | Comprimir PDF | `pdf-compress.html` | ✅ Completo |
| 8 | Extraer imágenes | `pdf-extract-images.html` | ✅ Completo |
| 9 | Rotar páginas | `pdf-rotate.html` | ✅ Completo |
| 10 | HTML a PDF | `html-to-pdf.html` | ✅ Completo |
| 11 | Unir PDFs | `pdf-merge.html` | ✅ Completo |
| 12 | Extraer páginas específicas | `pdf-extract-pages.html` | ✅ Completo |
| 13 | Reordenar páginas | `pdf-reorder.html` | ✅ Completo |
| 14 | Migrar SQL (NDM2) | `ndm-to-tables-seq.html` | ✅ Completo |
| 15 | PDF a CSV (tablas) | `pdf-to-csv.html` | ⏳ Pendiente |
| 16 | Web Scraper de contenido | `web-scraper.html` | ⚠️ Ver advertencias |
| 17 | Imágenes a PDF | `img-to-1pdf.html` | ⏳ Pendiente |

---

## ADVERTENCIAS ACTIVAS

Cosas que requieren tu atención o que pueden sorprenderte al usar el sistema.

---

### ⚠️ ADV-001 — Viñetas en Web Scraper (Etapa 16)
**Qué pasa:** En algunos sitios web, los ítems de listas con viñetas (`•`) aparecen
en el resultado pero sin el título de la viñeta. La explicación está pero el título
que la precede falta.

**Cuándo ocurre:** Solo en ciertos sitios. Depende de cómo trafilatura (la librería
de extracción) procesa ese sitio en particular.

**Estado:** Se intentaron tres correcciones diferentes. La última (carácter guardián)
está en el código pero no fue confirmada por el usuario. **Necesita prueba real.**

**Qué hacer:** Probá el scraper en una página con listas de viñetas y fijate si
aparecen los títulos. Si no, avisame y continuamos investigando.

---

### ⚠️ ADV-002 — Log de debug en Web Scraper
**Qué pasa:** Hay una línea de log temporaria en `services/web_scraper.py` que
imprime los primeros 800 caracteres del contenido crudo de trafilatura. Sirve para
depurar el bug de viñetas (ADV-001).

**Impacto:** Llena los logs del servidor con texto. En producción es ruido.

**Cuándo remover:** Cuando se confirme que las viñetas funcionan correctamente.
Pedirme que lo quite en esa sesión.

---

### ⚠️ ADV-003 — CLAUDE.md necesita una adición
**Qué pasa:** Se crearon dos archivos nuevos (`CLAUDE-CODE.md` y `CLAUDE-VAR.md`)
para mejorar mi rendimiento entre sesiones. Pero CLAUDE.md aún no tiene la
instrucción de leerlos al inicio de cada sesión.

**Impacto:** Si no está la instrucción, voy a seguir cometiendo los mismos errores
de sesiones anteriores (nombres de campos, firmas de funciones, etc.).

**Qué hacer vos:** Agregar al final de `CLAUDE.md`:
```
## Inicio de sesión obligatorio
Al comenzar, leer SIEMPRE antes de escribir código:
1. CLAUDE-CODE.md
2. CLAUDE-VAR.md
```

---

## DECISIONES TOMADAS

Registro de decisiones que tomamos durante el desarrollo. Útil si alguien pregunta
"por qué está hecho así".

| Fecha | Decisión | Motivo |
|-------|---------|--------|
| 27/02/2026 | Drag & drop de páginas en Reordenar con API nativa del navegador, sin librerías JS | Cumplir la regla de "sin frameworks JS". La API Drag & Drop de HTML5 es suficiente para este caso. |
| 27/02/2026 | Creados `CLAUDE-CODE.md` y `CLAUDE-VAR.md` en la raíz del proyecto | Tres bugs de la sesión tuvieron la misma causa: la IA asumió valores sin verificarlos. Estos archivos eliminan esa necesidad. |
| 27/02/2026 | Sistema de contexto IA documentado en `ContextIA/SISTEMA-CONTEXTO-IA.md` | Para que proyectos futuros arranquen con mejor organización de información. |
| Sesión anterior | Opción "Sin enlaces" en Web Scraper elimina `[texto](url)` → `texto` y `[[3]](url)` → nada | Pedido explícito para lectura sin interrupciones en el resultado del scraper. |
| Sesión anterior | Guardian character `\x02` en procesamiento Markdown del Scraper | Protege los marcadores de lista (`* item`) de ser colapsados por el pipeline de limpieza de párrafos. |

---

## RECOMENDACIONES FUTURAS

Cosas que no son urgentes pero conviene tener en cuenta.

---

### REC-001 — Sesiones más cortas, una feature por vez
**Por qué:** A medida que la conversación crece, los detalles finos se comprimen y
pierdo precisión. Las sesiones donde implementé 1-2 features con las herramientas
correctas (CLAUDE-CODE.md, CLAUDE-VAR.md) tuvieron cero bugs de "nombre de campo
incorrecto". Las sesiones largas tuvieron más errores tontos.

**Sugerencia:** Empezar nueva conversación para cada etapa nueva. Mencionar al inicio
"implementar Etapa X" para que lea los archivos de contexto correctos.

---

### REC-002 — Mantener CLAUDE-CODE.md cuando cambien patrones
**Por qué:** Si en el futuro cambiás la firma de `respuesta_exitosa` o el nombre
del campo de upload, actualizá `CLAUDE-CODE.md` en la misma sesión. Si no, en la
próxima sesión voy a usar el valor viejo que tengo documentado.

**Cómo:** Decirme "actualizá CLAUDE-CODE.md con este cambio" al final de la sesión.

---

### REC-003 — Etapa 15 (PDF a CSV) requiere una librería nueva
**Por qué:** `pdfplumber` no está en `requirements.txt` todavía. Al implementar
la Etapa 15, antes de escribir código, hay que agregar `pdfplumber` al requirements
y reconstruir la imagen Docker.

**Impacto:** Primer deploy con Etapa 15 va a requerir `docker build`, no solo
`git pull + restart`.

---

### REC-004 — Revisar comportamiento de reordenamiento con PDF muy grandes
**Por qué:** El servicio de reordenar carga todas las páginas en memoria. Para
documentos de 300+ páginas con imágenes pesadas, esto puede ser lento o consumir
mucha RAM.

**Cuándo preocuparse:** Si los usuarios empiezan a reportar lentitud o errores de
memoria en PDFs grandes con imágenes. Por ahora no es prioridad.

---

### REC-005 — El Web Scraper no funciona con páginas que requieren JavaScript
**Por qué:** La librería `trafilatura` descarga el HTML estático. Sitios que cargan
contenido dinámicamente con React/Vue/Angular devuelven páginas casi vacías.

**Alternativa futura:** Si necesitás scraping de sitios dinámicos, habría que agregar
`playwright` o `selenium`. Es un cambio significativo. Por ahora el scraper sirve
para artículos, noticias y documentación (que generalmente son estáticos).

---

## ACLARACIONES SOBRE EL CÓDIGO

Explicaciones de partes del código que pueden parecer raras o arbitrarias.

---

### ACL-001 — ¿Por qué hay un carácter invisible en el Web Scraper?

En `services/web_scraper.py` vas a ver el carácter `\x02` (STX, un carácter de
control invisible). No es un error tipográfico.

**Para qué sirve:** El pipeline de limpieza de Markdown tiene una regla que junta
líneas separadas por doble salto. Eso es necesario para los párrafos normales, pero
rompe las listas con viñetas. El `\x02` se inserta **antes** de cada ítem de lista
para "protegerlo" de esa regla, y luego se elimina al final. Es un marcador temporal
que no aparece en el resultado final.

---

### ACL-002 — ¿Por qué el campo del formulario de upload se llama 'archivo' y no 'file'?

Porque el proyecto usa nombres en español para todo. El endpoint de upload en
`api/routes_files.py` lee `request.files['archivo']`. Si el frontend envía el
campo con cualquier otro nombre (`'file'`, `'pdf'`, `'document'`), el backend
devuelve error 400. Este fue uno de los bugs de la sesión del 27/02/2026.
Está documentado en `CLAUDE-CODE.md` para evitar que se repita.

---

### ACL-003 — ¿Por qué `respuesta_exitosa()` siempre devuelve HTTP 200?

Por diseño del proyecto. El código HTTP indica si la *comunicación* fue exitosa.
El campo `success: true/false` del JSON indica si la *operación* fue exitosa.
Intentar pasar un tercer parámetro `202` a esa función causa un `TypeError` interno
que Flask convierte en una página HTML de error (y el frontend no puede parsearla).
Este fue otro bug de la sesión del 27/02/2026.

---

## HISTORIAL DE BUGS RESUELTOS

Para referencia futura. Si algo vuelve a fallar, buscar acá primero.

| Fecha | Bug | Causa | Solución |
|-------|-----|-------|---------|
| 27/02/2026 | "No se envió ningún archivo" en Reordenar | `formData.append('file', ...)` en lugar de `'archivo'` | Corregido el nombre del campo en `pdf-reorder.html` |
| 27/02/2026 | "JSON.parse: unexpected character" al aplicar reordenamiento | `respuesta_exitosa(data, msg, 202)` — 3 parámetros cuando acepta 2 | Eliminado el tercer parámetro en `routes_convert.py` |
| 27/02/2026 | "No hace nada" después de subir archivo en Reordenar | `resp.data.archivo` no existe; los datos están en `resp.data` directamente | Corregido acceso en `pdf-reorder.html` |
| Sesión anterior | Saltos de línea forzados en Web Scraper al eliminar referencias `[N]` | El paso de limpieza de referencias dejaba espacios vacíos que se convertían en saltos | Agregados pasos de limpieza de espacios y colapso de líneas vacías múltiples |
| Sesión anterior | Viñetas desaparecen en output Markdown | El regex de unión de párrafos colapsaba los marcadores `* item` | Implementado guardian character `\x02` (ver ADV-001) |
