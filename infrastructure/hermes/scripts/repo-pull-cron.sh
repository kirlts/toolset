#!/usr/bin/env bash
# Silent cron for git pull on cloned repos.
# Runs every 5 minutes via hermes cronjob (system crontab).
# When new commits arrive: write event file + invoke Hermes batch to evaluate buffer.
# Silent: no user notification unless merge conflict (max 1x/day).
set -uo pipefail

MANIFEST="/opt/toolset-repo/infrastructure/hermes/cloned-repos.yaml"
CONFLICT_FILE="/tmp/hermes-repo-conflicts"
EVENTS_DIR="/tmp/hermes-buffer-events"
NOTIFY_FILE="/tmp/hermes-repo-conflict-notified"
STATE_DIR="/tmp/hermes-repo-heads"

mkdir -p "$EVENTS_DIR" "$STATE_DIR"
: > "$CONFLICT_FILE"

REPOS=$(grep -oP '^\s+\K[a-z][a-z0-9_-]+(?=:)' "$MANIFEST" 2>/dev/null || true)
HAS_NEW_COMMITS=0

for key in $REPOS; do
  sync=$(awk "/^  ${key}:/{f=1} f{ if(\$1==\"sync:\"){print \$2; exit}} f && /^  [a-z]/{exit}" "$MANIFEST" 2>/dev/null)
  path=$(awk "/^  ${key}:/{f=1} f{ if(\$1==\"path:\"){print \$2; exit}} f && /^  [a-z]/{exit}" "$MANIFEST" 2>/dev/null)

  if [ ! -d "${path}/.git" ]; then
    continue
  fi

  # Handle ci_cd repos: externally updated via CI/CD deploy.sh, not git pull
  if [ "$sync" = "ci_cd" ]; then
    STATE_FILE="${STATE_DIR}/${key}"
    PREV_HEAD=$(cat "$STATE_FILE" 2>/dev/null || echo "")

    git fetch origin 2>/dev/null || true
    CURRENT_HEAD=$(cd "$path" && git rev-parse HEAD 2>/dev/null || echo "")
    [ -z "$CURRENT_HEAD" ] && continue

    if [ -n "$PREV_HEAD" ] && [ "$PREV_HEAD" != "$CURRENT_HEAD" ]; then
      HAS_NEW_COMMITS=1
      LOG=$(cd "$path" && git log --oneline --no-decorate "${PREV_HEAD}..${CURRENT_HEAD}" 2>/dev/null || true)
      BRANCH=$(cd "$path" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')

      EVENT_FILE="${EVENTS_DIR}/${key}_$(date +%Y%m%d%H%M%S).json"
      cat > "$EVENT_FILE" << EOF
{
  "repo": "${key}",
  "path": "${path}",
  "branch": "${BRANCH}",
  "old_head": "${PREV_HEAD}",
  "new_head": "${CURRENT_HEAD}",
  "timestamp": "$(date -Iseconds)",
  "commits": [
$(echo "$LOG" | sed 's/^/    "/' | sed 's/$/",/' | sed '$ s/,$//')
  ]
}
EOF
    fi
    echo "$CURRENT_HEAD" > "$STATE_FILE"
    continue
  fi

  if [ ! -d "${path}/.git" ]; then
    continue
  fi

  OLD_HEAD=$(cd "$path" && git rev-parse HEAD 2>/dev/null || echo "")

  OUTPUT=$(cd "$path" && git pull --ff-only 2>&1) || true
  EXIT_CODE=$?

  if [ $EXIT_CODE -ne 0 ]; then
    echo "${key}@${path}: pull failed (exit ${EXIT_CODE})" >> "$CONFLICT_FILE"
    echo "  ${OUTPUT}" >> "$CONFLICT_FILE"
    continue
  fi

  if echo "$OUTPUT" | grep -qi "conflict\|failed to merge\|merge failed\|couldn.t merge"; then
    echo "${key}@${path}: merge conflict" >> "$CONFLICT_FILE"
    echo "  ${OUTPUT}" >> "$CONFLICT_FILE"
    continue
  fi

  NEW_HEAD=$(cd "$path" && git rev-parse HEAD 2>/dev/null || echo "")
  if [ -n "$OLD_HEAD" ] && [ "$OLD_HEAD" != "$NEW_HEAD" ]; then
    HAS_NEW_COMMITS=1
    LOG=$(cd "$path" && git log --oneline --no-decorate "${OLD_HEAD}..${NEW_HEAD}" 2>/dev/null || true)
    BRANCH=$(cd "$path" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')

    # Write event file for buffer processing
    EVENT_FILE="${EVENTS_DIR}/${key}_$(date +%Y%m%d%H%M%S).json"
    cat > "$EVENT_FILE" << EOF
{
  "repo": "${key}",
  "path": "${path}",
  "branch": "${BRANCH}",
  "old_head": "${OLD_HEAD}",
  "new_head": "${NEW_HEAD}",
  "timestamp": "$(date -Iseconds)",
  "commits": [
$(echo "$LOG" | sed 's/^/    "/' | sed 's/$/",/' | sed '$ s/,$//')
  ]
}
EOF
  fi
done

# If new commits arrived, invoke Hermes batch to evaluate buffer silently
if [ $HAS_NEW_COMMITS -eq 1 ]; then
  export PATH="/usr/local/bin:/home/opc/.local/bin:$PATH"
  hermes chat -q "Se detectaron commits nuevos en repos clonados (revisa /tmp/hermes-buffer-events/). Evalua cada uno: si afecta la realidad de Martin (proyectos activos, ingresos, habilidades, condiciones laborales, estado de herramientas), haz retain al bank personal-buffer con tags ['pending','repo-push']. Si no es relevante, ignoralo. No respondas nada al usuario. Solo ejecuta los retains." --quiet --yolo 2>/dev/null
  # Cleanup processed events
  rm -f "${EVENTS_DIR}"/*
fi

# Conflict notification (max 1x/day) goes to stderr so it doesn't trigger agent
if [ -s "$CONFLICT_FILE" ]; then
  TODAY=$(date +%Y-%m-%d)
  LAST=$(cat "$NOTIFY_FILE" 2>/dev/null || echo "")
  if [ "$LAST" != "$TODAY" ]; then
    SUMMARY=$(cat "$CONFLICT_FILE")
    echo "$SUMMARY" >&2
    echo "$TODAY" > "$NOTIFY_FILE"
  fi
fi
