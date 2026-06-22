# Próxima Sesión: TASK-006 — Desplegar Hermes Agent

> Estado al cierre: 2026-06-22 13:49 CLT
> Commit: `45f30d0`

## Contexto

- Hindsight self-hosted en OCI, bank toolset migrado, MCP activo vía Funnel
- CI/CD pipeline con deploy-services (SSH + Tailscale)
- Caddy reverse proxy multi-servicio (Hindsight API/CP/Infisical)
- Daytona eliminado — Hermes usará sandbox Docker nativo (`terminal.backend: docker`)

## Qué hacer

1. **Agregar Hermes Agent al docker-compose.yml**
   - Repo oficial: `github.com/NousResearch/hermes-agent`
   - Verificar imagen Docker ARM64 disponible en GHCR
   - Puerto: TBD (investigar por defecto)

2. **Configurar Hermes**
   - `terminal.backend: docker` con hardening
   - `terminal.docker.image: nikolaik/python-nodejs:python3.11-nodejs20`
   - `terminal.docker.network: none` (por defecto)
   - `terminal.docker.timeout: 30s`

3. **Integraciones**
   - Infisical: secrets vía service token o sidecar
   - Hindsight: agregar Hermes como MCP client o al revés
   - Composio: MCP directo desde Hermes
   - GitHub CLI: acceso para operaciones sobre repos

4. **WhatsApp/Discord**
   - Investigar APIs de WhatsApp Business / Discord Bot
   - Hermes tiene integraciones nativas? o requiere capa aparte?

5. **Healthcheck**
   - Probar sandbox ejecuta Python, playwright, git clone
   - Verificar network isolation (no acceso a internet por defecto)

## Recursos

- Comunidad: `r/hermesagent` (VPS megathread pinned)
- Referencia: `r/hermesagent/user/scicco/hermzner` — Terraform+Ansible+Tailscale+Podman
- Hostinger guide: https://www.hostinger.com/tutorials/hermes-agent-security
- LumaDock hardening: https://lumadock.com/tutorials/hermes-agent-production-hardening

## Stack actual en OCI

| Servicio | Puerto | Estado |
|---|---|---|
| PostgreSQL 16 | 5432 | ✅ |
| Redis 7 | 6379 | ✅ |
| Infisical | 8081 | ✅ |
| Hindsight (pg0) | 8888/9999 | ✅ |
| Caddy (Funnel) | 8080 | ✅ |
| **Hermes** | **TBD** | **🔲 Pendiente** |
