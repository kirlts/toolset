---
name: pdf-mobile-friendly
description: Generar PDFs mobile-friendly desde Markdown usando WeasyPrint + CSS
---

# PDF Mobile-Friendly

Genera PDFs legibles en móvil con formato profesional. Usa WeasyPrint + CSS, no pandoc+typst.

## Requisitos

```bash
pip3 install weasyprint markdown
```

Tipografías: DejaVu Sans + DejaVu Sans Mono (vienen con OL9, si no: `sudo dnf install dejavu-sans-fonts dejavu-sans-mono-fonts`)

## Uso

```python
import weasyprint

# 1. Convertir MD a HTML con pandoc
#    pandoc entrada.md -o entrada.html

# 2. Envolver con CSS + portada
# 3. Generar PDF
doc = weasyprint.HTML(string=html_con_css)
doc.write_pdf("salida.pdf")
```

## CSS Template Base

Usar:
- DejaVu Sans 10.5pt, interlineado 1.6, texto justificado
- A4, márgenes 1.6cm
- h1: 18pt azul oscuro (#1a365d), bordes, page-break
- h2: 14pt azul (#2b6cb0)
- Tablas: header azul (#2b6cb0) con texto blanco, filas alternadas
- Código: DejaVu Sans Mono 8.5pt, fondo gris claro (#edf2f7)
- Blockquote: borde izquierdo azul, fondo azul claro (#ebf8ff)
- Portada: centrada, título grande (24pt), línea decorativa
- Números de página al pie
- Severity badges: critical (#e53e3e), high (#dd6b20), medium (#d69e2e), low (#718096)

## Script Canónico

`scripts/generate-pdf.py` — script autónomo para generar PDFs mobile-friendly.

```bash
python3 scripts/generate-pdf.py entrada.md salida.pdf "Título del Documento"
```

Requiere: `pip3 install weasyprint markdown`, `pandoc` en PATH.

## Casos de Uso

- Informes de diagnóstico (validado 25-jun-2026)
- Reportes de investigación (ResearchIt)
- Documentación de proyectos
- Cualquier artefacto que el usuario pida en PDF legible en móvil
