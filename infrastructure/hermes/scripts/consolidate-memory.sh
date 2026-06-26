#!/usr/bin/env bash
# consolidate-memory.sh — Monitor MEMORY.md size, trigger reflect+retain at threshold
# Ran by cron. If MEMORY.md exceeds 80% of capacity (~1760 chars), runs reflect+retain
# on the toolset bank via Hermes one-shot mode, then clears the memory buffer.
set -euo pipefail

MEMORY_FILE="${HERMES_HOME:-/home/opc/.hermes}/memories/MEMORY.md"
CAPACITY=2200
THRESHOLD=$((CAPACITY * 80 / 100))
LOG="/var/log/hermes-memory-consolidation.log"

if [ ! -f "$MEMORY_FILE" ]; then
  echo "[$(date -u)] MEMORY.md not found at $MEMORY_FILE" >> "$LOG"
  exit 0
fi

SIZE=$(wc -c < "$MEMORY_FILE" 2>/dev/null || echo 0)
if [ "$SIZE" -lt "$THRESHOLD" ]; then
  exit 0
fi

echo "[$(date -u)] MEMORY.md at ${SIZE}/${CAPACITY} chars (>80%), consolidating..." >> "$LOG"

export PATH="/usr/local/bin:/home/opc/.local/bin:$PATH"

# Step 1: reflect + retain on toolset bank
REFLECT_OUTPUT=$(hermes -z "Run reflect on bank toolset with query 'synthesize all MEMORY.md heuristics into structured observations' then retain the results" 2>&1)
echo "  Reflect+retain: $REFLECT_OUTPUT" >> "$LOG"

# Step 2: Clear the buffer (truncate to header only)
HEADER=$(head -5 "$MEMORY_FILE")
cat > "$MEMORY_FILE" << 'HEADER'
# MEMORY: Transferable Heuristics

> Append-only repository of patterns and lessons applicable to any software project.

HEADER

echo "[$(date -u)] Consolidation complete. Buffer cleared." >> "$LOG"
