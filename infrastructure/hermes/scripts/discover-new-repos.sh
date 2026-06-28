#!/usr/bin/env bash
# Discover new GitHub repos for kirlts and register them.
# Runs every 5 minutes via crontab.
set -uo pipefail

MANIFEST="/opt/toolset-repo/infrastructure/hermes/cloned-repos.yaml"

# Extract registered URLs to avoid duplicates (a repo may have different key but same URL)
REGISTERED_URLS=$(grep -oP 'url:\s+\K\S+' "$MANIFEST" 2>/dev/null | sort -u || true)

# Get repo list from gh
REPOS=$(gh repo list kirlts --limit 30 --json name,description,createdAt,isPrivate 2>/dev/null || echo "[]")

if [ "$REPOS" = "[]" ] || [ -z "$REPOS" ]; then
  exit 0
fi

NEW_REPOS=""
for name in $(echo "$REPOS" | python3 -c "import sys,json; repos=json.load(sys.stdin); [print(r['name']) for r in repos]" 2>/dev/null); do
  # Check if repo URL is already registered
  REPO_URL="https://github.com/kirlts/$name.git"
  if echo "$REGISTERED_URLS" | grep -qxF "$REPO_URL"; then
    continue
  fi
  NEW_REPOS="$NEW_REPOS $name"
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

  # Write to personal-buffer via Hermes
  PAYLOAD="{\"content\":\"Nuevo repositorio detectado: $repo. URL: https://github.com/kirlts/$repo. Descripcion: $DESC. Privado: $IS_PRIVATE. Clonado en $REPO_PATH.\",\"context\":\"new-repo-discovery\",\"tags\":[\"pending\",\"new-repo\"],\"bank_id\":\"personal-buffer\"}"
  echo "$PAYLOAD" > "/tmp/hermes-repo-event-$repo.json"
  # Use Hermes one-shot to retain to buffer
  export PATH="/usr/local/bin:/home/opc/.local/bin:$PATH"
  hermes -z "Hace retain a personal-buffer con tags pending,new-repo: Nuevo repositorio detectado: $repo ($DESC). URL: https://github.com/kirlts/$repo. Clonado en $REPO_PATH. No hagas nada mas, solo el retain." 2>/dev/null || true
done

# Commit manifest changes
cd /opt/toolset-repo
git add infrastructure/hermes/cloned-repos.yaml 2>/dev/null
git commit -m "feat: auto-register new repos $(echo $NEW_REPOS | tr '\n' ' ')" 2>/dev/null
git push origin main 2>/dev/null || true
