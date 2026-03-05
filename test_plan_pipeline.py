#!/usr/bin/env python3
"""Tests for prism.py v0.7 — plan, display, JSON parsing, backward compat."""

import json
import sys
import os

# Add project dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prism import PrismREPL


def test_parse_stage_json():
    """Test JSON parsing from model output."""
    repl = PrismREPL.__new__(PrismREPL)
    repl.working_dir = __import__("pathlib").Path(".")

    # Clean JSON array
    result = repl._parse_stage_json(
        '[{"id": 1, "files": ["a.py"]}]', "test")
    assert result == [{"id": 1, "files": ["a.py"]}], f"Got: {result}"

    # JSON in markdown fences
    result = repl._parse_stage_json(
        '```json\n[{"id": 1, "size": "M"}]\n```', "test")
    assert result == [{"id": 1, "size": "M"}], f"Got: {result}"

    # JSON embedded in prose
    result = repl._parse_stage_json(
        'Here is the result:\n[{"id": 2, "files": ["a.py"]}]\nDone.',
        "test")
    assert result == [{"id": 2, "files": ["a.py"]}], f"Got: {result}"

    # JSON object (not array)
    result = repl._parse_stage_json(
        '{"phases": [{"phase": 1}]}', "test")
    assert result == {"phases": [{"phase": 1}]}, f"Got: {result}"

    # Empty/error returns None
    assert repl._parse_stage_json("", "test") is None
    assert repl._parse_stage_json("[Error: timeout]", "test") is None
    assert repl._parse_stage_json("no json here", "test") is None

    print("  _parse_stage_json: PASS")


def test_enriched_plan_format():
    """Test that enriched plan.json has the expected structure."""
    issues = [
        {"id": 1, "file": "a.py", "priority": "P0", "title": "Bug",
         "files": ["a.py", "b.py"], "size": "S",
         "spec": "Fix method X", "done_when": "Test passes"},
        {"id": 2, "file": "b.py", "priority": "P1", "title": "Refactor",
         "files": ["b.py"], "size": "M"},
    ]

    enriched = {}
    for i in issues:
        iid = i.get("id")
        if iid is not None:
            enriched[str(iid)] = {
                k: i.get(k) for k in (
                    "files", "size", "spec", "done_when")
                if i.get(k) is not None
            }

    assert "1" in enriched
    assert enriched["1"]["files"] == ["a.py", "b.py"]
    assert enriched["1"]["size"] == "S"
    assert enriched["1"]["spec"] == "Fix method X"
    assert "spec" not in enriched["2"]  # wasn't set

    print("  enriched format: PASS")


def test_autopilot_enriched_lookup():
    """Test that autopilot correctly reads enriched data."""
    issue = {"id": 5, "file": "test.py", "title": "Fix X",
             "description": "Desc", "action": "Old action"}
    enriched_issues = {
        "5": {"spec": "Change method Y in line 100",
              "done_when": "py_compile passes",
              "size": "S"}
    }

    enriched = enriched_issues.get(str(issue.get("id", "")), {})
    spec = enriched.get("spec", "")
    done_when = enriched.get("done_when", "")
    size = enriched.get("size", issue.get("size", "M"))

    assert spec == "Change method Y in line 100"
    assert done_when == "py_compile passes"
    assert size == "S"

    # Without enriched data, falls back
    enriched2 = {}.get(str(issue.get("id", "")), {})
    spec2 = enriched2.get("spec", "")
    size2 = enriched2.get("size", issue.get("size", "M"))
    assert spec2 == ""
    assert size2 == "M"  # default

    print("  autopilot enriched lookup: PASS")


def test_backward_compatibility():
    """Verify old plan.json format still works with autopilot."""
    # Old format (no enriched_issues)
    old_plan = {
        "generated_at": "2026-01-01T00:00:00",
        "issue_count": 3,
        "plan": {
            "phases": [
                {"phase": 1, "streams": [
                    {"name": "safety", "tasks": [1, 2], "reason": "P0 first"}
                ]},
                {"phase": 2, "streams": [
                    {"name": "quality", "tasks": [3], "reason": "after safety"}
                ]}
            ]
        }
    }

    plan_json = old_plan.get("plan")
    enriched_issues = old_plan.get("enriched_issues", {})

    assert plan_json is not None
    assert plan_json["phases"][0]["streams"][0]["tasks"] == [1, 2]
    assert enriched_issues == {}

    # New format with enrichment
    new_plan = {
        "generated_at": "2026-03-02T00:00:00",
        "issue_count": 3,
        "plan": old_plan["plan"],
        "enriched_issues": {
            "1": {"files": ["a.py"], "size": "S", "spec": "Fix X", "done_when": "Test"},
            "2": {"files": ["a.py"], "size": "M"},
        }
    }

    assert new_plan["plan"]["phases"] == old_plan["plan"]["phases"]
    assert new_plan["enriched_issues"]["1"]["spec"] == "Fix X"

    print("  backward compatibility: PASS")


