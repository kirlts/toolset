# Typst PDF — Escaping Pitfalls & Pattern

## Problemas encontrados con deepseek-v4-flash output → Typst

### 1. Caracteres que Typst interpreta como sintaxis

| Carácter | Problema | Escapado |
|----------|----------|----------|
| `*` | Énfasis itálico/bold | `\*` |
| `_` | Énfasis itálico | `\_` |
| `` ` `` | Código inline | `` \` `` |
| `<` `>` | Label/etiqueta | `\<` `\>` |
| `@` | Reference/referencia | `\@` |
| `#` | Variable/función | `\#` |
| `$` | Math mode | `\$` |
| `{` `}` | Block/scope | `\{` `\}` |
| `~` | Non-breaking space | `\~` |
| `\` | Escape | `\\` |

### 2. Orden de escapado (CRÍTICO)

El orden determina si el PDF compila o no. **Siempre:**

1. **PRIMERO:** Procesar estructura (links, code spans)
2. **LUEGO:** Escapar caracteres especiales

Si se escapa `\` primero, luego las regex de enlaces y código no matchean porque los backslashes duplicados rompen los patrones.

```python
# 1. Links primero
text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'#link("\2")[\1]', text)

# 2. Código inline (antes de escapar backticks)
text = re.sub(r'`([^`]+)`', r'#raw(\1)', text)

# 3. Escapar caracteres especiales (ÚLTIMO)
text = text.replace("\\", "\\\\")
text = text.replace("#", "\\#")
text = text.replace("@", "\\@")
# ... resto
text = text.replace("`", "\\`")
```

### 3. `_escape_typst` vs `_inline_typst`

| Función | Usada para | Procesa code inline? | Escapa @? |
|---------|-----------|----------------------|-----------|
| `_escape_typst()` | Headings, list items | ❌ No | ❌ No (verificar) |
| `_inline_typst()` | Paragraphs (líneas sueltas) | ✅ Sí | ✅ Sí |

**⚠️ Pitfall:** Si un list item contiene `` `@Hermes` ``, pasa por `_escape_typst` que NO procesa code spans. El `@` queda sin escapar → Typst error `label <Hermes>`. Solución: escapar `@` también en `_escape_typst`.

### 4. Errores comunes de Typst

| Error | Causa | Solución |
|-------|-------|----------|
| `unclosed delimiter` | `_` o `*` sin cerrar en el texto | Escapar `_` y `*` antes de pasarlos a Typst |
| `label <...> does not exist` | `@Hermes` o `@usuario` interpretado como reference | Escapar `@` como `\@` |
| `unknown variable: ResearchIt` | `#smallcaps(ResearchIt)` sin comillas | Usar `#smallcaps("ResearchIt")` |
| `unknown font family` | Fuente no instalada | Usar `typst fonts` para listar fuentes disponibles |

### 5. Fuentes disponibles en ARM64/OL9

```
Cantarell
DejaVu Sans
DejaVu Sans Mono
Libertinus Serif
New Computer Modern
Source Code Pro
```

Usar `DejaVu Sans` para mejor legibilidad en móvil. `Libertinus Serif` alternativa profesional.
