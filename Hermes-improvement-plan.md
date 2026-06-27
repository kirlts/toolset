# 06-26 Diseño de arquitectura multi-canal en WhatsApp para perfiles Hermes con control de contexto y orquestación de repositorios

[image]
## Síntesis Central

La oportunidad es convertir WhatsApp Comunidades en la capa de orquestación de Hermes: múltiples grupos sirven como “canales-perfil” con contextos, skills y variables diferenciadas, enlazados dinámicamente a repositorios y documentación viva; el cuello de botella actual es un único canal y prompts globales rígidos. La evidencia: Hermes ya corre estable en un VPS, integra Bayliss (TypeScript) para WhatsApp, soporta perfiles (sub-instancias con contextos/skills/entornos separados) y cuenta con Kilo CLI para operaciones en repositorios; WhatsApp Comunidades provee grupos con descripciones y un canal de avisos reutilizable como fuente de verdad. El stake: sin arquitectura multi-perfil por canal, se mezcla contexto técnico, se degrada calidad a partir de ~500k tokens pese al millón del modelo DeepSeek V4 Flash, y se obliga a ejecutar /new para reiniciar el contexto del unico chat entre el usuario y el bot por whatsapp actualmente, perdiendo eficiencia y la posibilidad de una conversación focalizada con diseño per-repositorio y reglas parametrizadas, Hermes puede ejecutar flujos Kairos, mantener límites de contexto, y coordinar tareas entre perfiles (incluida infraestructura) sin romper continuidad. Es imperativo formalizar separación de responsabilidades, parametrización de contextos por canal, y controles de ventana de contexto con alertas suaves a 500k tokens.

---

## Arquitectura Operativa: Canales, Perfiles y Fuentes de Verdad

### 1. De “un chat” a “sistema multi-canal”
- Estado actual: Un único hilo de WhatsApp; comando /new borra contexto; reglas globales monolíticas.
- Objetivo: Comunidad WhatsApp con múltiples grupos para distintos usos; Hermes agregado a todos los grupos con un perfil específico según el grupo donde esté agregado, lista de grupos generada dinámicamente (sin hardcode).

### 2. Perfiles Hermes como separación de roles
- Cada grupo de whatsapp mapea a un perfil Hermes: contexto propio, skills específicas, variables de entorno diferenciadas, y acceso a Kilo CLI cuando aplique.
- Grupos por repo (ej. kirlts/cl-concerts-db): el perfil carga instrucciones específicas sobre como trabajar en ese repo en específico, sumado a sus instrucciones base ya existentes, y las instrucciones base de Kilo CLI le obligan a trabajar bajo el regimen kairos (dinámica “eje documental” con /document y /test periodicos). comandos de hindsight se hacen sobre el bank homónimo al repo (ej: para cl-concerts-db, bank se llama cl-concerts-db)
- Las palabras "grupo" y "perfil" son intercambiables en el contexto de Hermes, dado que el modo principal de interacción del usuario con Hermes será a través de grupos de whatsapp, cada uno correspondiendo a un perfil distinto. Salvo el caso específico donde se le hable al número personal del bot, que corresponderá al perfil maestro "hermes", cuyo bank "hermes" ya se encuentra activo y poblado, pero que deberá reiniciarse por completo dado el cambio de paradigma de comunicación.
- Un perfil corresponde a un grupo homónimo, con marcadas excepciones. Por el momento, el usuario ya ha creado desde su teléfono los grupos (y agregado al bot de hermes como integrante junto al propio usuario):\
  \
  - Chat (se deberá optimizar este grupo/perfil para chat en general, sin enfoque específico, útil para brainstorming, consultas rápidas, dialéctica)\
  - Code (optimizar para tareas en repositorios, altamente orientado a delegar tareas de todo tamaño a Kilo CLI, ya sea en Auto o en modo convencional, según contexto y conversación con el usuario)\
  - Research (optimizado para búsquedas en internet, reddit, y otras herramientas expuestas por MCP, utiliza el repo kirlts/researchit ya clonado en toolset cuando es necesario)\
  - Personal (optimizado para el contexto del usuario, vida diaria, objetivos, filosofia, pensamientos, planes, vivencias, etc)\
  - Toolset (optimizado para tareas de la infraestructura de hermes, las cuales todas persistirán en el repositorio toolset, dado que nuestro stack funciona con IaC)\
  \
  (La excepción actual es la existencia del perfil base "Hermes", que será el perfil por defecto si no se habla a hermes desde un grupo particular), y se mantendrá como perfil de más "bajo nivel" de hermes, con la misión de "ser Hermes" y hacer bien su trabajo. 
