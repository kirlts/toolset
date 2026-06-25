# New Project Onboarding — Checklist

Ejecutar en orden para CADA proyecto nuevo:

## Paso 1: Crear repo y clonar .agents/

```bash
gh repo create kirlts/<repo> --private --description "..."
gh repo clone kirlts/<repo> /tmp/<repo>
gh repo clone kirlts/kairos /tmp/kairos-tmp
cp -r /tmp/kairos-tmp/.agents /tmp/<repo>/.agents
rm -rf /tmp/kairos-tmp
```

## Paso 2: Crear docs/ con templates kairos

Usar Kilo CLI para generar docs/ desde templates de .agents/templates/:
- docs/MASTER-SPEC.md
- docs/TODO.md
- docs/MEMORY.md
- docs/USER-DECISIONS.md
- docs/CHANGELOG.md

## Paso 3: Ejecutar /document

```bash
kilo run "Ejecuta /document según .agents/workflows/document.md" --auto
```

## Paso 4: Crear bank en Hindsight

```bash
mcp_hindsight_selfhosted_create_bank(bank_id="<repo>", name="<repo>")
```
**Regla:** bank_id SIEMPRE es exactamente el nombre del repo. No descripciones, no nombres largos.

## Paso 5: Crear skill Hermes

```bash
skill_manage(action='create', name='<repo>', category='...', content='...')
```

## Paso 6: Push a GitHub

```bash
cd /tmp/<repo>
git add -A
git commit -m "<repo> v1.0: ..."
git push origin main
```

## Paso 7: /document en toolset

Tras completar el bloque de trabajo, ejecutar `/document` en el repo toolset (kirlts/toolset), NO en el repo trabajado.
