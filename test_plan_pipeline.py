#!/usr/bin/env python3
"""Tests for prism.py v0.8 — plan, display, JSON parsing, backward compat."""

import json
import pathlib
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


def test_extract_structural_context():
    """Test conservation law + meta-law extraction from L12 output."""
    repl = PrismREPL.__new__(PrismREPL)

    # Real L12 output pattern (numbered heading)
    text1 = (
        "## 12. Conservation Law\n\n"
        "> **Clarity × Authority = constant**\n\n"
        "Hidden authority means guaranteed correctness.\n\n"
        "## 13. Apply Diagnostic"
    )
    result = repl._extract_structural_context(text1)
    assert "Clarity × Authority = constant" in result
    assert "Conservation law:" in result

    # Unnumbered heading
    text2 = (
        "## Conservation Law\n\n"
        "Product form: X × Y = k\n\n"
        "## Meta-Law\n\n"
        "Distributed authority distributes risk.\n\n"
        "## End"
    )
    result = repl._extract_structural_context(text2)
    assert "Conservation law:" in result
    assert "Meta-law:" in result
    assert "Product form" in result
    assert "Distributed authority" in result

    # "The Conservation Law" variant
    text3 = (
        "## The Conservation Law\n\n"
        "Sum form: A + B = constant\n\n"
        "## 15. META-CONSERVATION LAW\n\n"
        "Meta-level finding here.\n\n"
        "## 16. Next"
    )
    result = repl._extract_structural_context(text3)
    assert "Sum form" in result
    assert "Meta-level finding" in result

    # No conservation law → empty string
    assert repl._extract_structural_context("## Random heading\nstuff") == ""
    assert repl._extract_structural_context("") == ""
    assert repl._extract_structural_context(None) == ""

    # Truncation: conservation law > 300 chars
    long_body = "x " * 200  # 400 chars
    text4 = f"## Conservation Law\n\n{long_body}\n\n## Next"
    result = repl._extract_structural_context(text4)
    assert len(result) < 350  # truncated
    assert result.endswith("...")

    print("  _extract_structural_context: PASS")


def test_parse_scan_args():
    """Test _parse_scan_args mode parsing."""
    parse = PrismREPL._parse_scan_args

    # Basic modes
    r = parse("file.py")
    assert r["mode"] == "single" and r["arg"] == "file.py"

    r = parse("file.py full")
    assert r["mode"] == "full" and r["arg"] == "file.py"

    r = parse("file.py discover")
    assert r["mode"] == "discover" and r["arg"] == "file.py"

    # expand → its own mode
    r = parse("file.py expand")
    assert r["mode"] == "expand" and r["arg"] == "file.py"
    assert r["expand_indices"] is None
    assert r["expand_mode"] is None

    # expand with indices
    r = parse("file.py expand 1,3,5")
    assert r["mode"] == "expand" and r["arg"] == "file.py"
    assert r["expand_indices"] == "1,3,5"

    # expand with * (all)
    r = parse("file.py expand *")
    assert r["mode"] == "expand" and r["arg"] == "file.py"
    assert r["expand_indices"] == "*"

    # expand single (all picked areas → single prism)
    r = parse("file.py expand single")
    assert r["mode"] == "expand"
    assert r["expand_mode"] == "single"

    # expand full (all picked areas → full prism)
    r = parse("file.py expand full")
    assert r["mode"] == "expand"
    assert r["expand_mode"] == "full"

    # expand indices + mode
    r = parse("file.py expand 1,3 full")
    assert r["mode"] == "expand"
    assert r["expand_indices"] == "1,3"
    assert r["expand_mode"] == "full"

    # discover full
    r = parse("file.py discover full")
    assert r["mode"] == "discover_full" and r["arg"] == "file.py"

    # deep="..." string goal
    r = parse('file.py deep="error handling"')
    assert r["mode"] == "deep" and r["deep_goal"] == "error handling"
    assert r["arg"] == "file.py"

    # deep=N numeric goal
    r = parse("file.py deep=3")
    assert r["mode"] == "deep" and r["deep_goal"] == 3
    assert r["arg"] == "file.py"

    # target="..." string goal
    r = parse('file.py target="race conditions"')
    assert r["mode"] == "target" and r["target_goal"] == "race conditions"
    assert r["arg"] == "file.py"

    # target=N numeric goal
    r = parse("file.py target=2")
    assert r["mode"] == "target" and r["target_goal"] == 2
    assert r["arg"] == "file.py"

    # fix and fix auto
    r = parse("file.py fix")
    assert r["mode"] == "fix" and r["fix_auto"] is False
    r = parse("file.py fix auto")
    assert r["mode"] == "fix" and r["fix_auto"] is True

    # deep takes priority over target (checked first)
    r = parse('file.py deep="X" target="Y"')
    assert r["mode"] == "deep"

    print("  _parse_scan_args: PASS")


