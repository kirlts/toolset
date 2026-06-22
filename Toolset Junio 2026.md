# **Especificación de Toolset Personal**

# **Junio 2026**

Este documento define la infraestructura técnica para un *solo-dev* autónomo. El diseño prioriza la separación de responsabilidades entre la deliberación profunda en local y la ejecución asíncrona en la nube, mitigando el *vendor lock-in* y los costos variables de infraestructura.

## **1\. Dominio Local (Workstation)**

La estación de trabajo gestiona la planificación, la edición quirúrgica y la investigación.

* **Antigravity / Claude Code Desktop:** Motor principal para deliberación. Utilizado para investigación arquitectónica, redacción de planes de trabajo y análisis de alto nivel. Suscripción activa para acceso a modelos de frontera.  
* **Kilo Code (VS Extension):** Entorno por defecto para tareas rutinarias y refactorización técnica. Conectado al proveedor "OpenCode Go" bajo una suscripción fija. Mantiene sesiones con un modelo único para evitar la destrucción de la caché de contexto.  
* **Conectividad MCP:** Ambos entornos consumen contexto mediante el estándar Model Context Protocol. Se conectan directamente a las instancias de Hermes, Hindsight y Composio.  
* **Gobernanza (Sistema Kairos):** Inyecta el comportamiento del agente mediante *Custom Modes* y directrices de sistema locales (director.md, senior-coder.md). Fuerza la estructura de trabajo definida en los protocolos de fricción productiva y excelencia visual.

## **2\. Dominio Cloud (Oracle Cloud Infrastructure \- OCI)**

La infraestructura opera como un nodo de ejecución persistente (24/7) en el nivel gratuito de OCI.

* **Aprovisionamiento (OpenTofu):** Infraestructura inmutable. Define y despliega todo el stack desde cero mediante archivos de configuración declarativa, eliminando la configuración manual (SSH o Web UI).  
* **Red (Tailscale & Funnel):** Crea una red privada (VLAN) que une la workstation local con el servidor en la nube sin exponer puertos públicos. "Tailscale Funnel" actúa como receptor seguro de eventos (webhooks) desde repositorios remotos.  
* **Gestión de Secretos (Infisical):** Elimina el almacenamiento de archivos .env. Inyecta credenciales y tokens directamente en memoria durante el tiempo de ejecución (local o en *sandbox*).  
* **Orquestación (Hermes Agent):** Procesa órdenes vía mensajería (WhatsApp/Discord). Delega tareas a subagentes, razona sobre el estado global y mantiene un hilo único de ejecución.  
* **Sandboxing (Daytona):** Entorno de ejecución aislado. Clona repositorios en micro-contenedores temporales, ejecuta pruebas (Playwright/Docker), realiza arreglos al vuelo y destruye el entorno tras finalizar.  
* **Memoria (Hindsight):** Centralizada y desplegada en OCI, expuesta por MCP. Utilizada por Hermes en Cloud, Antigravity/Claude Code y Kilo Code en local.  
* **Integración (Composio):** Pasarela de autenticación OAuth para GitHub CLI y otras APIs comerciales.

## **3\. Sinergia y Caso de Uso**

### **Operación Móvil (WhatsApp/Discord)**

* *Situación:* El usuario solicita a Hermes levantar un entorno desplegando el código de un repositorio dado, y realizar cambios, diagnosticar, ver capturas, o más, desde un entorno móvil / de mensajería.   
1. La orden llega vía texto o audio a Hermes utilizando sus integraciones nativas con Whatsapp o Discord  
2. Hermes delega a un subagente asíncrono para no bloquear la comunicación y poder entregar reportes de estado al usuario proactivamente o cuando este se lo solicita.  
3. El subagente solicita credenciales de entorno a Infisical, levanta un *sandbox* en Daytona, crea una rama nueva para su tarea en el repositorio ejecuta Playwright para capturar screenshots si es necesario, y reporta resultado, junto con screenshots opcionalmente.  
4. Hermes gestiona las operaciones en Github mediante CLI, Composio, o MCP.  
5. Hermes envía el reporte final o solicita intervención del usuario.

## **4\. Gobernanza y Sincronización**

* **Memoria Centralizada:** Hindsight corre exclusivamente en la instancia de OCI. Tanto la workstation local como el servidor en la nube consultan la misma URL vía Tailscale, garantizando que el contexto no se fragmente.  
* **Consistencia de Caché:** Para evitar el *cache miss* en OpenCode Go, cada sesión de trabajo (ya sea en Kilo Code o en una tarea de Hermes) mantiene un modelo de inferencia único asignado. El usuario debe poder consultar y/o gestionar el modelo seleccionado fácilmente al interactuar con Hermes.  
* **Independencia:** La infraestructura es recuperable y desplegable en su totalidad mediante OpenTofu. Si el proveedor de nube falla, la migración a un nuevo host requiere solo la ejecución de los scripts de aprovisionamiento existentes. La infraestructura es versionable.