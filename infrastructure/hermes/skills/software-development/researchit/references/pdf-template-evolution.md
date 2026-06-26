# PDF Template Evolution

## V1.0 — Initial (24 Jun 2026)
- cmarker-based rendering (fragile)
- DejaVu Sans 10.5pt, 1.4cm margins, leading 0.6em
- Failed on unclosed delimiters, `@` references, backtick nesting
- Raw bytes: ~76KB for ballenas report

## V1.1 — Escapado seguro (24 Jun 2026)
- Removed cmarker, added _escape_typst() and _md_to_typst()
- Escaped everything: `*`, `_`, `` ` ``, `<`, `>`, `@`
- Result: markdown SIN renderizar (asteriscos literales en el PDF)
- Raw bytes: ~145KB for Hermes report

## V1.2 — Markdown conversion with temp markers (24-25 Jun 2026)
- Temp markers (\x00B, \x00I, \x00C) to avoid re-matching
- Backtick code handled AFTER escaping
- Still fragile: SQL `SELECT * FROM` broke Typst parsing
- Still had unclosed delimiter errors
- Raw bytes: ~161KB

## V1.3 — Pandoc integration (25 Jun 2026)
- `_md_to_typst()` replaced with `subprocess.run(["pandoc", "-f", "markdown", "-t", "typst"], input=md)`
- Pandoc 3.6.4 installed at `/usr/local/bin/pandoc`
- Converts correctly: `**bold**` → `#strong[bold]`, `*italic*` → `#emph[italic]`, `` `code` `` → `` `code` ``, `[link](url)` → `#link("url")[link]`
- Handles `SELECT * FROM`, `@Hermes`, nested backticks, `#hashtags` without issues
- Post-processing: `#horizontalrule` → `#line()` (Pandoc outputs non-existent Typst function)
- NO more fragile regex converters
- NO more `_inline_typst()`, `_escape_typst()` functions
- Template: DejaVu Sans 15pt, page breaks for H1/H2/H3, cover page with prompt
- Raw bytes: ~224KB for Hermes report with cover page

## Key Lessons
1. Regex-based MD→Typst conversion is fragile and breaks on edge cases
2. Pandoc is the RIGHT tool for this conversion
3. The template can use Pandoc's output format directly (no need to modify Pandoc's Typst output except #horizontalrule)
4. Cover page with prompt makes the PDF self-documenting
5. Page breaks per section dramatically improve readability on mobile
