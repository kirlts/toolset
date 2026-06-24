#!/usr/bin/env bash
# ============================================================
# sync-hermes-to-repo.sh — Toolset Personal Hermes Sync
#
# Syncs all auto-generated Hermes artifacts from the running
# instance ( ~/.hermes/ ) into the toolset repo so they are
# versioned, recoverable, and auditable.
#
# Schedule: daily via cron ( cronjob action=create )
# ============================================================
set -euo pipefail

REPO_DIR="${REPO_DIR:-/home/opc/workspace/toolset}"
HERMES_DIR="${REPO_DIR}/infrastructure/hermes"
HERMES_HOME="${HERMES_HOME:-/home/opc/.hermes}"

TIMESTAMP=$(date -u +%Y-%m-%d)
COMMIT_MSG="hermes-sync: file artifacts ${TIMESTAMP}"

cd "$REPO_DIR"

echo "[SYNC] === Hermes → Repo sync ${TIMESTAMP} ==="

# ---- 1. SOUL.md ----
echo "[SYNC] SOUL.md..."
cp "${HERMES_HOME}/SOUL.md" "${HERMES_DIR}/SOUL.md"

# ---- 2. config.yaml (structural only — no secrets in this file) ----
echo "[SYNC] config.yaml..."
cp "${HERMES_HOME}/config.yaml" "${HERMES_DIR}/config.yaml"

# ---- 3. Memory files ----
echo "[SYNC] Memory files..."
cp "${HERMES_HOME}/memories/MEMORY.md" "${HERMES_DIR}/memory/MEMORY.md" 2>/dev/null || echo "  (no MEMORY.md)"
cp "${HERMES_HOME}/memories/USER.md"   "${HERMES_DIR}/memory/USER.md"   2>/dev/null || echo "  (no USER.md)"

# ---- 4. Skills (full snapshot — all skills as deployed) ----
echo "[SYNC] Skills..."
rm -rf "${HERMES_DIR}/skills"
cp -a "${HERMES_HOME}/skills" "${HERMES_DIR}/skills"
# Remove curator internal state and backups from repo
rm -rf "${HERMES_DIR}/skills/.curator_backups" 2>/dev/null || true
rm -f "${HERMES_DIR}/skills/.curator_state" 2>/dev/null || true
rm -f "${HERMES_DIR}/skills/.bundled_manifest" 2>/dev/null || true
rm -f "${HERMES_DIR}/skills/.usage.json" 2>/dev/null || true
# Remove .hub directory (hub-installed skills cache)
rm -rf "${HERMES_DIR}/skills/.hub" 2>/dev/null || true

# ---- 5. Scripts (excluye node_modules) ----
echo "[SYNC] Scripts..."
if [ -d "${HERMES_HOME}/scripts" ] && [ -n "$(ls -A ${HERMES_HOME}/scripts 2>/dev/null)" ]; then
  rsync -a --delete --exclude node_modules "${HERMES_HOME}/scripts/" "${HERMES_DIR}/scripts/"
else
  echo "  (no scripts)"
fi

# ---- 6. Hooks ----
echo "[SYNC] Hooks..."
if [ -d "${HERMES_HOME}/hooks" ] && [ -n "$(ls -A ${HERMES_HOME}/hooks 2>/dev/null)" ]; then
  rsync -a --delete "${HERMES_HOME}/hooks/" "${HERMES_DIR}/hooks/"
else
  echo "  (no hooks)"
fi

# ---- 7. WebUI settings (send_key, theme, font size, etc.) ----
echo "[SYNC] WebUI settings..."
if [ -f "${HERMES_HOME}/webui/settings.json" ]; then
  mkdir -p "${HERMES_DIR}/webui"
  cp "${HERMES_HOME}/webui/settings.json" "${HERMES_DIR}/webui/settings.json"
fi

# ---- 8. Commit local changes first ----
if ! git diff --quiet infrastructure/hermes/; then
  echo "[SYNC] Committing local changes..."
  git add infrastructure/hermes/
  git commit -m "${COMMIT_MSG}"
  CHANGES_COMMITTED=true
else
  echo "[SYNC] No local changes to commit."
  CHANGES_COMMITTED=false
fi

# ---- 8. Rebase on remote main then push ----
echo "[SYNC] Syncing with remote..."
git fetch origin main 2>&1
if [ "${CHANGES_COMMITTED}" = "true" ]; then
  # Only rebase if we actually committed something (avoids issues with stale index)
  git rebase origin/main 2>&1 && \
  git push origin HEAD:main 2>&1 || \
  echo "[SYNC] Remote sync failed (will retry next cycle)"
fi

echo "[SYNC] === Sync complete ==="