- Cada perfil debe tener su propio bank homónimo en hindsight, que debe ser creado mediante un script o proceso programático que cree un bank "[nombre de grupo de whatsapp en minusculas + sufijo "-group"]. Ej: Grupo "Personal" tiene bank "personal-group", y el perfil se llama "personal". Grupo "Chat" tiene bank "chat-group", y el perfil se llama "chat". Recordatorio: en el futuro se crearán grupos específicos para trabajar en repositorios, como "cl-concerts-db". En este caso, los banks se llamarán exactamente igual que el repositorio. 
- Cada perfil asume que el grupo solo tiene al usuario y al perfil como integrantes. La adición de terceros al grupo es posible pero no se modelarán comportamientos espscíficos para ello, más allá de que Hermes tenga consciencia de que podría darse el caso. 

### 3. Parametrización vía descripciones de WhatsApp (investigar, no sabemos si es posible actualmente en Hermes Whatsapp por baileys)
- Comunidad: descripción y canal de avisos como anclas de contexto (reglas globales mínimas, anuncios y cambios).
- Cada grupo: descripción actúa como manifiesto del perfil (instrucciones, rutas del repo, políticas de contexto, límites).
- Hermes/Baileys debe poder leer estos campos para auto-configuración, y cuando se le agregue a un grupo, iniciar un proceso de onboarding que creará y configurará el perfil tras haber iniciado y llevado a cabo las consultas necesarias con el usuario. 

### 4. Contexto, historial y control de tokens
- Diferenciar “ventana de contexto” vs “historial del grupo”:
  - Nuevo comando "/clean" para hermes, al mismo nivel de integracion y determinismo que "/new". Objetivo: Reiniciar ventana de contexto actual sin borrar historial, para que el agente pueda leer del hjistorial de la conversacion si es necesario para comprender mejor las peticiones del usuario, sin degradar su ventana de contexto para sesiones largas.
  - Uso de /new como comando dedicado para “borrar historial” y ventana de contexto. Revisar si /new actual requiere modificaciones.
- Modelo DeepSeek V4 Flash: ventana 1M; degradación significativa &gt;500k.
  - Política: límite suave a 500k con alertas progresivas; recuperación selectiva del historial sólo cuando aporte valor.

### 5. Interoperabilidad entre perfiles
- Perfiles deben poder delegarse tareas entre sí sin obligar a cambiar de grupo. \
  \
  Ej: Si durante una sesion en el grupo "chat" surge la idea de "mejorar la infraestructura de hermes", el perfil "chat" debe delegar al perfil "toolset" para su implementacion, con la premisa de que dicho perfil tendrá instrucciones, skills y bank específico llamado "toolset-profile" que lo hacen ideal para modificaciones de la IaC que compone a hermes. \
  El perfil invocado irá enviando mensajes y/o consultas y/o artefactos para el usuario en su grupo. Por ahora, quedará pendiente implementar una lógica para un verdadero trabajo y delegación asíncrona de agentes orquestados por un perfil en particular. \
  \
  El usuario debe poder invocar un perfil utilizando "@[perfil]"  en medio de una conversación. 
- Diseño tentativo: mensajería interna o “llamadas on-demand” documentadas por Hermes para coordinación entre perfiles.

### 6. Replanteo de reglas globales y skills
- Evaluar la pertinencia de las reglas globales actuales al diseño planteado. Las reglas globales, segun este diseño y la documentación de hermes, ¿terminarán afectando unicamente al perfil default "hermes", o quedarán como reglas ADICIONALES a las que ya pondremos por perfil? esto es vital de averiguar, pues afectará a lo que haremos con las rules. 
- Distribuir skills existentes por perfil según descripciones de cada uno para rol acotado y performance estable, agregando y/o modificando skills según sea necesario.
- Mantener instrucciones ajustadas al contexto, versionadas y editables , siguiendo la filosofía del repo toolset.

### 7. Flujo Kairos y Kilo CLI integrados
- Estándar de trabajo con repositorios bajo Kairos como “core” del canal de programación y de cada perfil por repo.
- Kilo CLI como herramienta por defecto para cambios, tests, investigación de código dentro de los perfiles que lo requieran.

---

