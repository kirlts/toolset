# API Key Export — set -a Pattern

## Problema

Cuando se ejecuta `source /home/opc/.hermes/.env` sin `set -a`, las variables se cargan en la shell actual PERO NO se exportan a procesos hijo. Esto causa:
- `kilo run` falla con "Missing API key" o "Invalid API key"
- `python3 -m src.research` falla con 401 AuthenticationError
- `curl` falla porque `$OPENCODE_GO_API_KEY` está vacío en el subprocess

## Solución: set -a

```bash
set -a                    # Mark vars for export
source /home/opc/.hermes/.env
set +a                    # Unset export mode

kilo run "task" --auto    # Ahora funciona porque OPENCODE_GO_API_KEY está exportada
```

## Por qué pasa

`set -a` (equivalente a `set -o allexport`) hace que TODAS las asignaciones de variables posteriores se exporten automáticamente al entorno de procesos hijo. Sin esto, `source` solo asigna variables de shell, no de entorno.

## Verificación

```bash
set -a && source /home/opc/.hermes/.env && set +a
python3 -c "import os; print('KEY' if os.environ.get('OPENCODE_GO_API_KEY') else 'MISSING')"
# Debe imprimir 'KEY', no 'MISSING'
```

## No usar en scripts

En scripts bash, usar `set -a` afecta todo el script. Preferir:
```bash
export OPENCODE_GO_API_KEY=***
source /home/opc/.hermes/.env 2>/dev/null
# O: extraer el valor específico
```

Para invocaciones one-liner, el compound command es la forma más limpia.