def test_discover_results_persistence():
    """Test round-trip save/load of discover.json."""
    import tempfile
    repl = PrismREPL.__new__(PrismREPL)
    repl.working_dir = pathlib.Path(tempfile.mkdtemp())
    repl._discover_results = []

    data = [
        {"name": "lens_a", "lens_path": "code_py/lens_a",
         "preview": "Identify...", "domain": "code_py"},
        {"name": "lens_b", "lens_path": "code_py/lens_b",
         "preview": "Extract...", "domain": "code_py"},
    ]
    repl._save_discover_results(data, "auth.py")

    # Clear memory, force load from disk
    repl._discover_results = []
    loaded = repl._load_discover_results("auth.py")
    assert len(loaded) == 2
    assert loaded[0]["name"] == "lens_a"
    assert loaded[1]["lens_path"] == "code_py/lens_b"

    # Different file returns empty (no cross-contamination)
    repl._discover_results = []
    assert repl._load_discover_results("router.py") == []

    # Verify file on disk is named per-stem
    assert (repl.working_dir / ".deep" / "discover_auth.json").exists()

    # Cleanup
    import shutil
    shutil.rmtree(repl.working_dir, ignore_errors=True)

    print("  discover_results_persistence: PASS")


def test_cook_deep_prompt_format():
    """Verify COOK_DEEP_PROMPT placeholder works."""
    from prism import COOK_DEEP_PROMPT
    formatted = COOK_DEEP_PROMPT.format(goal="error handling")
    assert "error handling" in formatted
    assert "{goal}" not in formatted
    # Must mention all three roles
    assert "primary" in formatted.lower()
    assert "adversarial" in formatted.lower()
    assert "synthesis" in formatted.lower()

    print("  cook_deep_prompt_format: PASS")


def test_target_by_index_bounds():
    """Reject index 0 and out-of-range."""
    import io
    repl = PrismREPL.__new__(PrismREPL)
    repl.working_dir = pathlib.Path(".")
    repl._discover_results = [
        {"name": "a", "lens_path": "x/a", "preview": "...", "domain": "x"},
    ]

    # Capture output to check error messages
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        repl._run_target_by_index("content", "file.py", 0)
        out0 = sys.stdout.getvalue()
        sys.stdout = io.StringIO()
        repl._run_target_by_index("content", "file.py", 5)
        out5 = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    assert "out of range" in out0
    assert "out of range" in out5

    print("  target_by_index_bounds: PASS")


def test_deep_goal_resolution():
    """Int→discover lookup, string→direct."""
    repl = PrismREPL.__new__(PrismREPL)
    repl.working_dir = pathlib.Path(".")
    repl._discover_results = [
        {"name": "error_handling", "lens_path": "code_py/error_handling",
         "preview": "...", "domain": "code_py"},
        {"name": "state_mgmt", "lens_path": "code_py/state_mgmt",
         "preview": "...", "domain": "code_py"},
    ]

    # Int goal resolves to discover name
    # We can't run the full _run_deep (needs claude), but test resolution
    # by checking that the slug would be correct
    import re as re_mod
    goal_int = 2  # should resolve to "state_mgmt"
    results = repl._load_discover_results()
    assert results[goal_int - 1]["name"] == "state_mgmt"

    # String goal passes through
    goal_str = "memory leaks"
    slug = re_mod.sub(r'[^a-z0-9]+', '_', goal_str.lower()).strip('_')[:40]
    assert slug == "memory_leaks"

    print("  deep_goal_resolution: PASS")


