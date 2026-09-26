#!/usr/bin/env python3
# no-es-instrumento: módulo sin __main__: la función esta_vivo/esta_retirado que importan vigencia.py, kb-mcp/server.py y correr.py
"""vivo.py — LA respuesta a «¿este compromiso sigue vivo?», en un solo lugar.

Existe por un defecto medido el 2026-08-28: la pregunta se contestaba a mano en cada
consumidor, y cada consumidor la armaba distinto. `tools/vigencia.py` no miraba `retirado` en
absoluto, y listaba como trabajo pendiente dos compromisos retirados —uno de ellos un plan
retirado por duplicado nueve días antes—. Y la cuenta hecha a mano con la misma regla
incompleta llegó hasta Martín dentro de un encargo: pedía seguir con «los 39 planes que quedan
en propuesto» cuando vivos había 31.

`tools/kb-mcp/server.py` y `delegacion/correr.py` SE VEÍAN bien —las dos miraban `retirado`
antes de contar algo como vivo— y no lo estaban del todo, y eso se descubrió recién al
consolidar acá (2026-09-24): `server.py` exigía el booleano `is True` y se quedaba corto con
la forma string `"true"` que la base también escribe; el inventario de `correr.py` filtraba
`retirado` sobre `en-curso/` pero no sobre los hallazgos de `comprobado/`. Los tres
consumidores importan esta función hoy, precisamente para que un cuarto no tenga que volver a
acertarle a mano.

LOS DOS CAMPOS SON ORTOGONALES A PROPÓSITO, y por eso el arreglo no es sincronizarlos:

  `estado`    en qué punto del ciclo está: propuesto → abierto → resuelto. El portón
              (`kb/validate.config.yaml`) no admite otros, y no existe un `estado: retirado`
              porque retirar no es una etapa del ciclo.
  `retirado`  si el documento se sirve. Es la disposición final de la curaduría: git lo
              conserva, el servidor deja de indexarlo.

Un documento puede estar `propuesto` y retirado sin contradicción. Lo que no puede es contarse
como trabajo vivo. Así que la respuesta necesita LOS DOS CAMPOS, siempre, y por eso vive acá y
no repetida en cada archivo: la misma verdad escrita a mano en dos lugares se desincroniza en la
primera edición.

Uso:
    from vivo import esta_retirado, esta_vivo
    if not esta_vivo(fm, ("propuesto", "abierto")):
        continue
"""
from __future__ import annotations

from typing import Iterable

# Los estados que significan trabajo por delante. Sale del portón
# (`kb/validate.config.yaml → estados_vivos`) y se repite acá con esa cita para que un cambio
# de allá se note leyendo esto.
ESTADOS_VIVOS = ("propuesto", "abierto", "aceptado", "en-curso")


def esta_retirado(fm: dict | None) -> bool:
    """True si el documento fue sacado de circulación por curaduría.

    Tolera el campo escrito como booleano de YAML o como la cadena «true», porque la base tiene
    las dos formas según qué verbo lo escribió.
    """
    if not isinstance(fm, dict):
        return False
    v = fm.get("retirado")
    if isinstance(v, str):
        return v.strip().lower() == "true"
    return v is True


def esta_vivo(fm: dict | None, estados: Iterable[str] = ESTADOS_VIVOS) -> bool:
    """True si el documento es trabajo vivo: estado de trabajo Y no retirado.

    El orden importa poco; lo que importa es que las dos condiciones estén acá y no en el
    consumidor. Un consumidor nuevo que pregunte por acá no puede heredar el defecto.
    """
    if not isinstance(fm, dict):
        return False
    if esta_retirado(fm):
        return False
    return str(fm.get("estado", "")).strip().lower() in {str(e).lower() for e in estados}
