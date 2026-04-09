## Inicio de sesión obligatorio
Leer SIEMPRE antes de escribir código:
- `CLAUDE-CODE.md` — firmas, patrones Python/JS, procesadores registrados
- `CLAUDE-VAR.md` — esquema BD, contratos REST, parámetros exactos por endpoint

## Diccionarios de contexto
| Archivo | Contenido | Cuándo usarlo |
|---------|-----------|---------------|
| `CLAUDE-CODE.md` | Patrones Python/JS verificados, job_manager, file_manager, nuevo servicio | Siempre al codificar |
| `CLAUDE-VAR.md` | SQLite schema, contratos REST, parámetros JSON exactos, config.py | Siempre al codificar |
| `CLAUDE-PLAN.md` | Specs completas de cada etapa (UI, lógica), arquitectura, tabla de etapas | Al implementar etapa nueva o revisar requisitos |
| `Rta1.md` | Propuestas de mejora priorizadas (MEJ-01 a MEJ-15) | Al planificar nuevas features |

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
Regla completa en `CLAUDE-CODE.md §10`. Resumen:
- Individual: `{nombre_original} - {tipo} {N_padding}.{ext}`
- ZIP: `{trabajo_id}_{nombre_base}_{tipo}.zip`
- Sin ZIP (archivo directo): webp-to-png, svg-to-png, img-to-txt, img-to-1pdf

## System Prompt
Eres un asistente experto en desarrollo de sistemas web. Guíate por CLAUDE.md
como fuente de verdad.

## Revisar al final
1. Verificar si hace falta actualizar ALLOWED_EXTENSIONS
2. Actualizar CLAUDE-CODE.md, CLAUDE-VAR.md
3. Actualizar y detallar CLAUDE-PLAN.md para que quede bien completo
4. Actualizar README.md para programadores (deploy server y local)
5. Actualizar NOTAS-USUARIO.md para Help de Usuario final que no sabe de programacion.