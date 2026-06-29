# Diagnóstico: Falla de Ruteo Multi-Grupo en Hermes Agent

**Fecha:** 29 junio 2026
**Contexto:** Mensaje entrante en grupo WhatsApp "Personal" (120363429377303869@g.us)
**Síntoma:** El orquestador respondió como si fuera un DM, sin cargar contexto del perfil personal.

---

## 1. Anatomía del Error

### 1.1 Lo que DEBIÓ ocurrir (según SOUL.md §Ruteo Multi-Grupo)

```
1. Extraer chat_id del origen → 120363429377303869@g.us
2. No es DM (@lid / @s.whatsapp.net)
3. Buscar chat_id en whatsapp-groups.yaml:
   → Encontrado: name=Personal, profile=personal, repo=kirlts/personal
   → profile existe en `hermes profile list` → SÍ
   → Acción requerida:
     a. recall(bank=personal-profile, max_tokens=8192)
     b. recall(bank=<repo>, max_tokens=16384, budget="high")
     c. Leer ~/.hermes/profiles/personal/SOUL.md
4. Responder como orquestador con contexto cargado
```

### 1.2 Lo que REALMENTE ocurrió

```
1. Extraer chat_id → ok (pero no se usó para routing)
2. Ejecutar "Inicio de CADA sesion: recall(bank=hermes)" → ok
3. Mensaje casual → modo conversacional
4. Responder sin cargar perfil personal
```

## 2. Análisis de Causa Raíz (5 Capas)

### Capa 1: Síntoma inmediato
El mensaje se trató como DM en lugar de grupo con perfil.

### Capa 2: Instrucción omitida
El algoritmo de ruteo (SOUL.md líneas ~23-39) no se ejecutó. Se ejecutó solo la instrucción de init de sesión (línea ~14).

### Capa 3: Competencia de instrucciones en el prompt
El system prompt contiene dos instrucciones aplicables al inicio:

| Instrucción | Posición | Naturaleza |
|---|---|---|
| "Inicio de CADA sesion: recall(bank='hermes')" | Linea ~14 | Incondicional, simple, 1 paso |
| "Cuando recibis un mensaje de WhatsApp, ejecutá este algoritmo SIN EXCEPCION" | Linea ~23 | Condicional, complejo, multi-paso |

La instrucción #1 es simple y concreta → se ejecuta primero. La #2 requiere parsear el origen del mensaje, lookup en YAML, branching condicional → más costosa cognitivamente. Al terminar #1, el tono casual del mensaje activa modo conversacional y #2 nunca se ejecuta.

### Capa 4: Ausencia de enforced pre-conditions
El ruteo es **texto en lenguaje natural** dentro del system prompt. No hay:

- Un middleware que verifique el origen del mensaje antes de que llegue al LLM
- Una condición programática que fuerce la ejecución del algoritmo
- Un formato de salida estructurado que declare el routing antes de responder
- Un guard que rechace respuestas sin routing explícito

Cada paso del algoritmo (extraer chat_id, leer YAML, hacer recall, leer SOUL.md) es una decisión voluntaria del LLM. Cada paso es un punto de falla.

### Capa 5: El problema fundamental
**El ruteo es una decisión de sistema (determinista, programable) delegada a un LLM (probabilístico, interpretativo).**

El lookup de `chat_id → profile → banks` es un mapeo 1:1. Es una función pura: dado un JID, devuelve una tupla de (profile, banks, SOUL.md path). Esto debería ejecutarse en código, no en una red neuronal.

## 3. Línea de Base del Problema

```
Input: mensaje WhatsApp + chat_id + metadata
↓
[GAP] Aquí no hay enforcement. El LLM decide si rutea o no.
↓
Output: respuesta con o sin contexto de perfil
```

### ¿Por qué no basta con "aprender" la lección?

Los retains a Hindsight (hermes bank, personal-buffer) **persisten**, pero:

1. En la próxima sesión, el recall traerá el hecho "error de ruteo el 29/jun"
2. Ese hecho compite con todas las demás instrucciones del prompt
3. Sin un cambio estructural, el mismo patrón de falla puede repetirse

La memoria de Hindsight es texto adicional. No es enforcement.

## 4. Arquitectura Actual vs. Arquitectura Deseada

### Actual

```
Gateway → Session Init → LLM (decide ruteo) → Responde
```

El LLM tiene dos trabajos: (a) decidir el ruteo, (b) generar la respuesta.

### Deseada

```
Gateway → Pre-processor (resuelve ruteo en código) → LLM (solo responde con contexto inyectado)
```

El LLM tiene un solo trabajo: responder con el contexto que ya le dieron resuelto.

## 5. Posibles Soluciones

### A. Gateway Pre-processor (Recomendado)

Un script que se ejecuta antes de que el mensaje llegue al LLM:

```bash
#!/bin/bash
# ~/.hermes/scripts/pre-process-message.sh
# Input: JID del chat
# Output: Contexto a inyectar en system prompt

JID=$1
GROUP=$(grep -A3 "\"$JID\"" ~/.hermes/whatsapp-groups.yaml)

if echo "$GROUP" | grep -q "profile:"; then
  PROFILE=$(echo "$GROUP" | grep "profile:" | awk '{print $2}')
  echo "ROUTED_PROFILE=$PROFILE"
  echo "SOUL_MD=$(cat ~/.hermes/profiles/$PROFILE/SOUL.md)"
  # Opcional: hacer recall de banks via API
fi
```

**Implementación:** Hook en el gateway de Hermes que ejecuta este script pre-mensaje e inyecta el output como contexto de sistema adicional.

**Beneficio:** El ruteo ocurre en bash, no en el LLM. Determinista.

### B. Forced Structured Preamble (Parche textual)

Modificar SOUL.md para exigir un formato de salida estructurado al inicio de cada respuesta en grupos:

```
[ROUTING] profile=personal banks=[personal-profile,personal-buffer] soul=loaded
```

Sin esta línea, la respuesta es inválida. El formato es verificable por el usuario y por un eventual linter.

**Limitación:** Sigue siendo texto que el LLM debe recordar escribir.

### C. Reordenamiento del System Prompt (Mínimo)

Mover el algoritmo de ruteo al inicio absoluto del SOUL.md, ANTES de "Inicio de CADA sesion". Hacerlo el paso 0 obligatorio.

**Limitación:** Sigue siendo texto. Mejora la probabilidad pero no la garantiza.

## 6. Recomendación

**Gateway Pre-processor (A)** es la única solución que elimina la variable LLM del ruteo. Convierte una decisión probabilística en una función determinista.

**Forced Preamble (B)** como complemento: da visibilidad y auditabilidad.

**Reordenamiento (C)** como parche inmediato mientras se implementa A.