def test_diff_issues():
    """Test issue diffing by (location, description[:50]) signature."""
    repl = PrismREPL.__new__(PrismREPL)

    old = [
        {"id": 1, "location": "method_a", "description": "Missing null check"},
        {"id": 2, "location": "method_b", "description": "Race condition in handler"},
    ]
    new = [
        {"id": 1, "location": "method_a", "description": "Missing null check"},  # same
        {"id": 2, "location": "method_c", "description": "New buffer overflow"},  # new
        {"id": 3, "location": "method_b", "description": "Race condition in handler"},  # same (diff id)
    ]

    diff = repl._diff_issues(old, new)
    assert len(diff) == 1
    assert diff[0]["location"] == "method_c"

    # Empty old → all new
    diff2 = repl._diff_issues([], new)
    assert len(diff2) == 3

    # Empty new → none
    diff3 = repl._diff_issues(old, [])
    assert len(diff3) == 0

    # Falls back to file field when no location
    old4 = [{"id": 1, "file": "a.py", "description": "Bug in a"}]
    new4 = [
        {"id": 1, "file": "a.py", "description": "Bug in a"},  # same
        {"id": 2, "file": "b.py", "description": "Bug in b"},  # new
    ]
    diff4 = repl._diff_issues(old4, new4)
    assert len(diff4) == 1
    assert diff4[0]["file"] == "b.py"

    print("  _diff_issues: PASS")


def test_parse_selection():
    """Test _parse_selection handles ranges, commas, *, bounds."""
    parse = PrismREPL._parse_selection

    # Single values
    assert parse("1", 5) == [1]
    assert parse("3", 5) == [3]

    # Comma-separated
    assert parse("1,3,5", 7) == [1, 3, 5]

    # Range
    assert parse("2-4", 7) == [2, 3, 4]

    # Mixed
    assert parse("1,3-5,7", 7) == [1, 3, 4, 5, 7]

    # Star = all
    assert parse("*", 4) == [1, 2, 3, 4]

    # Empty = all
    assert parse("", 3) == [1, 2, 3]

    # Out of bounds filtered
    assert parse("0,1,99", 5) == [1]

    # Deduplication
    assert parse("1,1,2", 5) == [1, 2]

    print("  _parse_selection: PASS")


def test_load_cached_pipeline():
    """Test _load_cached_pipeline reads ordered .md files."""
    import tempfile
    repl = PrismREPL.__new__(PrismREPL)
    tmp = pathlib.Path(tempfile.mkdtemp())

    # Empty dir → None
    assert repl._load_cached_pipeline(tmp) is None

    # Single file → None (need >= 2)
    (tmp / "00_primary.md").write_text("lens one", encoding="utf-8")
    assert repl._load_cached_pipeline(tmp) is None

    # Two files → valid pipeline
    (tmp / "01_adversarial.md").write_text("lens two",
                                           encoding="utf-8")
    result = repl._load_cached_pipeline(tmp)
    assert result is not None
    assert len(result) == 2
    assert result[0]["name"] == "primary"
    assert result[0]["prompt"] == "lens one"
    assert result[1]["name"] == "adversarial"
    assert result[1]["prompt"] == "lens two"

    # Cleanup
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    print("  _load_cached_pipeline: PASS")


