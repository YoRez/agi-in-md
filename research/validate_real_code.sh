#!/bin/bash
# Test portfolio lenses on real production code (Starlette routing.py)
# Also run vanilla Sonnet and Opus for head-to-head comparison
# Usage: bash research/validate_real_code.sh

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$PROJECT_DIR/output/round28_validation"
LENSES_DIR="$PROJECT_DIR/lenses"
CODE_FILE="$PROJECT_DIR/research/real_code_starlette.py"

export CLAUDECODE=""

TASK_PREFIX="Analyze this production code from Starlette's routing module. What patterns and problems do you see?"

# Build the full task: prefix + code
TASK="$TASK_PREFIX

\`\`\`python
$(cat "$CODE_FILE")
\`\`\`"

run_lens() {
    local lens_name="$1"
    local lens_file="$LENSES_DIR/${lens_name}.md"
    local outfile="$OUTPUT_DIR/haiku_${lens_name}_starlette.md"

    echo "Starting Haiku + $lens_name..."
    echo "$TASK" | claude -p \
        --model haiku \
        --system-prompt "$(cat "$lens_file")" \
        > "$outfile" 2>/dev/null
    echo "Done: Haiku + $lens_name ($(wc -c < "$outfile") bytes)"
}

run_vanilla() {
    local model="$1"
    local outfile="$OUTPUT_DIR/${model}_vanilla_starlette.md"

    echo "Starting $model vanilla..."
    echo "$TASK" | claude -p \
        --model "$model" \
        > "$outfile" 2>/dev/null
    echo "Done: $model vanilla ($(wc -c < "$outfile") bytes)"
}

# Run all 7 in parallel
run_lens "pedagogy" &
run_lens "claim" &
run_lens "scarcity" &
run_lens "rejected_paths" &
run_lens "degradation" &
run_vanilla "sonnet" &
run_vanilla "opus" &

wait
echo ""
echo "All 7 runs complete."
echo "Output in: $OUTPUT_DIR/"
ls -la "$OUTPUT_DIR/"*starlette*
