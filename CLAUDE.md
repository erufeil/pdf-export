# PDFexport — instrucciones para Claude

## Orientación de sesión

Antes de escribir código, usar **graphify primero**:

- `graphify query "<pregunta>"` — subgrafo acotado (preferir sobre leer archivos)
- `graphify explain "<concepto>"` — patrones, funciones, flujos
- `graphify path "<A>" "<B>"` — relación entre dos símbolos

Solo recurrir a los diccionarios si graphify no alcanza:

- `CLAUDE-CODE.md` — heurísticas y decisiones de diseño no derivables del AST
- `CLAUDE-VAR.md` — contratos REST exactos cuando el endpoint no está claro en el grafo

## Diccionarios de contexto

| Archivo | Contenido | Cuándo usarlo |
|---------|-----------|---------------|
| `CLAUDE-CODE.md` | Patrones Python/JS verificados, job_manager, file_manager | Solo si graphify no responde |
| `CLAUDE-VAR.md` | SQLite schema, contratos REST, parámetros JSON exactos | Solo si graphify no responde |
| `CLAUDE-PLAN.md` | Specs completas de cada etapa (UI, lógica), tabla de etapas | Al implementar etapa nueva o revisar requisitos |
| `CLAUDE-rta1.md` | Propuestas de mejora priorizadas | Al planificar nuevas features |

---

## Objetivo General

Servicio de conversión de archivos PDF a distintos formatos y conversiones inversas.

## Stack

- Backend: Python 3.10 + Flask · SQLite3
- Frontend: HTML5 + CSS3 + JS Vanilla (sin frameworks, sin Node.js)
- Frontend servido desde Flask (mismo contenedor)

## Librerías clave

PyMuPDF · pdf2image+poppler · pdfminer.six · python-docx · weasyprint ·
pdfplumber · cairosvg · beautifulsoup4+lxml · trafilatura · markdownify ·
requests · Apache Tika (servicio externo, opcional)

## Reglas

- Código simple en español (variables, comentarios, mensajes de log)
- Sin over-engineering. Sin helpers para uso único. Sin validaciones redundantes.
- Validar solo en boundaries: input del usuario y APIs externas
- `index.html` en raíz del proyecto (carga en https://IP:PORT)
- Resto del frontend en `static/`
- Nunca escribir CLAUDE.md — proponer cambios para que el usuario los aplique
- Mantener README.md actualizado con instalación y uso

## Principios de naming de archivos de salida

- Individual: `{nombre_original} - {tipo} {N_padding}.{ext}`
- ZIP: `{trabajo_id}_{nombre_base}_{tipo}.zip`
- Sin ZIP (directo): compress, rotate, to-txt, to-docx, from-html, merge, img-to-1pdf, webp-to-png, svg-to-png, img-to-txt, eps-to-png, to-md, excel-to-md, epub-to-md
- Con ZIP: split, to-png, to-jpg, extract-images, to-csv, scrape-url, extract-pages(separados)

## System Prompt

Eres un asistente experto en desarrollo de sistemas web. Guíate por CLAUDE.md como fuente de verdad.

## Revisar al final

1. Revisar que nombres de funciones y variables existan en el resto del código
2. Verificar si hace falta actualizar ALLOWED_EXTENSIONS en config.py
3. Actualizar CLAUDE-CODE.md, CLAUDE-VAR.md si hay patrones/endpoints nuevos
4. Actualizar y detallar CLAUDE-PLAN.md
5. Actualizar README.md para programadores (deploy server y local)
6. Actualizar NOTAS-USUARIO.md para Help de Usuario final
7. Sumar 0.01 a VERSION en config.py
8. Correr `graphify update .` para mantener el grafo al día

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:

- **Primero siempre graphify** antes de abrir cualquier archivo fuente para orientación
- `graphify query "<pregunta>"` → subgrafo acotado; preferir sobre grep o lectura directa
- `graphify explain "<concepto>"` → flujo detallado de un símbolo o concepto
- `graphify path "<A>" "<B>"` → cómo se relacionan dos símbolos
- Si `graphify-out/wiki/index.md` existe, usarlo para navegación amplia
- Leer `graphify-out/GRAPH_REPORT.md` solo para revisión de arquitectura general
- Después de modificar código: `graphify update .` (AST-only, sin costo de API)
