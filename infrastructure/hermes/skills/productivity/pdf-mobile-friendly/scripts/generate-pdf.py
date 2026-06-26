#!/usr/bin/env python3
"""
Generate a mobile-friendly PDF from Markdown using WeasyPrint + CSS.
Usage: python3 generate-pdf.py <input.md> <output.pdf> [title]
Requires: pip3 install weasyprint markdown, pandoc in PATH
"""
import weasyprint, sys, os, subprocess, tempfile

MD_PATH = sys.argv[1]
PDF_PATH = sys.argv[2]
TITLE = sys.argv[3] if len(sys.argv) > 3 else "Documento"

# 1. Convert MD to HTML with pandoc
with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
    HTML_TMP = f.name

subprocess.run([
    "pandoc", MD_PATH, "-o", HTML_TMP,
    "--embed-resources", "--standalone",
], check=True)

with open(HTML_TMP) as f:
    html_content = f.read()
os.unlink(HTML_TMP)

# 2. Build CSS
CSS = f"""
@page {{
    size: A4; margin: 1.6cm 1.8cm;
    @bottom-center {{ content: counter(page); font-family: 'DejaVu Sans', sans-serif; font-size: 8pt; color: #666; }}
}}
body {{
    font-family: 'DejaVu Sans', sans-serif;
    font-size: 10.5pt; line-height: 1.6;
    color: #1a1a1a; text-align: justify; hyphens: auto;
}}
h1 {{ font-size: 18pt; font-weight: 700; color: #1a365d;
     margin-top: 1.5cm; margin-bottom: 0.3cm;
     page-break-before: always; border-bottom: 2px solid #2b6cb0;
     padding-bottom: 0.2cm; }}
h1:first-of-type {{ page-break-before: avoid; }}
h2 {{ font-size: 14pt; font-weight: 700; color: #2b6cb0;
     margin-top: 0.8cm; margin-bottom: 0.2cm; }}
h3 {{ font-size: 11.5pt; font-weight: 700; color: #2d3748;
     margin-top: 0.5cm; margin-bottom: 0.15cm; }}
p {{ margin: 0.2cm 0; orphans: 2; widows: 2; }}
strong {{ color: #1a365d; }}
code {{ font-family: 'DejaVu Sans Mono', monospace; font-size: 8.5pt;
       background: #edf2f7; padding: 0.05cm 0.15cm; border-radius: 0.1cm; }}
pre {{ background: #f7fafc; border: 1px solid #e2e8f0;
      border-left: 3px solid #2b6cb0; padding: 0.3cm 0.4cm;
      font-family: 'DejaVu Sans Mono', monospace; font-size: 8pt;
      line-height: 1.3; white-space: pre-wrap; word-break: break-all; }}
pre code {{ background: none; padding: 0; }}
ul, ol {{ margin: 0.2cm 0; padding-left: 0.8cm; }}
li {{ margin: 0.1cm 0; }}
table {{ width: 100%; border-collapse: collapse; margin: 0.3cm 0; font-size: 9pt; }}
th {{ background: #2b6cb0; color: white; padding: 0.15cm 0.25cm; text-align: left; font-weight: 600; }}
td {{ padding: 0.12cm 0.25cm; border: 1px solid #e2e8f0; }}
tr:nth-child(even) {{ background: #f7fafc; }}
tr:nth-child(odd) {{ background: #ffffff; }}
blockquote {{ border-left: 3px solid #2b6cb0; margin: 0.3cm 0;
             padding: 0.15cm 0.4cm; background: #ebf8ff; font-style: italic; color: #2c5282; }}
hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 0.5cm 0; }}
"""

# 3. Cover page
COVER = f"""
<div style="text-align:center; padding-top:3cm;">
<h1 style="font-size:24pt; border:none; margin-bottom:0.5cm;">{TITLE}</h1>
<hr style="width:50%; margin:1cm auto; border-top:2px solid #2b6cb0;">
<div style="font-size:10pt; color:#718096; margin-top:2cm;">
<p><strong>Generado:</strong> {os.path.getmtime(MD_PATH)}</p>
</div></div>
<div style="page-break-before:always;"></div>
"""

FULL_HTML = f"""<!DOCTYPE html><html lang="es">
<head><meta charset="UTF-8"><style>{CSS}</style></head>
<body>{COVER}{html_content}</body></html>"""

# 4. Generate PDF
doc = weasyprint.HTML(string=FULL_HTML)
os.makedirs(os.path.dirname(PDF_PATH) or ".", exist_ok=True)
doc.write_pdf(PDF_PATH)

size = os.path.getsize(PDF_PATH)
print(f"PDF: {PDF_PATH} ({size//1024} KB)")
