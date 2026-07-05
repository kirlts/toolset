# Kilo CLI Recall Policy

## Hindsight Recall Budget (MANDATORY)

Toda llamada a `hindsight-selfhosted_recall()` DEBE especificar:

- `max_tokens`: maximo 4096 para contexto operativo, 1024 para startup de Kilo
- `budget`: "mid" o "low". NUNCA usar "high" como default.
- `query`: siempre especifico, nunca vacio.

Los recalls sin `max_tokens` ni `budget` estan PROHIBIDOS. Causan saturacion del context window (incidente documentado: 629,549 caracteres devueltos por un solo recall contra el banco toolset, causando hangs de 8+ minutos).

## Valores por Contexto

| Contexto | max_tokens | budget | Ejemplo |
|---|---|---|---|
| Kilo CLI startup | 1024 | low | `recall(query="ultimas decisiones, estado del proyecto", bank_id="<repo>-profile", max_tokens=1024, budget="low")` |
| Hermes profiles | 4096 | mid | `recall(bank_id="<profile>-profile", max_tokens=4096, budget="mid", query="contexto operativo reciente")` |
| Hermes orquestador | 4096 | mid | `recall(bank_id="hermes", max_tokens=4096, budget="mid", query="contexto reciente, decisiones")` |
| Chat profiles | 2048 | low | `recall(bank_id="chat-profile", max_tokens=2048, budget="low")` |
| Health checks | 8192 | mid | Lectura dedicada, mas permisiva |

## Bank Naming

- Patron: `<profile>-profile` (ej: `personal-profile`, `wwe-profile`, `toolset-profile`)

## Server-Side Enforcement

Los bancos Hindsight tienen `recall_max_tokens` configurado a nivel de servidor como safety net. Incluso si un recall no especifica parametros, el servidor limita la respuesta.
