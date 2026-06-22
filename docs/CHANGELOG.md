# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Creación de `.gitignore` robusto ignorando artefactos de Terraform, Python, Node y archivos de Kairós.
- Aprovisionamiento base de red virtual (VCN) en OCI utilizando OpenTofu (`infrastructure/`).
- Integración de Workload Identity Federation (Identity Propagation Trust) en OCI para GitHub Actions.
- Flujo automatizado de CI/CD en `.github/workflows/deploy.yml` para despliegues de OpenTofu desde GitHub.
- Creación de Confidential App y Identity Propagation Trust "GitHub Actions Toolset Trust" vía SCIM API en el dominio OCI.
- Generación de API key para `svc_github_actions` como puente temporal de autenticación.

### Fixed
- Pipeline CI/CD funcional con autenticación API key. El flujo OIDC/Identity Propagation Trust no logró completar el token exchange contra `/oauth2/v1/token` del dominio (error `invalid_request` persistente). Documentado como deuda técnica.

### Changed
- Sincronización masiva del eje documental con la especificación `Toolset Junio 2026.md` ejecutada bajo `/document` en modo incremental.
- `MASTER-SPEC.md`: Desglose arquitectónico en Fase 1 (Transición Cloud/MCP) y Fase 2 (Soberanía OCI).
- `TODO.md` y `VERIFICATION.md`: Inyección de las Epicas 002 a 005 trazando el camino hacia la implementación de OCI, Tailscale, Infisical, Daytona, Hermes y Hindsight self-hosted, configuradas para descubrimiento técnico progresivo.
- Actualización estructural de las reglas en `docs/RULES.md` para coincidir de forma estricta con la plantilla agnóstica de `mcp.md`.
- Reestructuración del formato interno en la configuración de MCP para Kilo Code (`~/.config/kilo/kilo.jsonc`) ajustándose a la clave `mcp` y forzando `"type": "remote"`.

## [0.1.0] - 2026-06-21

### Added
- Inicializacion del repositorio local git en /home/kirlts/toolset.
- Integracion del servidor MCP Composio para conectividad con Google Drive.
- Integracion del servidor MCP Hindsight para almacenamiento de memoria de contexto centralizado.
- Bootstrap inicial del sistema de documentacion de gobernanza de Kairos en el directorio docs/.
