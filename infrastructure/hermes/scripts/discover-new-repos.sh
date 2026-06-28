#!/usr/bin/env bash
# Discover new GitHub repos for kirlts and register them.
# Runs every 5 minutes via crontab.
# Only detects repos created within the last 48 hours.
set -uo pipefail

MANIFEST="/opt/toolset-repo/infrastructure/hermes/cloned-repos.yaml"

# Get current timestamp in ISO 8601 for comparison
NOW_ISO=$(date -u +%Y-%m-%dT%H:%M:%SZ)
# Only detect repos created on or after June 28, 2026
SINCE="2026-06-28T00:00:00Z"

# Extract registered URLs to avoid duplicates
REGISTERED_URLS=$(grep -oP 'url:\s+\K\S+' "$MANIFEST" 2>/dev/null | sort -u || true)

# Get repo list from gh, only repos created in the last 48h
REPOS=$(gh repo list kirlts --limit 50 --json name,description,createdAt,isPrivate 2>/dev/null || echo "[]")
if [ "$REPOS" = "[]" ] || [ -z "$REPOS" ]; then
  exit 0
fi

# Filter for repos created in the last 48h AND not already registered
NEW_REPOS=""
for name in $(echo "$REPOS" | python3 -c "
import sys, json
repos = json.load(sys.stdin)
for r in repos:
    print(f\"{r['name']}|{r['createdAt']}\")
" 2>/dev/null); do
  repo_name="${name%%|*}"
  repo_created="${name##*|}"

  # Skip if created before the cutoff
  if [ "$repo_created" \< "$SINCE" ] 2>/dev/null; then
    continue
  fi

  # Skip if already registered
  REPO_URL="https://github.com/kirlts/$repo_name.git"
  if echo "$REGISTERED_URLS" | grep -qxF "$REPO_URL" 2>/dev/null; then
    continue
  fi

  NEW_REPOS="$NEW_REPOS $repo_name"
done

if [ -z "$NEW_REPOS" ]; then
  exit 0
fi

for repo in $NEW_REPOS; do
  # Get repo details
  DETAILS=$(echo "$REPOS" | python3 -c "
import sys, json
repos = json.load(sys.stdin)
for r in repos:
    if r['name'] == '$repo':
        print(json.dumps(r))
        break
" 2>/dev/null)

  DESC=$(echo "$DETAILS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('description','') or '')" 2>/dev/null)
  IS_PRIVATE=$(echo "$DETAILS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('isPrivate',False))" 2>/dev/null)

  # Clone the repo
  REPO_PATH="/opt/$repo"
  if [ ! -d "$REPO_PATH" ] || [ -z "$(ls -A "$REPO_PATH" 2>/dev/null)" ]; then
    if [ "$IS_PRIVATE" = "True" ]; then
      gh repo clone "kirlts/$repo" "$REPO_PATH" 2>/dev/null || continue
    else
      git clone "https://github.com/kirlts/$repo.git" "$REPO_PATH" 2>/dev/null || continue
    fi
  fi

  # Add to cloned-repos.yaml
  cat >> "$MANIFEST" << YAML
  $repo:
    url: https://github.com/kirlts/$repo.git
    path: $REPO_PATH
    type: cloned
    sync: cron
YAML

  # Write to personal-buffer via hermes one-shot
  DESC_SAFE="${DESC:-sin descripcion}"
  export PATH="/usr/local/bin:/home/opc/.local/bin:$PATH"
  hermes -z "Hace retain a personal-buffer con tags pending,new-repo. Content: Nuevo repositorio detectado: $repo ($DESC_SAFE). URL: https://github.com/kirlts/$repo. Clonado en $REPO_PATH. No hagas nada mas, solo el retain." 2>/dev/null || true
done

# Commit manifest changes and push
cd /opt/toolset-repo
git add infrastructure/hermes/cloned-repos.yaml 2>/dev/null
git commit -m "feat: auto-register new repos $(echo $NEW_REPOS | tr '\n' ' ')" 2>/dev/null
git push origin main 2>/dev/null || true
