#!/usr/bin/env bash
# Silent cron for git pull on cloned repos.
# Runs every 5 minutes via systemd timer or crontab.
# Outputs nothing unless there's a merge conflict.
# Notifies via Hermes message max 1x per day per repo.
set -uo pipefail

MANIFEST="/opt/toolset-repo/infrastructure/hermes/cloned-repos.yaml"
NOTIFY_FILE="/tmp/hermes-repo-conflict-notified"
CONFLICT_FILE="/tmp/hermes-repo-conflicts"

: > "$CONFLICT_FILE"

# Read repos from manifest where sync=cron or sync=deploy (not ci_cd)
REPOS=$(grep -oP '^\s+\K[a-z][a-z0-9_-]+(?=:)' "$MANIFEST" 2>/dev/null || true)

for key in $REPOS; do
  sync=$(awk "/^  ${key}:/{f=1} f{ if(\$1==\"sync:\"){print \$2; exit}} f && /^  [a-z]/{exit}" "$MANIFEST" 2>/dev/null)
  path=$(awk "/^  ${key}:/{f=1} f{ if(\$1==\"path:\"){print \$2; exit}} f && /^  [a-z]/{exit}" "$MANIFEST" 2>/dev/null)

  # Skip ci_cd repos (handled by deploy pipeline)
  [ "$sync" = "ci_cd" ] && continue

  if [ ! -d "${path}/.git" ]; then
    continue
  fi

  OUTPUT=$(cd "$path" && git pull --ff-only 2>&1) || true
  EXIT_CODE=$?

  if [ $EXIT_CODE -ne 0 ]; then
    echo "${key}@${path}: pull failed (exit ${EXIT_CODE})" >> "$CONFLICT_FILE"
    echo "  ${OUTPUT}" >> "$CONFLICT_FILE"
  elif echo "$OUTPUT" | grep -qi "conflict\|failed to merge\|merge failed\|couldn.t merge"; then
    echo "${key}@${path}: merge conflict" >> "$CONFLICT_FILE"
    echo "  ${OUTPUT}" >> "$CONFLICT_FILE"
  fi
done

# Notify if conflicts exist, max 1x per day
if [ -s "$CONFLICT_FILE" ]; then
  TODAY=$(date +%Y-%m-%d)
  LAST=$(cat "$NOTIFY_FILE" 2>/dev/null || echo "")

  if [ "$LAST" != "$TODAY" ]; then
    SUMMARY=$(cat "$CONFLICT_FILE")
    export PATH="/usr/local/bin:/home/opc/.local/bin:$PATH"
    hermes -z "Conflicto de git pull automatico en repos clonados:\n${SUMMARY}\nRevisar manualmente."
    echo "$TODAY" > "$NOTIFY_FILE"
  fi
fi
