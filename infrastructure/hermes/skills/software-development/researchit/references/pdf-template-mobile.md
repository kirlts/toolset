# PDF Template Mobile — ResearchIt

## Template: templates/report.typ

```typst
#set page(
  margin: (left: 1.4cm, right: 1.4cm, top: 1cm, bottom: 1.2cm),
  numbering: "1",
  header: context {
    if here().page() > 1 {
      align(right)[
        #text(size: 0.5em, fill: rgb("#94a3b8"))[#smallcaps("ResearchIt") #h(0.5em) #datetime.today().display()]
      ]
    }
  },
  footer: context {
    align(center + bottom)[
      #text(size: 0.45em, fill: rgb("#cbd5e1"))[ResearchIt — #here().page()]
    ]
  },
)

#set text(font: "DejaVu Sans", size: 10.5pt, lang: "es")
#set par(justify: true, leading: 0.6em)

#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  set block(inset: (top: 0.6em, bottom: 0.4em, left: 0.4em), fill: rgb("#1e3a5f"), radius: 4pt)
  set text(size: 15pt, weight: "bold", fill: white)
  set par(justify: false)
  v(0.5em); it; v(0.4em)
}
#show heading.where(level: 2): it => {
  set block(inset: (top: 0.3em, bottom: 0.2em, left: 0.3em), fill: rgb("#e8f0fe"), radius: 3pt)
  set text(size: 12pt, weight: "bold", fill: rgb("#1e3a5f"))
  set par(justify: false)
  v(0.5em); it; v(0.2em)
}
#show heading.where(level: 3): it => {
  set text(size: 10.5pt, weight: "bold", fill: rgb("#2d5a87"))
  set par(justify: false)
  v(0.4em); it; v(0.1em)
}
#show raw.where(block: true): it => {
  set block(fill: rgb("#f1f5f9"), inset: 6pt, radius: 4pt, width: 100%)
  set text(size: 7.5pt, fill: rgb("#334155"))
  it
}
#show link: it => text(fill: rgb("#2563eb"), it)
#show list: it => { set par(justify: false); it }
#show strong: it => text(weight: "bold", fill: rgb("#1e293b"), it)
```

## Key Decisions

| Decisión | Razón |
|----------|--------|
| DejaVu Sans | Única sans-serif disponible en ARM64/OL9 (Libertinus Serif también disponible) |
| Sin cmarker | No funciona en este entorno (error "expected expression" con #) |
| Escapado total de * y _ | Evita "unclosed delimiter" en Typst cuando el texto tiene _Palabra* |
| Márgenes 1.4cm | Optimizado para pantalla de teléfono (no para papel A4) |
| Justificado + leading 0.6em | Mejora legibilidad en pantalla sin perder espacio vertical |

## Available Fonts (ARM64/OL9)

- Cantarell
- DejaVu Sans
- DejaVu Sans Mono
- Libertinus Serif
- New Computer Modern
- New Computer Modern Math
- Source Code Pro

## Font size rationale

- 11pt body = ~60-65 chars/line at 1.4cm margins on a 6.1" phone → comfortable reading
- 17pt H1 = clear hierarchy without wasting screen
- 7.5pt code = compressed enough for code blocks on narrow screens
