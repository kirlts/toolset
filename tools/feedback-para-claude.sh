#!/usr/bin/env bash
# Hook de sesión: las filas de feedback sin responder del proyecto, como contexto para Claude Code.
# En los hooks del repositorio (SessionStart o UserPromptSubmit):
#   {"type": "command", "command": "~/toolset/tools/feedback-para-claude.sh devalis", "timeout": 10}
exec timeout 8 python3 -I "$HOME/toolset/tools/feedback.py" pendientes ${1:+--proyecto "$1"} 2>/dev/null || true
