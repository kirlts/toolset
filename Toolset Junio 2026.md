# **Especificación de Toolset Personal**

# **Junio 2026** (Actualizado: 2026-06-22)

Este documento define la infraestructura técnica para un *solo-dev* autónomo. El diseño prioriza la separación de responsabilidades entre la deliberación profunda en local y la ejecución asíncrona en la nube, mitigando el *vendor lock-in* y los costos variables de infraestructura.

## **1\. Dominio Local (Workstation)**

La estación de trabajo gestiona la planificación, la edición quirúrgica y la investigación.

* **Antigravity / Claude Code Desktop:** Motor principal para deliberación. Utilizado para investigación arquitectónica, redacción de planes de trabajo y análisis de alto nivel. Suscripción activa para acceso a modelos de frontera.  
* **Kilo Code (VS Extension):** Entorno por defecto para tareas rutinarias y refactorización técnica. Conectado al proveedor "OpenCode Go" bajo una suscripción fija. Mantiene sesiones con un modelo único para evitar la destrucción de la caché de contexto.  
* **Conectividad MCP:** Ambos entornos consumen contexto mediante el estándar Model Context Protocol. Se conectan directamente a las instancias de Hermes, Hindsight y Composio.  
* **Gobernanza (Sistema Kairos):** Inyecta el comportamiento del agente mediante *Custom Modes* y directrices de sistema locales (director.md, senior-coder.md). Fuerza la estructura de trabajo definida en los protocolos de fricción productiva y excelencia visual.

## **2\. Dominio Cloud (Oracle Cloud Infrastructure \- OCI)**

La infraestructura opera como un nodo de ejecución persistente (24/7) en el nivel gratuito de OCI.

### 2.1 Instancia de Cómputo
* **Shape:** VM.Standard.A1.Flex (Ampere ARM)
* **OCPU:** 2 | **RAM:** 12 GB | **Boot Volume:** 100 GB (de 200 GB del pool Always Free)
* **SO:** Oracle Linux 9.7 aarch64
* **Región:** sa-valparaiso-1 | **AD:** SA-VALPARAISO-1-AD-1
* **Runtime:** Docker 29.6.0 + Docker Compose Plugin

### 2.2 Servicios Desplegados
* **Aprovisionamiento (OpenTofu):** Infraestructura inmutable. Define y despliega todo el stack desde cero mediante archivos de configuración declarativa, eliminando la configuración manual (SSH o Web UI). ✅ Desplegado.
* **Red (Tailscale):** Red privada (WireGuard) que une la workstation local con el servidor en la nube. No se exponen puertos públicos — el acceso SSH es exclusivamente vía Tailscale. ✅ Activo. (*Tailscale Funnel* para webhooks queda pendiente de configuración).
* **Gestión de Secretos (Infisical):** Self-hosted en OCI. Inyecta credenciales en runtime sin archivos .env persistentes. Admin creado (`martin.gil.o@gmail.com`). ✅ Desplegado (pendiente integración con Hermes y Daytona).
  * Dependencias: **PostgreSQL 16** (datos), **Redis 7** (caché/cola).
* **Orquestación (Hermes Agent):** 🔲 Pendiente. Procesa órdenes vía WhatsApp/Discord, delega subagentes, coordina el sandbox.
* **Sandboxing (Daytona):** 🔲 Pendiente. Crea micro-contenedores temporales para ejecución de código y pruebas.
* **Memoria (Hindsight):** Cloud MCP (vectorize.io). ✅ Activo. El self-hosting es viable vía `ghcr.io/vectorize-io/hindsight:latest` (ARM64). Pendiente de despliegue en OCI para migrar desde el cloud.
* **Integración (Composio):** Pasarela de autenticación OAuth para GitHub CLI y otras APIs comerciales. ✅ Activo.

### 2.3 Pipeline CI/CD
* **GitHub Actions + OpenTofu:** Despliegue automatizado de infraestructura. API key como autenticación temporal (OIDC Identity Propagation pendiente de resolver — ver TECHNICAL-DEBT.md).
* **Remote State:** Almacenado en OCI Object Storage (bucket `toolset-opentofu-state`). Sincronización vía OCI CLI en el pipeline.
* **Keepalive anti-reclamation:** Cron job cada 10 minutos que genera carga de CPU para evitar que OCI marque la instancia como idle.

## **3\. Sinergia y Caso de Uso**

### **Operación Móvil (WhatsApp/Discord)**

* *Situación:* El usuario solicita a Hermes levantar un entorno desplegando el código de un repositorio dado, y realizar cambios, diagnosticar, ver capturas, o más, desde un entorno móvil / de mensajería.   
1. La orden llega vía texto o audio a Hermes utilizando sus integraciones nativas con Whatsapp o Discord  
2. Hermes delega a un subagente asíncrono para no bloquear la comunicación y poder entregar reportes de estado al usuario proactivamente o cuando este se lo solicita.  
3. El subagente solicita credenciales de entorno a Infisical, levanta un *sandbox* en Daytona, crea una rama nueva para su tarea en el repositorio ejecuta Playwright para capturar screenshots si es necesario, y reporta resultado, junto con screenshots opcionalmente.  
4. Hermes gestiona las operaciones en Github mediante CLI, Composio, o MCP.  
5. Hermes envía el reporte final o solicita intervención del usuario.

## **4\. Gobernanza y Sincronización**

* **Memoria Centralizada:** Hindsight corre como servicio cloud (vectorize.io). Tanto la workstation local como el servidor en la nube consultan la misma URL, garantizando que el contexto no se fragmente. *(Self-hosting descartado: no existe imagen Docker pública para ARM64.)*
* **Consistencia de Caché:** Para evitar el *cache miss* en OpenCode Go, cada sesión de trabajo (ya sea en Kilo Code o en una tarea de Hermes) mantiene un modelo de inferencia único asignado. El usuario debe poder consultar y/o gestionar el modelo seleccionado fácilmente al interactuar con Hermes.  
* **Independencia:** La infraestructura es recuperable y desplegable en su totalidad mediante OpenTofu. Si el proveedor de nube falla, la migración a un nuevo host requiere solo la ejecución de los scripts de aprovisionamiento existentes. La infraestructura es versionable.

## **5\. Limitaciones Conocidas (Junio 2026)**

* **Hindsight self-hosted pendiente:** El Docker image `ghcr.io/vectorize-io/hindsight:latest` está disponible. Requiere PostgreSQL 14+ con pgvector + LLM API key. Pendiente migración del bank "toolset" desde cloud a OCI.
* **Tailscale SSH con SELinux:** Oracle Linux 9 tiene SELinux activo por defecto, lo que bloquea Tailscale SSH. El acceso SSH se realiza con llave convencional sobre la red Tailscale (IP 100.x.x.x).
* **SSH público cerrado:** El puerto 22 solo acepta conexiones desde dentro de la VCN (10.0.0.0/16). El bootstrap inicial de una instancia nueva requiere acceso SSH temporal vía IP pública hasta que cloud-init complete la instalación de Tailscale (~5-8 minutos).
* **OIDC Identity Propagation no funcional:** El pipeline CI/CD usa API key como puente. Ver TECHNICAL-DEBT.md DT-001.
