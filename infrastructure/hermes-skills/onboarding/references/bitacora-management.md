# Bitácora Management

Reglas para interactuar con bitácoras de proyecto en Google Docs (doc tipo bullet journal).

## Append-Only Convention

Nunca modificar, reemplazar o eliminar entradas existentes a menos que el usuario lo ordene explícitamente ("borra X", "cambia Y por Z"). Siempre agregar al final del documento.

## Formato Visual

| Elemento | Formato | Ejemplo |
|---|---|---|
| Fecha | **Bold** | `**09 - 07**` |
| Estado PENDIENTE | **Bold** | `**PENDIENTE:**` |
| Labels/títulos | **Bold** | `*Stack*`, `*MVP Trazambiental*` |
| URLs | _Italic_ | `_https://ejemplo.cl_` |
| Separación entre entradas | 1 blank line | `\n\n` entre entries |

## Herramientas Google Docs

| Operación | Tool | Cuándo |
|---|---|---|
| Append con formato (bold, italic) | `GOOGLEDOCS_UPDATE_DOCUMENT_SECTION_MARKDOWN` | Contenido nuevo con bold/italic |
| Insertar texto plano al final | `GOOGLEDOCS_INSERT_TEXT_ACTION` con `append_to_end=true` | Corregir spacing, insertar newlines de separación |
| Borrar y reemplazar | `GOOGLEDOCS_DELETE_CONTENT_RANGE` + luego append | Solo cuando el usuario lo pide o se necesita corregir error |
| Leer estructura | `GOOGLEDOCS_GET_DOCUMENT_BY_ID` | Obtener índices UTF-16 exactos |
| Leer texto plano | `GOOGLEDOCS_GET_DOCUMENT_PLAINTEXT` | Vista rápida del contenido |

### Pitfalls Conocidos

1. **UPDATE_DOCUMENT_SECTION_MARKDOWN se come los `\n` iniciales** del `markdown_text`. No poner leading newlines. Si se necesita separación del entry anterior, insertarla con `GOOGLEDOCS_INSERT_TEXT_ACTION` (con `insertion_index` apuntando al final del doc) ANTES del markdown append.

2. **Saltos de línea literales vs escapes**: En `UPDATE_DOCUMENT_SECTION_MARKDOWN`, usar saltos de línea reales (multiline string), NO `\n` escapes. El tool trata `\n` como texto literal y los inserta como "backslash-n" en el doc.

3. **DELETE_CONTENT_RANGE**: No incluir el último newline del segmento (endIndex = document_end - 1). Google Docs no permite borrar el trailing newline del body.

4. **Fechas duplicadas**: Cada fecha debe aparecer UNA SOLA VEZ en la bitácora. Todas las entradas de un mismo día van bajo la misma fecha. Si se agrega una entrada para un día que ya tiene fecha, no duplicar el encabezado.

## Criterio para Pendientes (PENDIENTE:)

Los pendientes que entran a la bitácora deben cumplir:

1. **Nivel equipo, sin dueño** — no asignar responsables. Decir qué hay que hacer, no quién lo hace.
2. **Estratégicos, no operativos** — si es un paso técnico que igual va a pasar durante la ejecución normal, no entra. Ej: "habilitar X en la config" no entra; "evaluar plataforma de hosting" sí entra.
3. **Con propósito explícito** — cada pendiente debe responder "para qué". Ej: "Revisar documentación antigua de Opentech, **clasificando su utilidad contra la estrategia actual para el MVP**".
4. **Generalizados** — dejar espacio a alternativas ("Infisical **o equivalente**", "evaluar Vercel **si** ...").
5. **Filtrar ruido** — lo que el usuario no dijo explícitamente pero está implícito en la conversación puede ser candidato; presentarlo como sugerencia, no grabarlo directo.

## Flujo Típico

1. Usuario pide agregar algo a la bitácora, o hay información que califica (decisiones, hitos, pendientes).
2. Si es agregar pendientes desde transcripciones de reuniones:
   a. Leer transcripciones de Google Drive (`drive-transcripciones-online` o `drive-transcripciones-presencial`).
   b. Extraer todos los posibles pendientes con LLM.
   c. Aplicar el criterio de pendientes (arriba).
   d. Presentar al usuario como bullet list para que seleccione.
   e. Agregar solo lo que el usuario confirma.
3. Si es agregar un hito/decisión directa:
   a. Leer el doc para conocer el último estado y fecha.
   b. Si la fecha ya existe, usar formato sin duplicar.
   c. Append con UPDATE_DOCUMENT_SECTION_MARKDOWN usando saltos de línea reales.
   d. Si necesita separación, INSERT_TEXT_ACTION primero con `\n\n`.
4. Confirmar al usuario el cambio.

## Caso: Perfil con Banco Único

Cada perfil usa UN SOLO bank Hindsight: `<profile>-profile`. No usar el bank `hermes` desde un perfil worker. El bank `hermes` es exclusivo del orquestador default.