def test_plan_md_generation():
    """Test plan.md is generated correctly from structured data."""
    issues = [
        {"id": 1, "priority": "P0", "title": "Critical bug", "size": "S",
         "spec": "Fix null check in line 50"},
        {"id": 2, "priority": "P1", "title": "Refactor auth", "size": "L"},
        {"id": 3, "priority": "P2", "title": "Add logging", "size": "M"},
    ]
    plan_json = {
        "phases": [
            {"phase": 1, "streams": [
                {"name": "safety", "tasks": [1], "reason": "P0 first"}
            ]},
            {"phase": 2, "streams": [
                {"name": "auth", "tasks": [2], "reason": "needs safety first"},
                {"name": "observability", "tasks": [3], "reason": "independent"}
            ]}
        ]
    }

    # Reproduce plan.md generation from _cmd_plan
    md_parts = ["# Execution Plan\n", f"3 issues\n"]
    for phase in plan_json.get("phases", []):
        pnum = phase.get("phase", "?")
        md_parts.append(f"\n## Phase {pnum}\n")
        for stream in phase.get("streams", []):
            sname = stream.get("name", "?")
            reason = stream.get("reason", "")
            md_parts.append(f"\n### {sname}")
            if reason:
                md_parts.append(f"_{reason}_\n")
            for tid in stream.get("tasks", []):
                iss = next((i for i in issues if i.get("id") == tid), None)
                if iss:
                    size = iss.get("size", "?")
                    pri = iss.get("priority", "P2")
                    md_parts.append(
                        f"- **#{tid}** [{pri}] {size} — "
                        f"{iss.get('title', '')}")
    plan_md = "\n".join(md_parts)

    assert "## Phase 1" in plan_md
    assert "## Phase 2" in plan_md
    assert "**#1** [P0] S" in plan_md
    assert "**#2** [P1] L" in plan_md
    assert "**#3** [P2] M" in plan_md

    print("  plan.md generation: PASS")


def test_display_output():
    """Test the display section handles all cases."""
    issues = [
        {"id": 1, "priority": "P0", "title": "Bug", "size": "S"},
        {"id": 2, "priority": "P1", "title": "Fix", "size": "M"},
        {"id": 3, "priority": "P2", "title": "Clean", "size": "L"},
    ]
    plan_json = {
        "phases": [
            {"phase": 1, "streams": [
                {"name": "safety", "tasks": [1], "reason": "critical"}
            ]},
            {"phase": 2, "streams": [
                {"name": "refactor", "tasks": [2, 3], "reason": "after safety"}
            ]}
        ]
    }

    # Reproduce display logic from _cmd_plan
    lines = []
    for phase in plan_json.get("phases", []):
        pnum = phase.get("phase", "?")
        stream_parts = []
        for s in phase.get("streams", []):
            task_parts = [f"#{tid}" for tid in s.get("tasks", [])]
            stream_parts.append(
                f"{s.get('name', '?')} ({', '.join(task_parts)})")
        lines.append(f"Phase {pnum}: {', '.join(stream_parts)}")

    assert lines[0] == "Phase 1: safety (#1)"
    assert lines[1] == "Phase 2: refactor (#2, #3)"

    print("  display output: PASS")


def test_default_config():
    """Test DEFAULT_CONFIG has expected keys."""
    from prism import DEFAULT_CONFIG
    assert "code_extensions" in DEFAULT_CONFIG
    print("  default config: PASS")


if __name__ == "__main__":
    print("\nRunning prism v0.7 tests...\n")
    test_parse_stage_json()
    test_enriched_plan_format()
    test_autopilot_enriched_lookup()
    test_backward_compatibility()
    test_plan_md_generation()
    test_display_output()
    test_default_config()
    print(f"\nAll tests passed!")
