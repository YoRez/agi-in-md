#!/bin/bash
# reflexive_matrix.sh — Run every lens on every lens (5x5 = 25 experiments)
# Each lens analyzes each lens file as its target artifact.
# All 25 run in parallel on Haiku.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
LENS_DIR="$ROOT/lenses"
OUT_DIR="$ROOT/output/reflexive"
MODEL="${1:-haiku}"

LENSES=(pedagogy claim scarcity rejected_paths degradation)

mkdir -p "$OUT_DIR"

echo "=== Reflexive Matrix: ${#LENSES[@]}x${#LENSES[@]} = $((${#LENSES[@]} * ${#LENSES[@]})) experiments ==="
echo "Model: $MODEL"
echo "Output: $OUT_DIR/"
echo ""

PIDS=()
COUNT=0

for target in "${LENSES[@]}"; do
    for analyzer in "${LENSES[@]}"; do
        COUNT=$((COUNT + 1))
        OUTFILE="$OUT_DIR/${analyzer}_ON_${target}.md"

        SYSTEM_PROMPT="$(cat "$LENS_DIR/${analyzer}.md")"
        TARGET_TEXT="$(cat "$LENS_DIR/${target}.md")"

        if [ "$analyzer" = "$target" ]; then
            QUESTION="Apply this lens to itself — the artifact below IS the ${target} lens prompt. What patterns/assumptions/resources/paths/decay does it contain? What breaks when someone internalizes them for a different purpose?"
        else
            QUESTION="Analyze this artifact — it is the '${target}' cognitive lens prompt, a system prompt designed to activate specific reasoning in AI models. Apply your full analytical framework to it."
        fi

        (
            echo "  [$COUNT/25] $analyzer → $target" >&2
            CLAUDECODE= claude -p --model "$MODEL" --output-format text \
                --system-prompt "$SYSTEM_PROMPT" \
                "$QUESTION

---
ARTIFACT: ${target} lens prompt
---
$TARGET_TEXT
---" < /dev/null > "$OUTFILE" 2>/dev/null
            echo "  [$COUNT/25] DONE: $analyzer → $target ($(wc -w < "$OUTFILE") words)" >&2
        ) &
        PIDS+=($!)
    done
done

echo "Launched $COUNT experiments. Waiting..."
echo ""

# Wait for all
FAILED=0
for pid in "${PIDS[@]}"; do
    if ! wait "$pid"; then
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "=== Complete: $((COUNT - FAILED))/$COUNT succeeded ==="
echo ""

# Summary matrix
echo "Word counts (analyzer → target):"
printf "%-18s" ""
for t in "${LENSES[@]}"; do
    printf "%-14s" "$t"
done
echo ""

for a in "${LENSES[@]}"; do
    printf "%-18s" "$a"
    for t in "${LENSES[@]}"; do
        f="$OUT_DIR/${a}_ON_${t}.md"
        if [ -f "$f" ] && [ -s "$f" ]; then
            WC=$(wc -w < "$f")
            if [ "$a" = "$t" ]; then
                printf "%-14s" "[${WC}w]"  # diagonal = self-analysis
            else
                printf "%-14s" "${WC}w"
            fi
        else
            printf "%-14s" "FAIL"
        fi
    done
    echo ""
done
