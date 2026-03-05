#!/bin/bash
# deep.sh — Deep analysis using proven cognitive lenses
#
# Portfolio of 6 champion lenses (9-9.5/10 on Haiku):
#   pedagogy  — What patterns does this teach? What breaks when someone copies them?
#   claim     — What claims does this embed? What if they're false?
#   scarcity  — What does this assume will never run out?
#   rejected  — What alternatives were rejected? What invisible problems would they create?
#   decay     — What degrades silently over time?
#   contract  — Interface promises vs implementation reality
#
# Usage:
#   ./deep.sh file.py                         # Auto-select best lens
#   ./deep.sh file.py "security risks?"       # Auto-select with question
#   ./deep.sh -l pedagogy file.py             # Specific lens
#   ./deep.sh -l all file.py                  # Run ALL 5 lenses
#   cat essay.txt | ./deep.sh                 # Pipe content
#   ./deep.sh -v -l claim doc.md              # Verbose (show lens selection)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LENS_DIR="$SCRIPT_DIR/lenses"
MODEL="${DEEP_MODEL:-haiku}"
LENS=""
VERBOSE=0

# Available lenses
LENSES=(pedagogy claim scarcity rejected_paths degradation contract)

# Parse flags
while [[ $# -gt 0 && "$1" == -* ]]; do
    case "$1" in
        -v|--verbose) VERBOSE=1; shift ;;
        -m|--model) MODEL="$2"; shift 2 ;;
        -l|--lens) LENS="$2"; shift 2 ;;
        -h|--help)
            echo "deep.sh — Deep analysis using proven cognitive lenses"
            echo ""
            echo "Usage: deep.sh [-v] [-m model] [-l lens] [file] [question]"
            echo ""
            echo "Lenses:"
            echo "  pedagogy       What patterns does this teach others? (champion, 9.5/10)"
            echo "  claim          What empirical claims does this embed?"
            echo "  scarcity       What does this assume will never run out?"
            echo "  rejected_paths What rejected alternatives would create invisible problems?"
            echo "  degradation    What degrades silently over time?"
            echo "  contract       Interface promises vs implementation reality"
            echo "  all            Run ALL 6 lenses (comprehensive)"
            echo "  (omit)         Auto-select best lens for input"
            echo ""
            echo "Options:"
            echo "  -v, --verbose   Show lens selection and prompts"
            echo "  -m, --model     Model for analysis (default: haiku)"
            echo "  -l, --lens      Choose lens (default: auto-select)"
            echo ""
            echo "Examples:"
            echo "  ./deep.sh code.py"
            echo "  ./deep.sh -l all code.py 'what could go wrong?'"
            echo "  ./deep.sh -l claim policy.md 'is this sound?'"
            echo "  cat contract.txt | ./deep.sh -l scarcity"
            exit 0
            ;;
        *) echo "Unknown option: $1. Use --help for usage."; exit 1 ;;
    esac
done

# Read input
INPUT=""
QUESTION=""

if [ $# -ge 1 ] && [ -f "$1" ]; then
    INPUT="$(cat "$1")"
    QUESTION="${2:-Analyze this deeply. What structural patterns and problems do you see?}"
elif [ $# -ge 1 ]; then
    INPUT="$1"
    QUESTION="${2:-Analyze this deeply. What structural patterns and problems do you see?}"
elif [ ! -t 0 ]; then
    INPUT="$(cat)"
    QUESTION="${1:-Analyze this deeply. What structural patterns and problems do you see?}"
else
    echo "Error: No input provided. Pass a file, text, or pipe content." >&2
    echo "Run ./deep.sh --help for usage." >&2
    exit 1
fi

# Function: run a single lens
run_lens() {
    local lens_name="$1"
    local lens_file="$LENS_DIR/${lens_name}.md"

    if [ ! -f "$lens_file" ]; then
        echo "Error: Lens '$lens_name' not found at $lens_file" >&2
        return 1
    fi

    CLAUDECODE= claude -p --model "$MODEL" --output-format text \
        --system-prompt-file "$lens_file" \
        "$QUESTION

$INPUT" < /dev/null
}

# Auto-select lens
auto_select() {
    local selector_prompt="You are a lens selector. Given content and a question, reply with ONLY the single best lens name from: pedagogy, claim, scarcity, rejected_paths, degradation, contract. No explanation, just the lens name."

    local preview
    # Send first 500 chars of input + question to selector
    preview="${INPUT:0:500}"

    local selected
    selected=$(CLAUDECODE= claude -p --model haiku --output-format text \
        --append-system-prompt "$selector_prompt" \
        "Question: $QUESTION

Content (preview): $preview" < /dev/null 2>/dev/null)

    # Clean the response — extract just the lens name
    selected=$(echo "$selected" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')

    # Validate
    local valid=0
    for l in "${LENSES[@]}"; do
        if [[ "$selected" == "$l" ]]; then
            valid=1
            break
        fi
    done

    if [ $valid -eq 0 ]; then
        # Check partial matches
        case "$selected" in
            *pedagogy*) selected="pedagogy" ;;
            *claim*) selected="claim" ;;
            *scarci*) selected="scarcity" ;;
            *reject*) selected="rejected_paths" ;;
            *degrad*|*decay*) selected="degradation" ;;
            *contract*|*interface*) selected="contract" ;;
            *) selected="pedagogy" ;;  # Default to champion
        esac
    fi

    echo "$selected"
}

# Main execution
if [ "$LENS" = "all" ]; then
    # Run all 6 lenses in parallel
    echo "Running all 6 lenses on $MODEL..." >&2
    echo "" >&2

    TMPDIR_DEEP=$(mktemp -d)

    for l in "${LENSES[@]}"; do
        (
            echo "  Starting: $l" >&2
            run_lens "$l" > "$TMPDIR_DEEP/$l.md" 2>/dev/null
            echo "  Done: $l" >&2
        ) &
    done
    wait

    # Output all results with headers
    for l in "${LENSES[@]}"; do
        echo ""
        echo "================================================================"
        echo "  LENS: $l"
        echo "================================================================"
        echo ""
        if [ -f "$TMPDIR_DEEP/$l.md" ] && [ -s "$TMPDIR_DEEP/$l.md" ]; then
            cat "$TMPDIR_DEEP/$l.md"
        else
            echo "(No output from $l lens)"
        fi
    done

    rm -rf "$TMPDIR_DEEP"

elif [ -n "$LENS" ]; then
    # Run specific lens
    if [ $VERBOSE -eq 1 ]; then
        echo "Lens: $LENS" >&2
        echo "Model: $MODEL" >&2
        echo "Prompt:" >&2
        cat "$LENS_DIR/${LENS}.md" >&2
        echo "" >&2
        echo "---" >&2
    fi

    run_lens "$LENS"

else
    # Auto-select
    echo "Selecting best lens..." >&2
    SELECTED=$(auto_select)

    if [ $VERBOSE -eq 1 ]; then
        echo "Selected: $SELECTED" >&2
        echo "Prompt:" >&2
        cat "$LENS_DIR/${SELECTED}.md" >&2
        echo "" >&2
        echo "---" >&2
    else
        echo "Selected: $SELECTED" >&2
    fi
    echo "" >&2

    run_lens "$SELECTED"
fi
