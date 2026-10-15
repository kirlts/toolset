# Punto de entrada común para el feedback

Análisis del 2026-10-15 de la nota «Idea QA» que Martín dibujó en Saber a las 00:26. El dibujo es
la especificación; este texto lo lee elemento por elemento y lo contrasta con lo que ya existe en
esta máquina. Donde el dibujo calla, hay una pregunta para Martín, no una decisión tomada.

![Idea QA, 2026-10-15](punto-de-entrada-feedback/Idea%20QA.png)

## Lo que dice el dibujo

Tres proyectos («Prod. 1», «Prod. 2», «Prod. 3»), cada uno con su propio QA. De cada QA sale una
flecha a una sola caja, y cada flecha lleva escrito su canal: «WhatsApp», «Gh Issues», «En
persona». La caja es un rectángulo con una fila de celdas arriba y un cuerpo abajo. De la caja
baja una sola flecha a un monito rotulado «Dev». Del Dev salen tres flechas directas a «QA 1»,
«QA 2» y «QA 3», sin pasar por la caja.

Seis decisiones de diseño están ya en esos trazos.

| Trazo | Decisión que fija |
|---|---|
| Un QA por proyecto, dibujado como persona | La fuente del feedback es una persona que prueba. Las alertas de máquina no están en el dibujo |
| El canal está escrito en la flecha, no en la caja | El canal es un atributo de cada entrada. La caja no sabe de WhatsApp ni de GitHub: recibe entradas ya convertidas |
| Una sola caja para los tres proyectos | Un solo lugar, no uno por repositorio. El proyecto es una columna, no una caja aparte |
| La caja tiene fila de celdas arriba y cuerpo abajo | Es una tabla con columnas fijas. No es un chat, no es un documento, no es una bandeja de mensajes |
| Una sola flecha de la caja al Dev | El Dev toma trabajo de la tabla y de ningún otro lado. Nunca va a buscar trabajo a WhatsApp |
| Las respuestas van del Dev a cada QA, sin volver por la caja | La respuesta viaja por el canal de cada QA. La tabla no es el medio de respuesta |

## Lo que ya existe y lo que falta

Medido hoy en esta máquina.

| Pieza del dibujo | Estado hoy | Dónde |
|---|---|---|
| Entradas de máquina a una tabla | Existe en dos proyectos: issues con etiqueta `alerta`, abiertas por guardias y Grafana. Un hook las inyecta en cada sesión de Claude Code | `alanberstein1/conversio-connect` (47 abiertas) y `kirlts/clara-ia` (2 abiertas) |
| Entradas de personas | No hay tabla. Llegan como archivo suelto o conversación | Devalis: `Errores funcionales 3.docx` del 2026-09-09, 12 puntos del cliente en Word. OKOS: Sentry y mensajes |
| Canal «Gh Issues» | Ya es una tabla por sí mismo, pero una por repositorio | Cada repo |
| Canal «WhatsApp» | Hay un receptor de WhatsApp medido y funcionando, dentro de la plataforma de Devalis | `~/devalis/plataforma/src/workers/baileys/` |
| Canal «En persona» | Llega como grabación de Plaud, nota de Saber o documento. Las dos primeras ya se leen desde una sesión | skills `plaud-transcripts` y `notas-saber` |
| El Dev que lee la tabla | Existe para las alertas: el hook de sesión. No existe para feedback de personas | `~/.claude/hooks/` (solo lectura desde el editor) |

Lo que falta es lo que el dibujo pone en el centro: la caja única, y las tres conversiones de
canal a fila.

## La caja, leída del dibujo

Una tabla con estas columnas. Son las que el dibujo exige para que la caja reciba de tres canales
distintos y el Dev devuelva a tres QA distintos.

| Columna | Por qué está |
|---|---|
| Proyecto | El dibujo tiene tres proyectos en una caja |
| QA | A quién vuelve la respuesta. Las tres flechas de salida van a personas con nombre |
| Canal | Está escrito en la flecha de entrada: WhatsApp, GitHub, en persona |
| Qué reportó | El contenido, en palabras del QA, sin reescribir |
| Evidencia | Captura, audio, enlace. Lo que el QA mostró |
| Estado | Nuevo, en curso, respondido. La fila cambia cuando el Dev responde |
| Respuesta | Qué se le dijo al QA y cuándo |

Dónde vive la tabla. El dibujo pide un solo lugar para los tres proyectos, y el Dev que ya lee
tablas en esta máquina lee issues de GitHub. La opción que cumple las dos cosas es un repositorio
único de feedback con una issue por fila y el proyecto como etiqueta. Una etiqueta `feedback` en
cada repositorio son tres cajas, y el dibujo tiene una.

## Las tres flechas de entrada

Cada canal se convierte en una fila con una herramienta propia. La caja no conoce el canal.