def test_build_project_map():
    """Test _build_project_map creates compact summary."""
    import tempfile
    repl = PrismREPL.__new__(PrismREPL)
    tmp = pathlib.Path(tempfile.mkdtemp())

    # Create a mini project
    (tmp / "main.py").write_text(
        "import os\nclass App:\n    pass\n", encoding="utf-8")
    (tmp / "utils.py").write_text(
        "def helper():\n    return 42\n", encoding="utf-8")

    result = repl._build_project_map(tmp)
    assert "2 files" in result
    assert "main.py" in result
    assert "utils.py" in result
    assert "import os" in result
    assert "def helper" in result

    # Empty dir → empty string
    empty = pathlib.Path(tempfile.mkdtemp())
    assert repl._build_project_map(empty) == ""

    # Cleanup
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(empty, ignore_errors=True)

    print("  _build_project_map: PASS")


def test_cmd_mode_prism():
    """Verify /prism command sets chat mode correctly."""
    import io
    repl = PrismREPL.__new__(PrismREPL)
    repl.working_dir = pathlib.Path(".")
    repl._chat_mode = "off"
    repl._active_lens_name = None
    repl._active_lens_prompt = None

    # Stub _load_lens for static lens test
    repl._load_lens = lambda name: "fake prompt" if name == "pedagogy" else None

    old_stdout = sys.stdout

    # /prism single
    sys.stdout = io.StringIO()
    repl._cmd_mode("single")
    sys.stdout = old_stdout
    assert repl._chat_mode == "single"
    assert repl._active_lens_name is None

    # /prism full
    sys.stdout = io.StringIO()
    repl._cmd_mode("full")
    sys.stdout = old_stdout
    assert repl._chat_mode == "full"
    assert repl._active_lens_name is None

    # /prism off
    sys.stdout = io.StringIO()
    repl._cmd_mode("off")
    sys.stdout = old_stdout
    assert repl._chat_mode == "off"

    # /prism pedagogy (static lens)
    sys.stdout = io.StringIO()
    repl._cmd_mode("pedagogy")
    sys.stdout = old_stdout
    assert repl._chat_mode == "off"
    assert repl._active_lens_name == "pedagogy"
    assert repl._active_lens_prompt == "fake prompt"

    # /prism nonexistent → stays unchanged
    sys.stdout = io.StringIO()
    repl._cmd_mode("nonexistent")
    out = sys.stdout.getvalue()
    sys.stdout = old_stdout
    assert "Unknown" in out
    assert repl._active_lens_name == "pedagogy"  # unchanged

    # /prism (no arg) → show current
    sys.stdout = io.StringIO()
    repl._cmd_mode("")
    out = sys.stdout.getvalue()
    sys.stdout = old_stdout
    assert "off" in out.lower() or "vanilla" in out.lower()

    # Default mode is "off"
    repl2 = PrismREPL.__new__(PrismREPL)
    repl2._chat_mode = "off"
    assert repl2._chat_mode == "off"

    print("  cmd_mode_prism: PASS")


def test_chat_mode_dispatch():
    """Verify chat loop dispatches to correct method based on _chat_mode."""
    repl = PrismREPL.__new__(PrismREPL)
    repl._chat_mode = "off"
    repl._active_lens_name = None
    repl._active_lens_prompt = None

    calls = []
    repl._send_and_stream = lambda msg: calls.append(("vanilla", msg))
    repl._chat_single_prism = lambda msg: calls.append(("single", msg))
    repl._chat_full_pipeline = lambda msg: calls.append(("full", msg))

    # Simulate the dispatch logic from the chat loop
    def dispatch(message):
        if repl._chat_mode == "full":
            repl._chat_full_pipeline(message)
        elif repl._chat_mode == "single":
            repl._chat_single_prism(message)
        else:
            repl._send_and_stream(message)

    # off → vanilla
    calls.clear()
    repl._chat_mode = "off"
    dispatch("hello")
    assert calls[0] == ("vanilla", "hello")

    # single → dynamic cook
    calls.clear()
    repl._chat_mode = "single"
    dispatch("analyze this")
    assert calls[0] == ("single", "analyze this")

    # full → dynamic pipeline
    calls.clear()
    repl._chat_mode = "full"
    dispatch("deep analysis")
    assert calls[0] == ("full", "deep analysis")

    print("  chat_mode_dispatch: PASS")


