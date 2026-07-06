# CI/CD Manual Deploy — Transition Reference

## Policy (establecida 2026-07-05)

**Push a main** → solo corre `validate-configs` (syntax check, rápido).
**Deploy** → solo via `workflow_dispatch` manual, previa autorización del usuario.

### Reglas

- Hermes pushea a main autónomamente (sin preguntar).
- Hermes NOTIFICA al usuario que hay cambios listos para deploy.
- Deploy SOLO cuando el usuario autoriza explícitamente.
- Hermes gatilla: `gh workflow run deploy.yml --repo kirlts/toolset`
- Si el usuario rechaza o no responde: los cambios quedan en main sin deploy.

## Cambios en deploy.yml

Para implementar este cambio en el workflow de GitHub Actions:

1. **Jobs `opentofu`, `deploy-services`, `preflight`** deben tener condición:
   ```
   if: ${{ ... && github.event_name == 'workflow_dispatch' }}
   ```
2. **Job `validate-configs`** se mantiene en `on.push` (corre en cada push).
3. El trigger `workflow_dispatch` ya existe en el workflow (con inputs para skip flags).

## Nota de Transición

El primer push que incluye estos cambios en deploy.yml gatillará un ÚLTIMO deploy automático con el workflow anterior (sin las condiciones). Esto es normal. Después de ese deploy, la política nueva queda activa y futuros pushes solo correrán validate-configs.

## Referencia del Usuario

Martín fue explícito: "el deploy queda criterio mío, pero que tú me tienes que avisar."
"no es que el deploy sea manual [necesite mi click en GitHub], tú puedes hacer el push por tu cuenta, pero la orden de hacer deploy es manual."
