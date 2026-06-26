---
name: toolset-ops
description: "Infrastructure operations for Toolset Personal (OCI/Docker/CI)."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [Infrastructure, OCI, Docker, CI-CD, Deployment]
    triggers: ["deploy", "fix bug", "infrastructure", "run cd"]
---

# Toolset Infrastructure Operations

## Rules (MASTER-SPEC §8)

- **INFRA-01**: All infra mutations strictly via CI/CD.
- **INFRA-04**: Mandatory MCP service restart after pipeline modifications.
- **INFRA-02**: Remote state in OCI Object Storage is authoritative.
- **INFRA-03**: Service deployment via CI/CD (deploy.sh). Local execution for verification only.

## Health Checks

| Service | Command |
|---|---|
| Docker containers | `sudo docker compose -f /opt/toolset/docker-compose.yml ps` |
| Hindsight | `curl -sf https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/health` |
| Infisical | `curl -sf http://localhost:8081/api/status` |
| Caddy | `curl -sf http://localhost:8080/health` |
| hermes-gateway | `systemctl is-active hermes-gateway` |

## Monitoring Protocol

When user asks "monitor", run the health checks above, report results, and do NOT follow up unless a failure is detected.