| Canal | Conversión | Qué ya hay |
|---|---|---|
| WhatsApp | Martín reenvía el mensaje del QA a un número receptor, o el QA escribe directo a ese número. Un modelo lee el mensaje y llena las columnas. Ningún `if` sobre el texto de la persona: en Devalis esa regla es la invariante XI | El receptor Baileys medido el 2026-08-26 |
| Gh Issues | La issue del repositorio del proyecto se refleja como fila en la caja, con enlace de vuelta. El QA sigue usando su repositorio | Issues por repositorio |
| En persona | Una sesión lee la grabación de Plaud, la nota de Saber o el documento, y crea una fila por punto reportado. El Word de Devalis tenía 12 puntos: 12 filas | `plaud-transcripts`, `notas-saber`, `pandoc` para Word |

## Las tres flechas de salida

El Dev responde a cada QA por el canal de ese QA: mensaje de WhatsApp, comentario en su issue, o
en la próxima reunión. La tabla registra la respuesta y cambia el estado. El dibujo no hace pasar
la respuesta por la caja, y por eso la caja no manda mensajes: los manda el Dev.

## Lo que el dibujo enseña sobre la caja que ya existe

La caja de alertas de OKOS muestra la falla que esta caja tiene que evitar. De las 47 abiertas
hoy, 41 dicen «batch merge queue: PR set aside, no author left to notify», y la misma PR aparece
hasta tres veces (#1197, #1198 y #1199 para la PR #1174). El hook que las inyecta termina diciendo
«si no, no hace falta actuar». Una tabla que el Dev aprende a ignorar deja de ser la única flecha
que entra al Dev.

Dos reglas salen de ahí. Una fila entra una sola vez por reporte: la llave es proyecto más
enlace o mensaje de origen. Y a esta caja entran solo personas, como en el dibujo: las máquinas ya
tienen la suya.

## Construido el 2026-10-15

| Pieza | Qué es | Comprobado |
|---|---|---|
| La caja | Repositorio privado [kirlts/feedback](https://github.com/kirlts/feedback). Una issue por fila; proyecto, canal y estado como etiquetas; QA, fecha, origen y evidencia en una tabla del cuerpo; la respuesta como comentario | 24 filas reales cargadas |
| `feedback nueva` | Una fila desde la terminal, con evidencia que se guarda en `evidencia/` del repositorio | Una fila de prueba creada y borrada |
| `feedback desde-docx` | Una fila por punto numerado de un Word, con sus imágenes | Los 24 puntos de Pablo (`Errores funcionales 3.docx`, 2026-09-09), 14 con imagen. Primera carga 1 min 20 s; segunda corrida 5 s y cero filas nuevas |
| `feedback desde-github` | Refleja las issues de un repositorio de proyecto, con enlace de vuelta | Una issue de prueba en `kirlts/HPOMEN`: reflejada, no duplicada en la segunda corrida, borrada |
| `feedback responder` | Guarda la respuesta, marca `estado:respondido`, cierra la issue y dice por qué canal y a quién enviarla | Sobre la fila de prueba |
| `feedback pendientes` y `feedback-para-claude.sh` | Las filas sin responder, en el formato que las sesiones ya reciben para las alertas | Salida de 24 líneas para Devalis, 0 para OKOS |

Lo que no se construyó. El receptor de WhatsApp: depende de la pregunta 2. El enganche del hook
en cada repositorio: los archivos de hooks solo los edita Martín (candado medido hoy: el shell y
la lectura del directorio quedan bloqueados). Para Devalis, una línea en la lista `SessionStart`
de los hooks del repositorio:

```
{"type": "command", "command": "~/toolset/tools/feedback-para-claude.sh devalis", "timeout": 10}
```

## Preguntas para Martín

El dibujo no contesta estas tres. Cada una cambia lo que se construye.

1. ¿Un repositorio único de feedback con el proyecto como etiqueta, o una etiqueta en cada
   repositorio? El dibujo tiene una caja; la primera opción es la fiel.
2. ¿El número de WhatsApp receptor es uno nuevo al que escriben los QA, o Martín reenvía desde el
   suyo? Lo segundo no cambia nada para los QA y se puede medir en una semana.
3. ¿El Dev del dibujo es Martín, o son también las sesiones de Claude Code? Si son las sesiones,
   el hook de alertas ya es el mecanismo y solo cambia la tabla que lee.

## Lo mínimo que se construye primero

Con las tres respuestas, el orden es este, y cada paso se mide antes del siguiente.

| Paso | Qué queda funcionando | Cómo se mide |
|---|---|---|
| 1. El repositorio de feedback con la plantilla de issue de siete columnas | La caja existe. Las filas se crean a mano | Cargar los 12 puntos del Word de Devalis y los reportes de OKOS de esta semana |
| 2. La conversión «en persona» | Una orden que toma una grabación, una nota o un documento y crea las filas | Correrla sobre el mismo Word y comparar con la carga a mano del paso 1 |
| 3. El reflejo de issues de cada repositorio | Las issues de QA de OKOS aparecen en la caja | Una issue de prueba en cada repositorio |
| 4. El receptor de WhatsApp | Un mensaje reenviado se vuelve fila en menos de un minuto | Diez mensajes reales, contados a mano contra la tabla |
| 5. El Dev lee la caja | Las filas nuevas llegan a la sesión igual que las alertas | Abrir una sesión y ver la fila |

Los pasos 2, 3 y 4 no dependen entre sí y corren en paralelo una vez hecho el 1.
