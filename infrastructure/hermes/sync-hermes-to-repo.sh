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

# ---- 5. Scripts ----
echo "[SYNC] Scripts..."
if [ -d "${HERMES_HOME}/scripts" ] && [ -n "$(ls -A ${HERMES_HOME}/scripts 2>/dev/null)" ]; then
  rsync -a --delete "${HERMES_HOME}/scripts/" "${HERMES_DIR}/scripts/"
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

# ---- 7. Git pull with rebase to avoid non-fast-forward rejection ----
echo "[SYNC] Pulling latest remote changes..."
git fetch origin main 2>&1
git rebase origin/main 2>&1 || echo "[SYNC] Rebase failed (will retry next cycle)"

# ---- 8. Git commit ----"
if git diff --quiet infrastructure/hermes/; then
  echo "[SYNC] No changes to commit."
else
  git add infrastructure/hermes/
  git commit -m "${COMMIT_MSG}"
  # Push current branch to main on remote
  git push origin HEAD:main 2>&1 || echo "[SYNC] Push failed (will retry next cycle)"
  echo "[SYNC] Committed and pushed: ${COMMIT_MSG}"
fi

echo "[SYNC] === Sync complete ==="
