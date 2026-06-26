#!/usr/bin/env bash
# consolidate-memory.sh — Monitor MEMORY.md size, trigger reflect+retain at threshold
# Runs on cron. If MEMORY.md exceeds 85% of capacity, consolidates to Hindsight
# via reflect+retain, then clears the buffer. After clearing, leaves a recall
# instruction so the next Hermes session restores context from Hindsight.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HERMES_HOME="${SCRIPT_DIR}"
MEMORY_FILE="${HERMES_HOME}/memories/MEMORY.md"
CAPACITY=2200
THRESHOLD=$((CAPACITY * 85 / 100))
LOG="/var/log/hermes-memory-consolidation.log"

if [ ! -f "$MEMORY_FILE" ]; then
  exit 0
fi

SIZE=$(wc -c < "$MEMORY_FILE" 2>/dev/null || echo 0)
if [ "$SIZE" -lt "$THRESHOLD" ]; then
  exit 0
fi

echo "[$(date -u)] MEMORY.md at ${SIZE}/${CAPACITY} chars (>85%), consolidating..." >> "$LOG"

export PATH="/usr/local/bin:/home/opc/.local/bin:$PATH"

# Step 1: reflect + retain on hermes bank (Hermes personal memory)
REFLECT_OUTPUT=$(hermes -z "Run reflect on bank hermes with query 'synthesize all MEMORY.md heuristics into structured observations' then retain the results" 2>&1)
echo "  Reflect+retain: $REFLECT_OUTPUT" >> "$LOG"

# Step 2: Clear the buffer. Leave a recall instruction so Hermes restores
# context from Hindsight on the next session.
cat > "$MEMORY_FILE" << 'HEADER'
# MEMORY: Transferable Heuristics

> Append-only repository. Buffer was consolidated to bank `hermes` via reflect+retain.
> Session init already runs `recall(bank="hermes")` — consolidated heuristics restore automatically.

HEADER

echo "[$(date -u)] Consolidation complete. Buffer cleared." >> "$LOG"
