# Pandoc — Conversión Markdown a Typst en ResearchIt

## Instalación

```bash
curl -sL "https://github.com/jgm/pandoc/releases/download/3.6.4/pandoc-3.6.4-linux-arm64.tar.gz" -o /tmp/pandoc.tar.gz
tar xzf /tmp/pandoc.tar.gz -C /tmp
sudo mv /tmp/pandoc-3.6.4/bin/pandoc /usr/local/bin/
rm -rf /tmp/pandoc.tar.gz /tmp/pandoc-3.6.4
pandoc --version
```

## Uso en ResearchIt

```python
import subprocess
result = subprocess.run(
    ["pandoc", "-f", "markdown", "-t", "typst"],
    input=md_content,
    capture_output=True, text=True, timeout=60
)
typst_content = result.stdout
```

## Formatos convertidos

| Markdown | Typst output |
|----------|-------------|
| `**bold**` | `#strong[bold]` |
| `*italic*` | `#emph[italic]` |
| `` `code` `` | `` `code` `` (mismo syntax) |
| `[text](url)` | `#link("url")[text]` |
| `# Header` | `= Header` |
| `## Header` | `== Header` |
| `- list` | `- list` (mismo syntax) |
| `1. list` | `+ list` |

## Ventajas sobre converter manual

- Maneja correctamente casos borde: `SELECT * FROM`, `@usuario`, `#hashtag`, `_texto_`, backticks anidados
- No produce errores de "unclosed delimiter" en Typst
- No requiere mantenimiento de regex
- Tamaño: ~40MB ARM64

## Troubleshooting

- `pandoc: not found` → binario no instalado en `/usr/local/bin/`
- Conversión lenta → marcar `timeout` en subprocess (60s es suficiente)
- Output vacío → verificar que md_content no sea vacío