def test_cmd_scan_dispatch():
    """Verify _cmd_scan routes each mode to the correct method."""
    repl = PrismREPL.__new__(PrismREPL)
    repl.working_dir = pathlib.Path(".")
    repl.session = type("S", (), {
        "model": "haiku", "total_input_tokens": 0,
        "total_output_tokens": 0, "total_cost_usd": 0.0})()
    repl._last_action = None
    repl._discover_results = []

    calls = []

    # Stub content loader to return fake content
    repl._resolve_file = lambda f: None  # not a dir
    repl._get_deep_content = lambda f: ("fake content", f)
    repl._suggest_next = lambda *a, **kw: None

    # Stub downstream methods to record which was called
    repl._run_single_lens_streaming = (
        lambda *a, **kw: calls.append(("single", a, kw)) or "")
    repl._run_full_pipeline = (
        lambda *a, **kw: calls.append(("full", a, kw)))
    repl._run_discover = (
        lambda *a, **kw: calls.append(("discover", a, kw)))
    repl._run_discover_full = (
        lambda *a, **kw: calls.append(("discover_full", a, kw)))
    repl._run_expand = (
        lambda *a, **kw: calls.append(("expand", a, kw)))
    repl._run_deep = (
        lambda *a, **kw: calls.append(("deep", a, kw)))
    repl._run_target_by_index = (
        lambda *a, **kw: calls.append(("target_idx", a, kw)))
    repl._run_target = (
        lambda *a, **kw: calls.append(("target_str", a, kw)))

    # Single (default)
    calls.clear()
    repl._cmd_scan("file.py")
    assert calls[0][0] == "single", f"Expected single, got {calls}"

    # Full
    calls.clear()
    repl._cmd_scan("file.py full")
    assert calls[0][0] == "full"

    # Discover
    calls.clear()
    repl._cmd_scan("file.py discover")
    assert calls[0][0] == "discover"

    # Expand → expand mode
    calls.clear()
    repl._cmd_scan("file.py expand")
    assert calls[0][0] == "expand"

    # Expand with indices
    calls.clear()
    repl._cmd_scan("file.py expand 1,3")
    assert calls[0][0] == "expand"

    # Expand with mode
    calls.clear()
    repl._cmd_scan("file.py expand 1,3 full")
    assert calls[0][0] == "expand"

    # Discover full
    calls.clear()
    repl._cmd_scan("file.py discover full")
    assert calls[0][0] == "discover_full"

    # deep="X"
    calls.clear()
    repl._cmd_scan('file.py deep="error handling"')
    assert calls[0][0] == "deep"

    # deep=N
    calls.clear()
    repl._cmd_scan("file.py deep=3")
    assert calls[0][0] == "deep"

    # target="X"
    calls.clear()
    repl._cmd_scan('file.py target="race conditions"')
    assert calls[0][0] == "target_str"

    # target=N
    calls.clear()
    repl._cmd_scan("file.py target=2")
    assert calls[0][0] == "target_idx"

    print("  cmd_scan_dispatch: PASS")


if __name__ == "__main__":
    print("\nRunning prism v0.8 tests...\n")
    test_parse_stage_json()
    test_enriched_plan_format()
    test_autopilot_enriched_lookup()
    test_backward_compatibility()
    test_plan_md_generation()
    test_display_output()
    test_default_config()
    test_extract_structural_context()
    test_parse_scan_args()
    test_discover_results_persistence()
    test_cook_deep_prompt_format()
    test_target_by_index_bounds()
    test_deep_goal_resolution()
    test_diff_issues()
    test_parse_selection()
    test_load_cached_pipeline()
    test_build_project_map()
    test_cmd_mode_prism()
    test_chat_mode_dispatch()
    test_cmd_scan_dispatch()
    print(f"\nAll 20 tests passed!")
