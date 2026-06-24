---
name: markitdown-converter
description: "Convert supported document formats (PDF, DOCX, PPTX, XLSX, EPUB, HTML, CSV, JSON, XML, images, audio, ZIP) to Markdown using Microsoft MarkItDown before analysis. Saves tokens, avoids hallucinations, preserves structure."
version: 1.0.0
author: Hermes Agent + Microsoft MarkItDown
license: MIT
platforms: [linux, macos]
prerequisites:
  commands: [markitdown]
metadata:
  hermes:
    tags: [documents, conversion, markdown, pdf, docx, ppy, xlsx, token-efficiency]
    related_skills: [computer-use, vision_analyze]
    homepage: https://github.com/microsoft/markitdown
---

# MarkItDown Converter — Auto-convert documents to Markdown

## Purpose

When you receive a file in any supported format — via WhatsApp, WebUI, CLI, web download, or repo — convert it to Markdown **first** using `markitdown` before analyzing its content. This:

- Saves **tokens** (LLMs understand Markdown more efficiently than raw PDF/DOCX)
- Avoids **hallucinations** from structure guessing
- Preserves document **structure** (headings, lists, tables, links)
- Works across **all channels**: WhatsApp, WebUI, CLI, web, repos

## Supported File Extensions

| Format | Extensions |
|--------|-----------|
| PDF | `.pdf` |
| Word | `.docx` |
| PowerPoint | `.pptx` |
| Excel | `.xlsx`, `.xls` |
| HTML | `.html`, `.htm` |
| EPUB | `.epub` |
| CSV | `.csv` |
| JSON | `.json` |
| XML | `.xml` |
| Images | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.tiff`, `.webp` |
| Audio | `.wav`, `.mp3` (EXIF + transcription via speech recognition) |
| ZIP | `.zip` (iterates over contents) |
| YouTube | URLs |
| Outlook | `.msg` |

## CLI Usage

```bash
# Basic conversion — stdout
markitdown path/to/document.pdf

# Save to file
markitdown path/to/document.docx -o document.md

# Pipe from stdin
cat document.pptx | markitdown

# List available plugins
markitdown --list-plugins
```

## Python API (programmatic)

```python
from markitdown import MarkItDown
md = MarkItDown()
result = md.convert("path/to/file.pdf")
markdown_text = result.text_content
```

## Integration Points

### 1. Document from user (WhatsApp, WebUI, CLI)
When the user sends a file or provides a file path:
```bash
markitdown <file_path> 2>/dev/null
```
Read the output and analyze the Markdown instead of the raw file.

### 2. Document from web download (curl/wget)
After downloading a file from a URL:
```bash
curl -sL <url> -o /tmp/doc.pdf
markitdown /tmp/doc.pdf 2>/dev/null
```

### 3. Document from repo (local file)
```bash
markitdown path/to/repo/document.pdf 2>/dev/null
```

### 4. Document in Docker sandbox
Mount the Hermes venv or install markitdown in the sandbox:
```bash
docker run --rm -v /usr/local/lib/hermes-agent/venv:/venv:ro \
  -v /path/to/file.pdf:/doc.pdf \
  python:3.11 bash -c "pip install -q markitdown[all] && markitdown /doc.pdf"
```

## Rules

1. **ALWAYS convert first** — never pass raw PDF/DOCX/PPTX/XLSX/EPUB/HTML to LLM analysis
2. **Use the CLI** `markitdown <file>` — it's a single command, no complex setup
3. **Read the output** with `read_file` if the file is saved, or capture stdout
4. **Fallback**: If `markitdown` fails or returns empty, use `read_file` or `vision_analyze` as fallback and note the fallback
5. **Clean up**: Remove temp converted files after analysis

## Verification

After conversion, verify:
- Output is non-empty and looks like valid Markdown
- Document structure (headings, lists, tables) is preserved
- File size: markdown is typically 10-20% of original binary size
