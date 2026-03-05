#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$PROJECT_DIR/output/round28_validation"
LENSES_DIR="$PROJECT_DIR/lenses"
CODE_FILE="$PROJECT_DIR/research/real_code_tenacity.py"
export CLAUDECODE=""

TASK="Analyze this production code from Tenacity's retry module. What patterns and problems do you see?

\`\`\`python
$(cat "$CODE_FILE")
\`\`\`"

run_lens() {
    local lens_name="$1"
    echo "Starting Haiku + $lens_name on Tenacity..."
    echo "$TASK" | claude -p --model haiku --system-prompt "$(cat "$LENSES_DIR/${lens_name}.md")" \
        > "$OUTPUT_DIR/haiku_${lens_name}_tenacity.md" 2>/dev/null
    echo "Done: Haiku + $lens_name ($(wc -c < "$OUTPUT_DIR/haiku_${lens_name}_tenacity.md") bytes)"
}

run_vanilla() {
    local model="$1"
    echo "Starting $model vanilla on Tenacity..."
    echo "$TASK" | claude -p --model "$model" \
        > "$OUTPUT_DIR/${model}_vanilla_tenacity.md" 2>/dev/null
    echo "Done: $model vanilla ($(wc -c < "$OUTPUT_DIR/${model}_vanilla_tenacity.md") bytes)"
}

run_lens "pedagogy" &
run_lens "claim" &
run_lens "scarcity" &
run_lens "rejected_paths" &
run_lens "degradation" &
run_vanilla "sonnet" &
run_vanilla "opus" &

wait
echo "All 7 Tenacity runs complete."
