#!/usr/bin/env python3
"""prism.py — Structural code analysis through analytical lenses. Subscription-powered, zero dependencies."""

import argparse
import difflib
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import threading
import time


# ── Windows ANSI support ─────────────────────────────────────────────────────

if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x4)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass

# Handle non-UTF8 console encoding (Windows emoji crashes)
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass


# ── Constants & ANSI ─────────────────────────────────────────────────────────

VERSION = "0.8.0"
SESSIONS_DIR = pathlib.Path.home() / ".prism_sessions"
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
LENS_DIR = SCRIPT_DIR / "lenses"
DEFAULT_CONFIG = {
    "code_extensions": [".py", ".js", ".ts", ".go", ".rs", ".java", ".rb", ".sh"],
}
GLOBAL_SKILLS_DIR = pathlib.Path.home() / ".prism_skills"
FINDINGS_MAX_AGE_DAYS = 30     # delete .deep/findings/*.md older than this
TOOLS_FOR_FIX = "Read,Edit,Write"


ISSUE_EXTRACT_FALLBACK = (
    "You receive an L12 structural analysis. Extract only bugs fixable with a "
    "specific code change. Output a JSON array in a ```json``` code block.\n\n"
    "Find the bug section near the end: headings like \"BUG INVENTORY\", "
    "\"CONCRETE BUGS\", or a final list after \"collect every concrete bug.\" "
    "May be a table or prose.\n\n"
    "Fixable: report says \"fixable\", \"yes\", \"can be fixed\", or gives a "
    "concrete fix hint in parentheses. Skip: \"structural\", \"no\", "
    "\"not fixable\", \"by design\", \"unfixable.\"\n\n"
    "Each fixable bug:\n"
    "{\"id\": 1, \"priority\": \"P1\", \"title\": \"short title\", "
    "\"file\": \"filename.py\", \"location\": \"ClassName.method() or "
    "function_name()\", \"description\": \"what breaks and why\", "
    "\"action\": \"specific code change\"}\n\n"
    "Priority: CRITICAL/HIGH -> P1. MEDIUM -> P2. LOW/VERY LOW -> P3.\n\n"
    "Rules:\n"
    "- location must name a specific function or method, not a bare class\n"
    "- action must state a concrete fix, not \"consider redesigning\"\n"
    "- skip design observations, trade-offs, structural impossibilities\n"
    "- use Fixable? column parenthetical hint verbatim as action when present\n"
    "- infer file from the analysis target name if not stated\n"
    "- output ONLY the ```json``` block, nothing else"
)

HEAL_VERIFY_PROMPT = (
    "You are verifying a code fix. Given the ISSUE description and the "
    "CURRENT code after the fix was applied:\n"
    "1. Is the original issue fixed?\n"
    "2. Were any new problems introduced?\n\n"
    "Output format (exactly):\n"
    "VERDICT: FIXED | PARTIAL | UNFIXED\n"
    "REGRESSION: YES | NO\n"
    "DETAIL: one sentence explanation (optional)"
)


PROMPTS_DIR = SCRIPT_DIR / "prompts"

# B3 meta-cooker: few-shot reverse engineering of analytical lenses.
# Shows scored champion lenses so the model learns what works, then generates
# new domain-specific lenses.  Research proved: B3 (9.5/10) >> principle
# teaching (7/10) >> goal specification (6/10).
COOK_PROMPT = (
    "You reverse-engineer what makes analytical lenses effective by studying scored examples.\n\n"
    "These lenses are system prompts given to a cheap AI model analyzing an artifact. "
    "Each was scored by an expert.\n\n"
    'SCORED 9.5/10 (pedagogy): "Identify every explicit choice this artifact makes. '
    "For each, name the alternative it invisibly rejects. Now: design a new artifact by "
    "someone who internalized this one's patterns but faced a different problem — which "
    "rejected alternatives do they unconsciously resurrect? Show the result concretely. "
    "Trace: which transferred patterns create silent problems? Name the pedagogy law: "
    'what constraint gets transferred as assumption."\n'
    "WHY 9.5: Forces construction in a new context. Traces invisible transfer. "
    "Ends with a named law.\n\n"
    'SCORED 9/10 (claim): "Extract every empirical claim this artifact embeds about '
    "timing, causality, resources, or human behavior. For each claim, assume it is false. "
    "Trace the corruption that unfolds. Build three alternative designs, each inverting one "
    "claim. Name what each inversion reveals about the original's hidden assumptions. "
    'Predict which false claim causes the slowest, most invisible failure."\n'
    "WHY 9: Systematic claim extraction + inversion. Construction through alternatives. "
    "Testable prediction.\n\n"
    'SCORED 9/10 (scarcity): "Identify every concrete problem. For each, name the '
    "resource scarcity it exposes — what does this artifact assume will never run out? "
    "Design an alternative that gambles on opposite scarcities. Name the conservation "
    'law: what quantity is preserved across all designs?"\n'
    "WHY 9: Names hidden assumptions as scarcities. Construction via inversion. "
    "Conservation law.\n\n"
    'SCORED 7/10 (vanilla): "Analyze this for issues. Identify problems. '
    'Suggest improvements. Prioritize by impact."\n'
    "WHY 7: No construction. No chaining. Passive verbs. Produces a list, not a discovery.\n\n"
    "Study these examples. The 9+ lenses work because they: (1) chain operations, "
    "(2) force construction of alternatives, (3) name a law or invariant, "
    "(4) end with a testable prediction. Each lens is 50-80 words, imperative form.\n\n"
    "DOMAIN: {domain}\n\n"
    "Generate NEW analytical lenses for this domain. Each must exploit a DIFFERENT "
    "analytical angle. Output ONLY a JSON array:\n"
    '[{{"name": "snake_case_name", "prompt": "the lens text"}}, ...]'
)

# Variant for target= mode: generates ONE focused lens for a specific goal.
COOK_TARGET_PROMPT = (
    "You generate a focused analytical lens for a specific goal.\n\n"
    "An analytical lens is a system prompt given to an AI analyzing an artifact. "
    "Study these scored examples:\n\n"
    'SCORED 9.5/10: "Identify every explicit choice this artifact makes. For each, name the '
    "alternative it invisibly rejects. Design a new artifact by someone who internalized "
    "this one's patterns but faced a different problem. Trace which transferred patterns "
    'create silent problems. Name the pedagogy law."\n'
    'SCORED 9/10: "Extract every empirical claim this artifact embeds. For each, assume it is false. '
    "Trace the corruption. Build three alternatives, each inverting one claim. "
    'Predict which false claim causes the slowest, most invisible failure."\n\n'
    "USER GOAL: {goal}\n\n"
    "Generate ONE analytical lens laser-focused on this goal. "
    "Output ONLY a JSON object:\n"
    '{{"name": "snake_case_name", "prompt": "the lens text"}}'
)

# Variant for deep= mode: generates THREE complementary lenses (primary + adversarial + synthesis)
# for a specific area. The three lenses form a full pipeline that can be run sequentially.
COOK_DEEP_PROMPT = (
    "You generate a 3-lens analytical system for deep investigation of a specific area.\n\n"
    "An analytical lens is a system prompt given to an AI analyzing an artifact. "
    "Study these scored examples:\n\n"
    'SCORED 9.5/10: "Identify every explicit choice. Name the alternative each invisibly rejects. '
    "Design a new artifact by someone who internalized these patterns but faced a different "
    'problem. Trace which transferred patterns create silent problems. Name the pedagogy law."\n'
    'SCORED 9/10: "Extract every empirical claim about timing, causality, resources, or behavior. '
    "Assume each is false. Trace the corruption. Build three alternatives inverting one claim each. "
    'Predict which false claim causes the slowest, most invisible failure."\n\n'
    "The three lenses form a pipeline:\n"
    "- PRIMARY: structural analysis — find what the area conceals\n"
    "- ADVERSARIAL: receive the primary analysis, try to break it\n"
    "- SYNTHESIS: receive both, resolve contradictions, produce a corrected finding\n\n"
    "AREA TO INVESTIGATE: {goal}\n\n"
    "Generate THREE lenses forming a coherent pipeline for this area. "
    "Output ONLY a JSON array:\n"
    '[{{"name": "snake_case", "prompt": "lens text", "role": "primary"}}, '
    '{{"name": "snake_case", "prompt": "lens text", "role": "adversarial"}}, '
    '{{"name": "snake_case", "prompt": "lens text", "role": "synthesis"}}]'
)

# Full Prism cooker for expand mode: generates an ordered pipeline of lenses.
# Does NOT constrain count or roles — the cooker decides the structure.
COOK_FULL_PRISM_PROMPT = (
    "You generate a multi-pass analytical system for deep investigation of a specific area.\n\n"
    "An analytical lens is a system prompt given to an AI analyzing an artifact. "
    "Study these scored examples:\n\n"
    'SCORED 9.5/10: "Identify every explicit choice. Name the alternative each invisibly rejects. '
    "Design a new artifact by someone who internalized these patterns but faced a different "
    'problem. Trace which transferred patterns create silent problems. Name the pedagogy law."\n'
    'SCORED 9/10: "Extract every empirical claim about timing, causality, resources, or behavior. '
    "Assume each is false. Trace the corruption. Build three alternatives inverting one claim each. "
    'Predict which false claim causes the slowest, most invisible failure."\n\n'
    "The lenses form an ordered pipeline. The first lens analyzes the raw artifact. "
    "Each subsequent lens receives the artifact PLUS all previous analyses. "
    "Later lenses should challenge, deepen, or synthesize earlier findings.\n\n"
    "AREA TO INVESTIGATE: {area}\n\n"
    "Generate lenses forming a coherent pipeline for this area. "
    "Output ONLY a JSON array:\n"
    '[{{"name": "snake_case", "prompt": "lens text", "role": "descriptive_role"}}, ...]'
)


# Full Prism cooker for discover: generates a multi-pass discovery pipeline.
# First pass discovers areas. Subsequent passes find what the first missed.
COOK_DISCOVER_FULL_PROMPT = (
    "You generate a multi-pass discovery system that finds all structural areas "
    "worth investigating in an artifact.\n\n"
    "An analytical lens is a system prompt given to an AI. "
    "Study these scored examples:\n\n"
    'SCORED 9.5/10: "Identify every explicit choice. Name the alternative each invisibly rejects. '
    "Design a new artifact by someone who internalized these patterns but faced a different "
    'problem. Trace which transferred patterns create silent problems. Name the pedagogy law."\n'
    'SCORED 9/10: "Extract every empirical claim about timing, causality, resources, or behavior. '
    "Assume each is false. Trace the corruption. Build three alternatives inverting one claim each. "
    'Predict which false claim causes the slowest, most invisible failure."\n\n'
    "The passes form an ordered pipeline. The first pass discovers areas from the raw artifact. "
    "Each subsequent pass receives the artifact PLUS all previous discovery outputs. "
    "Later passes should find what earlier passes missed — blind spots, "
    "hidden dependencies, structural properties that only become visible through contradiction.\n\n"
    "DOMAIN: {domain}\n\n"
    "Generate passes forming a coherent discovery pipeline. "
    "Output ONLY a JSON array:\n"
    '[{{"name": "snake_case", "prompt": "pass instructions", "role": "descriptive_role"}}, ...]'
)

# Chat cooker: generates ONE optimal lens for responding to a user's message.
COOK_CHAT_SINGLE_PROMPT = (
    "You generate an optimal analytical lens for responding to a user's message.\n\n"
    "An analytical lens is a system prompt given to an AI before it responds. "
    "Study these scored examples:\n\n"
    'SCORED 9.5/10: "Identify every explicit choice this artifact makes. For each, name the '
    "alternative it invisibly rejects. Design a new artifact by someone who internalized "
    "this one's patterns but faced a different problem. Trace which transferred patterns "
    'create silent problems. Name the pedagogy law."\n'
    'SCORED 9/10: "Extract every empirical claim this artifact embeds. For each, assume it is false. '
    "Trace the corruption. Build three alternatives, each inverting one claim. "
    'Predict which false claim causes the slowest, most invisible failure."\n\n'
    "The lens should make the AI think more deeply about this specific message — "
    "find hidden assumptions, structural properties, non-obvious implications. "
    "The lens shapes HOW the AI thinks, not WHAT it says.\n\n"
    "USER MESSAGE:\n{message}\n\n"
    "Generate ONE lens optimized for responding to this message. "
    "Output ONLY a JSON object:\n"
    '{{"name": "snake_case", "prompt": "the lens text"}}'
)

# Chat cooker: generates a multi-pass response pipeline for a user's message.
COOK_CHAT_FULL_PROMPT = (
    "You generate a multi-pass response pipeline for a user's message.\n\n"
    "An analytical lens is a system prompt given to an AI. "
    "Study these scored examples:\n\n"
    'SCORED 9.5/10: "Identify every explicit choice. Name the alternative each invisibly rejects. '
    "Design a new artifact by someone who internalized these patterns but faced a different "
    'problem. Trace which transferred patterns create silent problems. Name the pedagogy law."\n'
    'SCORED 9/10: "Extract every empirical claim about timing, causality, resources, or behavior. '
    "Assume each is false. Trace the corruption. Build three alternatives inverting one claim each. "
    'Predict which false claim causes the slowest, most invisible failure."\n\n'
    "The lenses form an ordered pipeline. The first lens generates a deep response. "
    "Each subsequent lens receives the message PLUS all previous responses. "
    "Later lenses should challenge, deepen, or synthesize earlier responses.\n\n"
    "USER MESSAGE:\n{message}\n\n"
    "Generate lenses forming a coherent response pipeline for this message. "
    "Output ONLY a JSON array:\n"
    '[{{"name": "snake_case", "prompt": "lens text", "role": "descriptive_role"}}, ...]'
)

SYSTEM_PROMPT_FALLBACK = (
    "You are a structural analyst. For any input — code, ideas, designs, systems, "
    "strategies — you find what it conceals. Every structure hides real problems "
    "behind plausible surfaces. You make specific, falsifiable claims and test them: "
    "what defends this claim, what breaks it, what both sides take for granted. "
    "You think in conservation laws: every design trades one property against another, "
    "and you name the trade-off. You distinguish fixable issues (implementation "
    "choices that can change) from structural ones (properties of the problem space "
    "that persist through every improvement). When proposing improvements, you check "
    "whether they recreate the problems they solve. You name the structural invariant — "
    "the property that survives all attempts to fix it — and derive the conservation "
    "law it implies. Be concise. When working with code, use tools to read, edit, "
    "and write files, run commands, and search. Always read files before editing."
)

ALLOWED_TOOLS = "Read,Edit,Write,Glob,Grep"

# Resolve claude executable (claude.cmd on Windows)
CLAUDE_CMD = shutil.which("claude") or "claude"


class ClaudeInterface:
    """Abstraction layer for all Anthropic CLI interactions."""

    def __init__(self, working_dir, cmd=None):
        self.working_dir = pathlib.Path(working_dir)
        self.cmd = cmd or CLAUDE_CMD

    def call(self, system_prompt, user_input, model="haiku", timeout=120,
             output_format="text", tools=None):
        """Fire-and-forget call. Returns stdout text.

        Uses --system-prompt-file (temp file) instead of --system-prompt
        to avoid CLAUDE.md leaking into the system prompt on long prompts.
        """
        # Write system prompt to temp file — avoids shell escaping issues
        # and CLAUDE.md contamination that happens with --system-prompt arg
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8",
            dir=str(self.working_dir))
        try:
            tmp.write(system_prompt)
            tmp.close()
            args = [
                self.cmd, "-p",
                "--model", model,
                "--output-format", output_format,
                "--system-prompt-file", tmp.name,
            ]
            if tools:
                args.extend(["--allowedTools", tools])
            proc = subprocess.run(
                args,
                input=user_input, capture_output=True, text=True,
                encoding="utf-8", timeout=timeout,
                env={k: v for k, v in os.environ.items() if k != "CLAUDECODE"},
                cwd=str(self.working_dir),
            )
            return proc.stdout.strip()
        except subprocess.TimeoutExpired:
            return ""
        except Exception as e:
            return f"[Error: {e}]"
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    def call_checked(self, system_prompt, user_input, model="haiku",
                     timeout=120, tools=None):
        """Like call(), but returns (text, ok) where ok=True on returncode==0."""
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8",
            dir=str(self.working_dir))
        try:
            tmp.write(system_prompt)
            tmp.close()
            args = [
                self.cmd, "-p",
                "--model", model,
                "--output-format", "text",
                "--system-prompt-file", tmp.name,
            ]
            if tools:
                args.extend(["--allowedTools", tools])
            proc = subprocess.run(
                args,
                input=user_input, capture_output=True, text=True,
                encoding="utf-8", timeout=timeout,
                env={k: v for k, v in os.environ.items() if k != "CLAUDECODE"},
                cwd=str(self.working_dir),
            )
            return proc.stdout.strip(), (proc.returncode == 0)
        except subprocess.TimeoutExpired:
            return "", False
        except Exception as e:
            return f"[Error: {e}]", False
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    def _write_prompt_file(self, system_prompt):
        """Write system prompt to a temp file. Caller must delete it."""
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8",
            dir=str(self.working_dir))
        tmp.write(system_prompt)
        tmp.close()
        return tmp.name

    def call_streaming(self, system_prompt, user_input, model="haiku",
                       resume=None, tools=False):
        """Streaming call via Popen. Returns (subprocess.Popen, tmp_path).

        Caller is responsible for reading stdout, waiting for completion,
        and deleting tmp_path when done.
        """
        tmp_path = None
        args = [
            self.cmd, "-p",
            "--model", model,
            "--output-format", "stream-json",
        ]
        if resume:
            args.extend(["--resume", resume])
        if tools:
            args.append("--allowedTools")
            args.append(ALLOWED_TOOLS)
        if system_prompt:
            tmp_path = self._write_prompt_file(system_prompt)
            args.extend(["--system-prompt-file", tmp_path])

        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env={k: v for k, v in os.environ.items() if k != "CLAUDECODE"},
            cwd=str(self.working_dir),
        )
        if user_input:
            try:
                proc.stdin.write(user_input)
                proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass
        return proc, tmp_path


class C:
    """ANSI color codes."""
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    CYAN   = "\033[36m"
    GREEN  = "\033[32m"
    YELLOW = "\033[33m"
    RED    = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE   = "\033[34m"


# ── Session ──────────────────────────────────────────────────────────────────

class Session:
    """Track session ID, model, and cumulative usage."""

    def __init__(self, model="haiku"):
        self.session_id = None
        self.model = model
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.turn_count = 0

    def save(self, name):
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        path = SESSIONS_DIR / f"{name}.json"
        path.write_text(json.dumps({
            "_version": 1,
            "session_id": self.session_id,
            "model": self.model,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": self.total_cost_usd,
            "turn_count": self.turn_count,
        }, indent=2))
        return path

    def load(self, name):
        path = SESSIONS_DIR / f"{name}.json"
        if not path.exists():
            return False
        data = json.loads(path.read_text())
        if isinstance(data, dict) and "_version" not in data:
            data["_version"] = 1
        self.session_id = data.get("session_id")
        self.model = data.get("model", "sonnet")
        self.total_input_tokens = data.get("total_input_tokens", 0)
        self.total_output_tokens = data.get("total_output_tokens", 0)
        self.total_cost_usd = data.get("total_cost_usd", 0.0)
        self.turn_count = data.get("turn_count", 0)
        return True

    @staticmethod
    def list_saved():
        if not SESSIONS_DIR.exists():
            return []
        return sorted(p.stem for p in SESSIONS_DIR.glob("*.json"))


# ── Stream Parser ────────────────────────────────────────────────────────────

class StreamParser:
    """Parse claude -p --output-format stream-json output line by line.

    CLI format (not API deltas):
      type: "system"    — init with session_id, model
      type: "assistant" — message with content blocks (thinking|text|tool_use)
      type: "result"    — final result with session_id, cost, usage
    """

    def __init__(self):
        self.result_data = None
        self.session_id = None

    def parse_line(self, line):
        """Parse one JSON line. Returns list of (event_type, data) tuples."""
        line = line.strip()
        if not line:
            return []
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return []

        etype = event.get("type", "")
        events = []

        if etype == "system":
            self.session_id = event.get("session_id")
            events.append(("system", event))

        elif etype == "assistant":
            msg = event.get("message", {})
            content = msg.get("content", [])
            for block in content:
                btype = block.get("type", "")
                if btype == "thinking":
                    events.append(("thinking", block.get("thinking", "")))
                elif btype == "text":
                    events.append(("text", block.get("text", "")))
                elif btype == "tool_use":
                    name = block.get("name", "tool")
                    events.append(("tool_use", name))
                elif btype == "tool_result":
                    events.append(("tool_result", block))

        elif etype == "result":
            self.result_data = event
            self.session_id = event.get("session_id")
            events.append(("result", event))

        return events


# ── Claude Backend ───────────────────────────────────────────────────────────

class ClaudeBackend:
    """Manage claude -p subprocess. Sends messages via stdin, yields stream lines."""

    def __init__(self, model, working_dir, session_id=None,
                 system_prompt=None, tools=True):
        self.model = model
        self.working_dir = working_dir
        self.session_id = session_id
        self.system_prompt = system_prompt or SYSTEM_PROMPT_FALLBACK
        self.tools = tools
        self.proc = None

    def build_cmd(self, prompt_file=None):
        cmd = [
            CLAUDE_CMD, "-p",
            "--output-format", "stream-json",
            "--verbose",
            "--model", self.model,
        ]
        if self.tools:
            cmd += ["--allowedTools", ALLOWED_TOOLS]
        if self.session_id:
            cmd += ["--resume", self.session_id]
        elif prompt_file:
            cmd += ["--system-prompt-file", prompt_file]
        else:
            cmd += ["--system-prompt", self.system_prompt]
        return cmd

    def send(self, message):
        """Send message to claude -p, yield raw stdout lines.

        Uses --system-prompt-file (temp file) to avoid CLAUDE.md contamination.
        """
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8",
            dir=self.working_dir)
        tmp.write(self.system_prompt)
        tmp.close()

        try:
            cmd = self.build_cmd(prompt_file=tmp.name)
            env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=env,
                cwd=self.working_dir,
            )

            try:
                self.proc.stdin.write(message.encode("utf-8"))
                self.proc.stdin.close()
            except BrokenPipeError:
                return

            for raw_line in self.proc.stdout:
                yield raw_line.decode("utf-8", errors="replace")

            self.proc.wait()
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    def kill(self):
        """Terminate the subprocess."""
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()


# ── REPL ─────────────────────────────────────────────────────────────────────

class PrismREPL:
    """Main REPL loop with slash commands and streaming output."""

    def __init__(self, model, working_dir, resume_session=None):
        self.session = Session(model=model)
        self.working_dir = pathlib.Path(working_dir).resolve()
        self._claude = ClaudeInterface(self.working_dir)
        self.backend = None
        self.queued_files = []
        self._interrupted = False
        self._auto_mode = False
        self._last_action = None  # ("scan", {"issues": [...]}) | ("deep", {"file": ...}) | ...
        self._discover_results = []  # cached discover lens list for target=N / deep=N
        self._chat_mode = "off"  # "off" (vanilla), "single" (dynamic cook per msg), "full" (dynamic pipeline per msg)
        self._active_lens_name = None   # e.g. "pedagogy" or "readme/promise_credibility"
        self._active_lens_prompt = None # loaded lens text, used in system prompt
        self.system_prompt = self._load_system_prompt()
        self._session_diverged = False       # True when session_id changed unexpectedly
        self._session_transition_log = []    # In-memory log of session ID transitions
        self._commands = {}
        self._register_builtin_commands()

        if resume_session:
            if self.session.load(resume_session):
                print(f"{C.GREEN}Resumed session: {resume_session} "
                      f"(turn {self.session.turn_count}, {self.session.model}){C.RESET}")
            else:
                print(f"{C.YELLOW}Session '{resume_session}' not found, "
                      f"starting fresh{C.RESET}")

    def banner(self):
        lens_info = ""
        if self._active_lens_name:
            lens_info = f"  {C.DIM}lens={C.RESET}{self._active_lens_name}"
        print(f"\n{C.BOLD}{C.CYAN}prism{C.RESET} {C.DIM}v{VERSION}{C.RESET}"
              f"  {C.DIM}model={C.RESET}{self.session.model}"
              f"  {C.DIM}prism={C.RESET}{self._chat_mode}"
              f"{lens_info}"
              f"  {C.DIM}cwd={C.RESET}{self.working_dir}")
        print(f"{C.DIM}Type /help for commands. "
              f"Ctrl+C to cancel. Ctrl+D to exit.{C.RESET}\n")

    def run(self):
        """Main loop: read input, dispatch commands or send to Claude."""
        self.banner()
        while True:
            try:
                user_input = input(f"{C.GREEN}>{C.RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{C.DIM}bye{C.RESET}")
                break

            if not user_input:
                continue

            if user_input.startswith("/"):
                if not self._handle_command(user_input):
                    break
                continue

            if self._check_shortcuts(user_input):
                continue

            self._enrich(user_input)
            message = self._build_message(user_input)
            self.queued_files.clear()
            if self._chat_mode == "full":
                self._chat_full_pipeline(message)
            elif self._chat_mode == "single":
                self._chat_single_prism(message)
            else:
                self._send_and_stream(message)



    # ── Full-mode chat pipeline ──────────────────────────────────────────────

    def _chat_single_prism(self, message):
        """Dynamic single prism: cook 1 lens per message, then respond.

        1. Cook an optimal lens for this specific message
        2. Use it as system prompt for the response
        """
        # Cook lens for this message
        print(f"  {C.DIM}cooking lens...{C.RESET}", end="",
              flush=True)
        raw = self._call_model(
            COOK_CHAT_SINGLE_PROMPT.format(
                message=message[:2000]),
            message[:2000], timeout=60)
        parsed = self._parse_stage_json(raw, "cook_chat_single")

        if isinstance(parsed, dict) and parsed.get("prompt"):
            lens_prompt = parsed["prompt"]
            name = parsed.get("name", "dynamic")
            sys.stdout.write(
                f"\r  {C.DIM}lens: {name}{C.RESET}"
                + " " * 20 + "\n")
        else:
            # Fallback: use base system prompt
            sys.stdout.write(
                f"\r  {C.DIM}(using default lens){C.RESET}"
                + " " * 20 + "\n")
            lens_prompt = None

        print(f"{C.BOLD}{C.BLUE}── Response ──{C.RESET}")
        self._chat_full_call(message, system_prompt=lens_prompt)

    def _chat_full_pipeline(self, message):
        """Dynamic full prism: cook pipeline per message, then run chained.

        1. Cook a multi-pass pipeline for this specific message
        2. Run each lens in sequence, chaining outputs
        3. Return synthesized response
        """
        # Cook pipeline for this message
        print(f"  {C.DIM}cooking pipeline...{C.RESET}", end="",
              flush=True)
        raw = self._call_model(
            COOK_CHAT_FULL_PROMPT.format(
                message=message[:2000]),
            message[:2000], timeout=90)
        parsed = self._parse_stage_json(raw, "cook_chat_full")

        if isinstance(parsed, list) and len(parsed) >= 2:
            lenses = []
            for item in parsed:
                text = item.get("prompt", "")
                role = item.get("role", item.get("name", "pass"))
                if text:
                    lenses.append({"prompt": text, "role": role})
            roles = ", ".join(l["role"] for l in lenses)
            sys.stdout.write(
                f"\r  {C.DIM}pipeline: {roles}{C.RESET}"
                + " " * 20 + "\n")
        else:
            # Fallback: hardcoded adversarial + synthesis
            sys.stdout.write(
                f"\r  {C.DIM}(using default pipeline){C.RESET}"
                + " " * 20 + "\n")
            adv_prompt = self._load_lens(
                "l12_general_adversarial") or ""
            synth_prompt = self._load_lens(
                "l12_general_synthesis") or ""
            lenses = [
                {"prompt": "", "role": "response"},
                {"prompt": adv_prompt, "role": "adversarial"},
                {"prompt": synth_prompt, "role": "synthesis"},
            ]

        # Run pipeline
        outputs = []
        for i, lens in enumerate(lenses):
            role = lens["role"]

            if i == 0:
                msg = message
                prompt = lens["prompt"] or None
            else:
                parts = [f"# USER REQUEST\n\n{message}"]
                for j, prev in enumerate(outputs):
                    prev_role = lenses[j]["role"].upper()
                    parts.append(
                        f"# PASS {j + 1}: {prev_role}"
                        f"\n\n{prev}")
                msg = "\n\n---\n\n".join(parts)
                prompt = lens["prompt"]

            print(f"\n{C.BOLD}{C.BLUE}── {role} ──{C.RESET}")
            output = self._chat_full_call(
                msg, system_prompt=prompt)

            if output and not self._interrupted:
                outputs.append(output)
            if not output or self._interrupted:
                break

    def _chat_full_call(self, message, system_prompt=None):
        """Single streaming call for the chat pipeline. Returns captured output."""
        active_prompt = system_prompt
        if active_prompt is None:
            active_prompt = getattr(
                self, '_enriched_system_prompt', None)
            if active_prompt:
                self._enriched_system_prompt = None
            else:
                active_prompt = self.system_prompt
        if self._active_lens_prompt and system_prompt is None:
            active_prompt = (self._active_lens_prompt
                             + "\n\n" + active_prompt)

        backend = ClaudeBackend(
            model=self.session.model,
            working_dir=str(self.working_dir),
            session_id=None,
            system_prompt=active_prompt,
            tools=False,
        )
        return self._stream_and_capture(backend, message)

    # ── Non-interactive review mode ───────────────────────────────────────────

    def review(self, path, lenses=None, json_output=False, output_file=None):
        """Non-interactive review mode. Returns exit code: 0=clean, 1=issues, 2=error."""
        target = pathlib.Path(path)
        if not target.is_absolute():
            target = self.working_dir / target

        if not target.exists():
            print(f"Error: {path} not found", file=sys.stderr)
            return 2

        # Collect files
        if target.is_dir():
            files = self._collect_files(str(target))
        else:
            files = [target]

        if not files:
            print(f"Error: no analyzable files in {path}", file=sys.stderr)
            return 2

        # Determine lenses
        if lenses is None:
            lenses = self._get_lenses()

        print(f"Reviewing {len(files)} file(s) with {len(lenses)} lens(es)...",
              file=sys.stderr)

        # Run lenses in parallel (reuse _run_lens_oneshot)
        all_results = {}
        sem = threading.Semaphore(5)
        lock = threading.Lock()
        total = len(files) * len(lenses)
        done = [0]

        def run_one(fpath, lens):
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                result = self._run_lens_oneshot(lens, content, fpath.name)
            except Exception:
                result = ""
            with lock:
                all_results[(fpath.name, lens)] = result
                done[0] += 1
                print(f"\r  Progress: {done[0]}/{total}", end="", file=sys.stderr)

        threads = []
        for fpath in files:
            for lens in lenses:
                def _run(f=fpath, l=lens):
                    sem.acquire()
                    try:
                        run_one(f, l)
                    finally:
                        sem.release()
                t = threading.Thread(target=_run)
                t.start()
                threads.append(t)

        for t in threads:
            t.join()
        print(file=sys.stderr)  # newline after progress

        # Format output
        if json_output:
            output = self._review_format_json(files, lenses, all_results)
        else:
            output = self._review_format_markdown(files, lenses, all_results)

        # Write output
        if output_file:
            pathlib.Path(output_file).write_text(output, encoding="utf-8")
            print(f"Report written to {output_file}", file=sys.stderr)
        else:
            print(output)

        # Exit code: 1 if any results found content, 0 if empty
        has_findings = any(v.strip() for v in all_results.values())
        return 1 if has_findings else 0

    def _review_format_json(self, files, lenses, all_results):
        """Format review results as JSON."""
        data = {}
        for fpath in files:
            file_data = {}
            for lens in lenses:
                result = all_results.get((fpath.name, lens), "")
                if result:
                    file_data[lens] = result
            if file_data:
                data[fpath.name] = file_data
        return json.dumps(data, indent=2, ensure_ascii=False)

    def _review_format_markdown(self, files, lenses, all_results):
        """Format review results as markdown report."""
        lines = ["# Code Review Report\n"]
        for fpath in files:
            lines.append(f"## {fpath.name}\n")
            for lens in lenses:
                result = all_results.get((fpath.name, lens), "")
                if result:
                    lines.append(f"### {lens}\n")
                    lines.append(result)
                    lines.append("")
        return "\n".join(lines)

    # ── Slash commands ───────────────────────────────────────────────────

    def _handle_command(self, cmd):
        """Handle slash command. Returns True to continue, False to exit."""
        parts = cmd.split(maxsplit=1)
        name = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        entry = self._commands.get(name)
        if entry:
            result = entry["handler"](arg)
            return result if result is False else True
        else:
            print(f"{C.YELLOW}Unknown command: {name}. Type /help{C.RESET}")
            return True

    def _register_builtin_commands(self):
        """Populate the command registry with all built-in slash commands."""
        cmds = {
            "/exit":      {"handler": self._cmd_exit,       "help": "Exit Prism",                                        "args": "",                                              "category": "session"},
            "/help":      {"handler": self._cmd_help,       "help": "Show all commands with examples",                   "args": "",                                              "category": "session"},
            "/clear":     {"handler": self._cmd_clear,      "help": "Reset session, clear discover cache and queued files", "args": "",                                           "category": "session"},
            "/model":     {"handler": self._cmd_model,      "help": "Switch Claude model for all operations",            "args": "haiku|sonnet|opus",                             "category": "session"},
            "/prism":     {"handler": self._cmd_mode,       "help": "Chat mode: off (vanilla), single/full (dynamic lenses), or static lens", "args": "[off|single|full|<lens>]", "category": "session"},

            "/compact":   {"handler": self._cmd_compact,    "help": "Trim conversation context to reduce token usage",   "args": "",                                              "category": "session"},
            "/cost":      {"handler": self._cmd_cost,       "help": "Show turns, tokens in/out, and USD cost",           "args": "",                                              "category": "session"},
            "/save":      {"handler": self._cmd_save,       "help": "Save current session to a named file for later",    "args": "<name>",                                        "category": "session"},
            "/load":      {"handler": self._cmd_load,       "help": "Resume a saved session (no arg = list all)",        "args": "[name]",                                        "category": "session"},
            "/scan":      {"handler": self._cmd_scan,       "help": "Structural analysis via cognitive lenses",          "args": "<file|dir|text> [mode]",                        "category": "analysis"},
            "/cook":      {"handler": self._cmd_cook,       "help": "Generate domain-specific lenses via meta-cooker",   "args": "<domain> [sample-file]",                        "category": "analysis"},
            "/lenses":    {"handler": self._cmd_lenses,     "help": "List all lenses: built-in, cooked, and local",      "args": "",                                              "category": "info"},

            "/fix":       {"handler": self._cmd_heal,       "help": "Extract issues from scan → apply fixes with diff review", "args": "[file] [deep] [auto]",                    "category": "fix"},
            "/status":    {"handler": self._cmd_status,     "help": "Dashboard: last scan age, open issues, cooked skills", "args": "",                                            "category": "info"},
            "/reload":    {"handler": self._cmd_reload_cmd, "help": "Hot-reload prism.py + lenses without restarting",   "args": "",                                              "category": "session"},
        }
        self._commands.update(cmds)

    # ── Inline command wrappers ───────────────────────────────────────────────

    def _cmd_exit(self, arg):
        """Print bye and signal loop exit."""
        print(f"{C.DIM}bye{C.RESET}")
        return False

    def _cmd_help(self, arg):
        """Show help text."""
        self._show_help()

    def _cmd_clear(self, arg):
        """Clear session, queued files, and last action."""
        model = self.session.model
        self.session = Session(model=model)
        self.queued_files.clear()
        self._last_action = None
        self._discover_results = []
        print(f"{C.YELLOW}Session cleared{C.RESET}")

    def _cmd_model(self, arg):
        """Validate and switch model."""
        if arg in ("haiku", "sonnet", "opus"):
            self.session.model = arg
            print(f"{C.CYAN}Model: {arg}{C.RESET}")
        else:
            print(f"{C.YELLOW}Usage: /model haiku|sonnet|opus{C.RESET}")

    def _cmd_mode(self, arg):
        """Switch chat prism mode or set a static lens.

        /prism             — show current mode
        /prism off         — vanilla chat (no lenses)
        /prism single      — dynamic single prism (cook lens per message)
        /prism full        — dynamic full prism (cook pipeline per message)
        /prism <lens>      — static lens for all messages (e.g. pedagogy)
        """
        if not arg:
            if self._chat_mode == "off":
                lens = self._active_lens_name or "none"
                print(f"{C.CYAN}Prism: off (vanilla), "
                      f"lens={lens}{C.RESET}")
            elif self._chat_mode == "single":
                print(f"{C.CYAN}Prism: single "
                      f"(dynamic lens per message){C.RESET}")
            elif self._chat_mode == "full":
                print(f"{C.CYAN}Prism: full "
                      f"(dynamic pipeline per message){C.RESET}")
            return

        if arg == "off":
            self._chat_mode = "off"
            self._active_lens_name = None
            self._active_lens_prompt = None
            print(f"{C.CYAN}Prism: off (vanilla){C.RESET}")
        elif arg == "single":
            self._chat_mode = "single"
            self._active_lens_name = None
            self._active_lens_prompt = None
            print(f"{C.CYAN}Prism: single "
                  f"(cook lens per message){C.RESET}")
        elif arg == "full":
            self._chat_mode = "full"
            self._active_lens_name = None
            self._active_lens_prompt = None
            print(f"{C.CYAN}Prism: full "
                  f"(cook pipeline per message){C.RESET}")
        else:
            # Static lens mode
            prompt = self._load_lens(arg)
            if prompt:
                self._chat_mode = "off"
                self._active_lens_name = arg
                self._active_lens_prompt = prompt
                preview = prompt[:60] + (
                    "..." if len(prompt) > 60 else "")
                print(f"{C.CYAN}Lens: {arg}{C.RESET}")
                print(f"  {C.DIM}{preview}{C.RESET}")
            else:
                print(f"{C.YELLOW}Unknown: {arg}{C.RESET}")
                print(f"  {C.DIM}/prism off|single|full "
                      f"or /lenses{C.RESET}")

    def _cmd_compact(self, arg):
        """Compact context."""
        self._send_and_stream("/compact")

    def _cmd_cost(self, arg):
        """Print turn/token/cost stats."""
        s = self.session
        print(f"{C.CYAN}Turns: {s.turn_count}  "
              f"In: {s.total_input_tokens:,}  "
              f"Out: {s.total_output_tokens:,}  "
              f"Cost: ${s.total_cost_usd:.4f}{C.RESET}")

    def _cmd_save(self, arg):
        """Save session to named file."""
        if not arg:
            print(f"{C.YELLOW}Usage: /save <name>{C.RESET}")
        elif not self.session.session_id:
            print(f"{C.YELLOW}No active session to save{C.RESET}")
        else:
            path = self.session.save(arg)
            print(f"{C.GREEN}Saved: {path}{C.RESET}")

    def _cmd_load(self, arg):
        """Load a named session or list saved sessions."""
        if not arg:
            saved = Session.list_saved()
            if saved:
                print(f"{C.CYAN}Sessions: {', '.join(saved)}{C.RESET}")
            else:
                print(f"{C.DIM}No saved sessions{C.RESET}")
        elif self.session.load(arg):
            print(f"{C.GREEN}Loaded: {arg} "
                  f"(turn {self.session.turn_count}){C.RESET}")
        else:
            print(f"{C.RED}Session '{arg}' not found{C.RESET}")

    def _cmd_reload_cmd(self, arg):
        """Wrapper for _cmd_reload that also re-registers commands."""
        self._cmd_reload()
        self._register_builtin_commands()

    def _show_help(self):
        """Auto-generate help from command registry, grouped by category."""
        # Category display order and headers
        categories = [
            ("analysis", "Analysis"),
            ("fix",      "Fix"),
            ("info",     "Info"),
            ("session",  "Session"),
        ]

        # Collect entries per category, deduplicate aliases
        seen_handlers = set()
        by_category = {cat: [] for _, cat in [(c, c) for c, _ in categories]}
        for name, entry in self._commands.items():
            handler_fn = getattr(entry["handler"], "__func__", entry["handler"])
            if handler_fn in seen_handlers:
                continue
            seen_handlers.add(handler_fn)
            cat = entry.get("category", "session")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append((name, entry))

        print()
        for cat_key, cat_label in categories:
            entries = by_category.get(cat_key, [])
            if not entries:
                continue
            print(f"{C.BOLD}{cat_label}:{C.RESET}")
            for name, entry in entries:
                args = entry.get("args", "")
                help_text = entry.get("help", "")
                if args:
                    left = f"  {C.CYAN}{name}{C.RESET} {args}"
                else:
                    left = f"  {C.CYAN}{name}{C.RESET}"
                # Pad left column to ~38 chars (visible chars only)
                visible_left = f"  {name}" + (f" {args}" if args else "")
                pad = max(1, 38 - len(visible_left))
                print(f"{left}{' ' * pad}{help_text}")
            # Extra detail lines per category
            if cat_key == "analysis":
                print(f"\n  {C.DIM}Single Prism — 1 call, L12 structural analysis (~$0.003):{C.RESET}")
                print(f"  {C.DIM}  /scan auth.py                      conservation law + meta-law + bug table{C.RESET}")
                print(f"  {C.DIM}  /scan \"how should a todo app        works on any text, not just code files{C.RESET}")
                print(f"  {C.DIM}         handle shared state?\"{C.RESET}")

                print(f"\n  {C.DIM}Full Prism — 3 calls: L12 → adversarial → synthesis:{C.RESET}")
                print(f"  {C.DIM}  /scan auth.py full                  overclaims destroyed, corrected synthesis{C.RESET}")

                print(f"\n  {C.DIM}Discover → Expand — explore areas, then go deep on the ones you pick:{C.RESET}")
                print(f"  {C.DIM}  /scan auth.py discover              cook area lenses, show numbered list{C.RESET}")
                print(f"  {C.DIM}  /scan auth.py discover full         multi-pass discover (cooked pipeline, deeper){C.RESET}")
                print(f"  {C.DIM}  /scan auth.py expand                pick areas interactively, single/full each{C.RESET}")
                print(f"  {C.DIM}  /scan auth.py expand 1,3 single     areas 1,3 as single prism{C.RESET}")
                print(f"  {C.DIM}  /scan auth.py expand 2-4 full       areas 2-4 as full prism{C.RESET}")
                print(f"  {C.DIM}  /scan auth.py expand * single       all discovered areas as single prism{C.RESET}")

                print(f"\n  {C.DIM}Direct targeting — you already know what area to investigate:{C.RESET}")
                print(f'  {C.DIM}  /scan auth.py target="race conds"   cook goal-specific lens + run it{C.RESET}')
                print(f"  {C.DIM}  /scan auth.py target=2              run 2nd discover lens (already cooked){C.RESET}")
                print(f'  {C.DIM}  /scan auth.py deep="error handling" cook 3-lens pipeline for area + run all 3{C.RESET}')
                print(f"  {C.DIM}  /scan auth.py deep=1                same, using 1st discover area as goal{C.RESET}")

                print(f"\n  {C.DIM}Fix loop — scan → fix → re-scan until clean:{C.RESET}")
                print(f"  {C.DIM}  /scan auth.py fix                   interactive: review each fix before applying{C.RESET}")
                print(f"  {C.DIM}  /scan auth.py fix auto              automatic: apply all, re-scan to verify{C.RESET}")

                print(f"\n  {C.DIM}Project-level — works on directories:{C.RESET}")
                print(f"  {C.DIM}  /scan src/                          L12 on every code file in directory{C.RESET}")
                print(f"  {C.DIM}  /scan src/ discover                 project-level area discovery (compact map){C.RESET}")
                print(f"  {C.DIM}  /scan src/ expand                   project-level expand with area selection{C.RESET}")

                print(f"\n  {C.DIM}Lens generation — create domain-specific lenses:{C.RESET}")
                print(f"  {C.DIM}  /cook legal                         generate lenses for legal documents{C.RESET}")
                print(f"  {C.DIM}  /cook api-design spec.yaml          lenses informed by a sample artifact{C.RESET}")
                print(f"  {C.DIM}  /lenses                             list all lenses (built-in + cooked + local){C.RESET}")

            if cat_key == "fix":
                print(f"\n  {C.DIM}Examples:{C.RESET}")
                print(f"  {C.DIM}  /fix                                pick issues interactively from last scan{C.RESET}")
                print(f"  {C.DIM}  /fix auth.py                        fix that file (auto-scans if no results){C.RESET}")
                print(f"  {C.DIM}  /fix auth.py deep                   full prism scan (3 calls) first, then fix{C.RESET}")
                print(f"  {C.DIM}  /fix auto                           fix all open issues, up to 3 passes{C.RESET}")

            if cat_key == "session":
                print(f"\n  {C.DIM}Chat prism modes — /prism controls how chat responses are enhanced:{C.RESET}")
                print(f"  {C.DIM}  /prism off                          vanilla chat, no lenses (default){C.RESET}")
                print(f"  {C.DIM}  /prism single                       each message gets a freshly cooked lens{C.RESET}")
                print(f"  {C.DIM}  /prism full                         each message gets a cooked multi-lens pipeline{C.RESET}")
                print(f"  {C.DIM}  /prism pedagogy                     static lens: all messages use pedagogy{C.RESET}")
                print(f"  {C.DIM}  /prism legal/contract_analysis      static lens from a cooked domain{C.RESET}")
                print(f"  {C.DIM}  /prism                              show current mode{C.RESET}")

            print()

        print(f"{C.BOLD}Shortcuts:{C.RESET}")
        print(f"  After /scan, type a {C.CYAN}number{C.RESET} (e.g. {C.CYAN}3{C.RESET}) to fix that issue directly.")
        print(f"  Type {C.CYAN}status{C.RESET} anytime (no slash needed) for .deep/ dashboard.")
        print(f"  Just type anything — Prism is a chat. Use /prism to control lens mode.")
        print()

    def _load_system_prompt(self):
        """Load system prompt: .deep/system.md → ~/.prism_skills/system.md → fallback."""
        local = self.working_dir / ".deep" / "system.md"
        if local.exists():
            return local.read_text(encoding="utf-8").strip()
        global_path = GLOBAL_SKILLS_DIR / "system.md"
        if global_path.exists():
            return global_path.read_text(encoding="utf-8").strip()
        return self._load_intent("system_prompt_fallback", SYSTEM_PROMPT_FALLBACK)

    # ── Smart flow ─────────────────────────────────────────────────────

    _FILE_RE = re.compile(
        r'(?:^|[\s\'"`(,])('                          # leading boundary
        r'(?:[\w./\\-]+/)?'                            # optional path prefix
        r'[\w.-]+'                                     # filename stem
        r'\.(?:py|js|ts|tsx|jsx|go|rs|java|rb|sh|c|cpp|h|hpp|cs|swift|kt|'
        r'yaml|yml|toml|json|md|html|css|scss|sql|proto|ex|exs|zig|lua|'
        r'vue|svelte)'                                 # extension
        r')(?=[\s\'"`),.:;!?]|$)',                     # trailing boundary
        re.MULTILINE,
    )

    def _detect_file_mentions(self, user_input):
        """Detect file mentions in user input, resolve to real paths.
        Only matches files that exist directly under working_dir — no recursive
        glob fallback, to prevent ghost auto-reads of casually mentioned names.
        Returns list of resolved Path objects (max 3, deduped against queued)."""
        matches = self._FILE_RE.findall(user_input)
        if not matches:
            return []

        queued_set = {p.resolve() for p in self.queued_files}
        resolved = []
        seen = set()

        for mention in matches:
            mention = mention.replace("\\", "/")
            # Existence check only — direct path relative to working_dir.
            # No glob fallback: broad tree search causes ghost reads for names
            # mentioned in passing (e.g. "like logger.py" or "test_runner.py (optional)").
            candidate = self.working_dir / mention
            if candidate.is_file():
                real = candidate.resolve()
                if real not in seen and real not in queued_set:
                    resolved.append(real)
                    seen.add(real)
                    if len(resolved) >= 3:
                        break

        return resolved

    def _save_deep_finding(self, file_name, lens_name, output):
        """Save analysis output to .deep/findings/ for future enrichment.

        Appends or updates a ## LENS section in the per-file findings markdown.
        """
        if not output or len(output.strip()) < 50:
            return  # skip trivially short output (likely failed)
        stem = pathlib.Path(file_name).stem
        findings_dir = self.working_dir / ".deep" / "findings"
        findings_dir.mkdir(parents=True, exist_ok=True)
        findings_path = findings_dir / f"{stem}.md"

        section_header = f"## {lens_name.upper()}"
        new_section = f"{section_header}\n\n{output.strip()}\n\n"

        if findings_path.exists():
            existing = findings_path.read_text(encoding="utf-8")
            # Replace existing section or append
            pattern = rf'## {re.escape(lens_name.upper())}\s*\n.*?(?=\n## |\Z)'
            if re.search(pattern, existing, re.DOTALL):
                updated = re.sub(pattern, new_section.strip(), existing,
                                 count=1, flags=re.DOTALL)
            else:
                updated = existing.rstrip() + "\n\n" + new_section
            findings_path.write_text(updated, encoding="utf-8")
        else:
            findings_path.write_text(
                f"# Findings: {file_name}\n\n{new_section}",
                encoding="utf-8")

        print(f"  {C.DIM}Saved to .deep/findings/{stem}.md{C.RESET}")

    def _load_deep_context(self, files):
        """Load .deep/ context for detected files. Returns XML string or ""."""
        deep_dir = self.working_dir / ".deep"
        if not deep_dir.exists():
            return ""

        parts = []

        # Project summary: issue counts + scan age
        issues_path = deep_dir / "issues.json"
        if issues_path.exists():
            try:
                raw = json.loads(issues_path.read_text(encoding="utf-8"))
                self._ensure_version(raw)
                issues = raw.get("issues", []) if isinstance(raw, dict) else raw
                open_issues = [i for i in issues if i.get("status") != "fixed"]
                if open_issues:
                    counts = {}
                    for i in open_issues:
                        p = i.get("priority", "P2")
                        counts[p] = counts.get(p, 0) + 1
                    count_str = ", ".join(
                        f"{v} {k}" for k, v in sorted(counts.items()))
                    summary_parts = [
                        f"{len(open_issues)} open issues ({count_str})"]
                    # Scan age
                    report = deep_dir / "report.md"
                    if report.exists():
                        age = time.time() - report.stat().st_mtime
                        summary_parts.append(
                            f"Last scan: {self._format_age(age)}")
                    parts.append(
                        f'<project summary="{". ".join(summary_parts)}" />')
            except (json.JSONDecodeError, OSError):
                pass

        # Per-file context
        for fpath in files:
            file_parts = []
            stem = fpath.stem
            name = fpath.name

            # Findings: extract per-lens summaries + L12 structural
            findings_path = deep_dir / "findings" / f"{stem}.md"
            if findings_path.exists():
                try:
                    text = findings_path.read_text(encoding="utf-8")
                    finding_lines = []
                    # Portfolio lenses: first 2 lines each
                    for lens in self._get_lenses():
                        pattern = (rf'## {re.escape(lens.upper())}\s*\n'
                                   r'(.*?)(?=\n## |\Z)')
                        m = re.search(pattern, text, re.DOTALL)
                        if m:
                            content = m.group(1).strip()
                            lines = [l.strip() for l in content.split("\n")
                                     if l.strip()][:2]
                            if lines:
                                finding_lines.append(
                                    f"- {lens}: {lines[0]}")
                                if len(lines) > 1:
                                    finding_lines.append(
                                        f"  {lines[1]}")
                    # L12 structural: conservation law + meta-law + bug summary
                    l12_pattern = (r'## L12\s*\n(.*?)(?=\n## |\Z)')
                    l12_m = re.search(l12_pattern, text, re.DOTALL)
                    if l12_m:
                        l12_text = l12_m.group(1).strip()
                        # Extract key structural findings (first 20 lines)
                        l12_lines = [l.strip() for l in l12_text.split("\n")
                                     if l.strip()][:20]
                        if l12_lines:
                            finding_lines.append(
                                "- L12 structural: " + l12_lines[0])
                            for line in l12_lines[1:]:
                                finding_lines.append(f"  {line}")
                    if finding_lines:
                        file_parts.append(
                            "[findings]\n" + "\n".join(finding_lines))
                except (OSError, UnicodeDecodeError):
                    pass

            # Issues for this file (cap 5)
            if issues_path.exists():
                try:
                    raw = json.loads(issues_path.read_text(encoding="utf-8"))
                    self._ensure_version(raw)
                    issues = (raw.get("issues", [])
                              if isinstance(raw, dict) else raw)
                    file_issues = [
                        i for i in issues
                        if i.get("status") != "fixed"
                        and name in i.get("file", "")][:5]
                    if file_issues:
                        issue_lines = []
                        for i in file_issues:
                            p = i.get("priority", "P2")
                            iid = i.get("id", "?")
                            title = i.get("title", "")
                            issue_lines.append(
                                f"- {p} #{iid}: {title}")
                        file_parts.append(
                            "[issues]\n" + "\n".join(issue_lines))
                except (json.JSONDecodeError, OSError):
                    pass

            if file_parts:
                parts.append(
                    f'<file-context name="{name}">\n'
                    + "\n".join(file_parts)
                    + "\n</file-context>")

        if not parts:
            return ""
        return "<context>\n" + "\n".join(parts) + "\n</context>"

    def _enrich(self, user_input):
        """Auto-detect files + inject structural context into system prompt.

        Auto-detect files + inject L12 structural context into system prompt.
        Benefits from /scan cached findings on disk.
        """
        detected = self._detect_file_mentions(user_input)

        # Confirm with user before queuing each detected file
        confirmed = []
        for fpath in detected:
            try:
                ans = input(
                    f"  {C.DIM}detected: {fpath.name}{C.RESET} — auto-read? [Y/n] "
                ).strip().lower()
            except (EOFError, KeyboardInterrupt):
                ans = "n"
            if ans in ("", "y"):
                self.queued_files.append(fpath)
                confirmed.append(fpath)

        # Load cached findings for all relevant files (queued + confirmed)
        context_files = list({p.resolve() for p in self.queued_files})
        deep_ctx = self._load_deep_context(context_files) if context_files else ""

        # Auto-enrich: run L12 oneshot on files without cached findings
        lens_ctx = ""
        if context_files:
            files_without_findings = []
            deep_dir = self.working_dir / ".deep" / "findings"
            for fpath in context_files:
                finding = deep_dir / f"{fpath.stem}.md" if deep_dir.exists() else None
                if not finding or not finding.exists():
                    files_without_findings.append(fpath)

            if files_without_findings:
                print(f"  {C.DIM}L12 quick analysis...{C.RESET}",
                      end="", flush=True)
                lens_parts = []
                for fpath in files_without_findings[:2]:  # cap at 2 files
                    try:
                        content = fpath.read_text(
                            encoding="utf-8", errors="replace")
                        result = self._run_lens_oneshot(
                            "l12", content, model="haiku")
                        if result and not result.startswith("["):
                            lens_parts.append(
                                f"[{fpath.name} — l12]\n{result}")
                            print(f" {C.CYAN}{fpath.name}{C.RESET}",
                                  end="", flush=True)
                    except Exception:
                        pass
                print()
                if lens_parts:
                    lens_ctx = "\n\n".join(lens_parts)

        # Inject structural context into system prompt
        if deep_ctx or lens_ctx:
            combined_ctx = "\n".join(p for p in [deep_ctx, lens_ctx] if p)
            self._enriched_system_prompt = (
                self.system_prompt + "\n\n"
                "## Structural findings for the code being discussed\n"
                "Use these findings to inform your response — conservation laws, "
                "trade-offs, and structural constraints this code embeds.\n\n"
                + combined_ctx
            )
        else:
            self._enriched_system_prompt = None

        # Feedback
        if confirmed or deep_ctx or lens_ctx:
            feedback = []
            if confirmed:
                names = [p.name for p in confirmed]
                feedback.append(f"auto-read: {', '.join(names)}")
            if deep_ctx:
                feedback.append("+findings from .deep/")
            if lens_ctx:
                feedback.append("+L12 analysis")
            print(f"  {C.DIM}{' | '.join(feedback)}{C.RESET}")

        # Hint: suggest /scan when files detected but no cached findings
        if confirmed and not deep_ctx:
            names = " ".join(p.name for p in confirmed[:2])
            print(f"  {C.DIM}hint: /scan {names} for L12 structural analysis{C.RESET}")

    def _post_response_hint(self, tools_used):
        """Print dim hint after Claude uses Edit/Write tools."""
        if not (tools_used & {"Edit", "Write"}):
            return
        issues_path = self.working_dir / ".deep" / "issues.json"
        if issues_path.exists():
            print(f"  {C.DIM}hint: /fix to verify{C.RESET}")

    def _suggest_next(self, action_type, data=None):
        """Set _last_action and print contextual hints after commands."""
        self._last_action = (action_type, data or {})

        if action_type == "scan":
            # Load issues from .deep/issues.json
            issues_path = self.working_dir / ".deep" / "issues.json"
            if issues_path.exists():
                try:
                    raw = json.loads(issues_path.read_text(encoding="utf-8"))
                    self._ensure_version(raw)
                    issues = raw.get("issues", []) if isinstance(raw, dict) else raw
                    open_issues = [i for i in issues if i.get("status") != "fixed"]
                    if open_issues:
                        # Count by priority
                        counts = {}
                        for i in open_issues:
                            p = i.get("priority", "P2")
                            counts[p] = counts.get(p, 0) + 1
                        parts = [f"{v} {k}" for k, v in
                                 sorted(counts.items())]
                        summary = ", ".join(parts)
                        self._last_action = (action_type, {"issues": issues})
                        print(f"  {C.CYAN}{len(open_issues)} issues "
                              f"({summary}).{C.RESET}\n"
                              f"  {C.DIM}  Type a number to fix one issue{C.RESET}\n"
                              f"  {C.DIM}  /fix          pick issues interactively{C.RESET}\n"
                              f"  {C.DIM}  /fix auto     fix all issues (up to 3 passes){C.RESET}")
                except (json.JSONDecodeError, OSError):
                    pass

    def _check_shortcuts(self, user_input):
        """Check for conversational shortcuts. Returns True if handled."""
        # Bare number → heal that issue directly
        if (user_input.isdigit() and self._last_action
                and self._last_action[0] == "scan"):
            issues = self._last_action[1].get("issues", [])
            target_id = int(user_input)
            issue = next((i for i in issues
                          if i.get("id") == target_id
                          and i.get("status") != "fixed"), None)
            if issue:
                self._heal_single_issue(issue, issues)
                return True
            else:
                print(f"{C.YELLOW}No open issue #{target_id}. "
                      f"/fix to see all.{C.RESET}")
                return True

        # "status" as bare word
        if user_input.lower() == "status":
            self._cmd_status("")
            return True

        return False

    def _heal_single_issue(self, issue, all_issues):
        """Fix a single issue directly (no picker). Supports one retry."""
        deep_dir = self.working_dir / ".deep"
        iid = issue.get("id", "?")
        title = issue.get("title", "untitled")
        print(f"\n  {C.BOLD}{C.CYAN}── Fix #{iid}: {title} ──{C.RESET}")

        attempts = 0
        instructions = ""
        while attempts < 2:
            attempts += 1
            fix_issue = dict(issue)
            if instructions:
                fix_issue["action"] = (
                    f"{issue.get('action', '')} "
                    f"User instructions: {instructions}")

            result, snapshots = self._heal_fix_one(fix_issue)

            if result == "approved":
                _t = self._resolve_file(issue.get("file", ""))
                pre_fix = snapshots.get(str(_t)) if _t else None
                verdict = self._heal_verify(issue, pre_fix_snapshot=pre_fix)
                issue["status"] = verdict
                self._heal_save_issues(deep_dir, all_issues)
                break
            elif result == "rejected":
                break
            elif result == "instructed":
                try:
                    instructions = input(
                        f"  {C.GREEN}Instructions:{C.RESET} ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if not instructions:
                    break
                print(f"  {C.DIM}Retrying with instructions...{C.RESET}")
        print()

    def _cmd_status(self, arg):
        """/status — .deep/ dashboard."""
        deep_dir = self.working_dir / ".deep"
        if not deep_dir.exists():
            print(f"{C.DIM}No .deep/ directory. Run /scan first.{C.RESET}")
            return

        print(f"\n  {C.BOLD}.deep/ status{C.RESET}\n")

        # Last scan
        report_path = deep_dir / "report.md"
        if report_path.exists():
            age = time.time() - report_path.stat().st_mtime
            age_str = self._format_age(age)
            findings_dir = deep_dir / "findings"
            file_count = len(list(findings_dir.glob("*.md"))) if findings_dir.exists() else 0
            print(f"  Last scan: {C.CYAN}{age_str}{C.RESET} "
                  f"({file_count} files)")
        else:
            print(f"  Last scan: {C.DIM}none{C.RESET}")

        # Issues
        issues_path = deep_dir / "issues.json"
        if issues_path.exists():
            try:
                raw = json.loads(issues_path.read_text(encoding="utf-8"))
                self._ensure_version(raw)
                issues = raw.get("issues", []) if isinstance(raw, dict) else raw
                total = len(issues)
                fixed = sum(1 for i in issues if i.get("status") == "fixed")
                open_issues = [i for i in issues if i.get("status") != "fixed"]
                counts = {}
                for i in open_issues:
                    p = i.get("priority", "P2")
                    counts[p] = counts.get(p, 0) + 1
                parts = [f"{v} {k}" for k, v in sorted(counts.items())]
                summary = ", ".join(parts) if parts else "all fixed"
                pct = int(fixed / total * 100) if total else 0
                print(f"  Issues: {C.CYAN}{total}{C.RESET} total "
                      f"({summary})")
                print(f"  Fixed: {C.GREEN}{fixed}{C.RESET} ({pct}%)")
            except (json.JSONDecodeError, OSError):
                print(f"  Issues: {C.RED}error reading{C.RESET}")
        else:
            print(f"  Issues: {C.DIM}none{C.RESET}")

        # Skills
        skills_dir = deep_dir / "skills"
        skills = []
        if skills_dir.exists():
            skills = [p.stem for p in skills_dir.glob("*.md")
                      if not p.stem.endswith("_lens")]
        global_skills = []
        if GLOBAL_SKILLS_DIR.exists():
            global_skills = [p.stem for p in GLOBAL_SKILLS_DIR.glob("*.md")
                             if not p.stem.endswith("_lens")]
        all_skills = sorted(set(skills + global_skills))
        if all_skills:
            print(f"  Skills: {C.CYAN}{', '.join(all_skills)}{C.RESET}")
        else:
            print(f"  Skills: {C.DIM}none{C.RESET}")

        # Model
        print(f"  Model: {C.CYAN}{self.session.model}{C.RESET}")
        print()

    def _ensure_version(self, data, warn_label=None):
        """Ensure JSON data has _version field. Migrates v0 (missing) to v1."""
        if isinstance(data, dict) and "_version" not in data:
            data["_version"] = 1
            if warn_label:
                print(f"  {C.DIM}Migrated {warn_label} to v1{C.RESET}")
        return data

    @staticmethod
    def _strip_version(data):
        """Return data dict without _version key (for config reads)."""
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if k != "_version"}
        return data

    @staticmethod
    def _format_age(seconds):
        """Format age in seconds to human-readable string."""
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            return f"{int(seconds / 60)}m ago"
        if seconds < 86400:
            return f"{int(seconds / 3600)}h ago"
        return f"{int(seconds / 86400)}d ago"

    # ── Live config layer ────────────────────────────────────────────────

    def _config(self):
        """Read .deep/config.json, merge with defaults. Fresh every call."""
        cfg = dict(DEFAULT_CONFIG)
        path = self.working_dir / ".deep" / "config.json"
        if path.exists():
            try:
                override = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(override, dict):
                    self._ensure_version(override)
                    cfg.update(self._strip_version(override))
            except (json.JSONDecodeError, OSError):
                pass
        return cfg

    def _config_set(self, key, value):
        """Update a single key in .deep/config.json. Takes effect immediately."""
        path = self.working_dir / ".deep" / "config.json"
        cfg = {}
        if path.exists():
            try:
                cfg = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        cfg[key] = value
        cfg["_version"] = 1
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    def _get_lenses(self):
        """Active lens list — reads config fresh, validates files exist."""
        names = self._config().get("lenses", ["l12"])
        valid = []
        for name in names:
            local = self.working_dir / ".deep" / "lenses" / f"{name}.md"
            builtin = LENS_DIR / f"{name}.md"
            if local.exists() or builtin.exists():
                valid.append(name)
        return valid if valid else ["l12"]

    def _cmd_reload(self):
        """Hot-reload: reimport module, rebind all methods on running instance."""
        import importlib.util
        try:
            spec = importlib.util.spec_from_file_location(
                "_prism_reload", SCRIPT_DIR / "prism.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            old_methods = {n for n in dir(self.__class__)
                          if not n.startswith('__')}
            self.__class__ = mod.PrismREPL
            new_methods = {n for n in dir(self.__class__)
                          if not n.startswith('__')}
            added = new_methods - old_methods
            removed = old_methods - new_methods
            parts = [f"{len(new_methods)} methods"]
            if added:
                parts.append(f"+{len(added)} new")
            if removed:
                parts.append(f"-{len(removed)} removed")
            lenses = self._get_lenses()
            print(f"  {C.GREEN}Code: {', '.join(parts)}{C.RESET}")
            print(f"  {C.GREEN}Config: "
                  f"{len(lenses)} lenses{C.RESET}")
        except Exception as e:
            print(f"  {C.RED}Reload failed: {e}{C.RESET}")
            print(f"  {C.DIM}Running code unchanged.{C.RESET}")

    # ── Cook (lens generation) ───────────────────────────────────────────

    def _cmd_cook(self, arg):
        """/cook <domain> [input] — generate domain-specific lenses via B3 meta-cooker.

        /cook readme                  — generate lenses for analyzing READMEs
        /cook legal-contracts         — generate lenses for legal documents
        /cook readme README.md        — generate lenses informed by a sample file
        """
        if not arg:
            print(f"{C.YELLOW}Usage: /cook <domain> [sample-file]{C.RESET}")
            return

        parts = arg.split(maxsplit=1)
        domain = parts[0].lower().replace(" ", "-")
        sample_content = None

        # Optional sample file to inform lens generation
        if len(parts) > 1:
            resolved = self._resolve_file(parts[1])
            if resolved and resolved.is_file():
                try:
                    sample_content = resolved.read_text(
                        encoding="utf-8", errors="replace")[:3000]
                except OSError:
                    pass
            else:
                print(f"{C.YELLOW}Sample file not found: {parts[1]} "
                      f"(cooking without sample){C.RESET}")

        lenses = self._cook_lenses(domain, sample_content)
        if lenses:
            print(f"\n{C.GREEN}Cooked {len(lenses)} lenses → "
                  f"lenses/{domain}/{C.RESET}")
            print(f"  {C.DIM}Use: /scan <input> discover  or  "
                  f"/prism {domain}/<name>{C.RESET}")

    def _cook_lenses(self, domain, sample_content=None):
        """Generate domain-specific lenses using B3 meta-cooker.

        Returns list of (name, prompt) tuples, or empty list on failure.
        Saves each lens to .deep/lenses/<domain>/<name>.md (project-local).
        """
        prompt = COOK_PROMPT.format(domain=domain)
        user_input = f"Generate analytical lenses for the domain: {domain}"
        if sample_content:
            user_input += (
                f"\n\nHere is a sample artifact from this domain "
                f"to inform your lens design:\n\n{sample_content}")

        print(f"{C.CYAN}Cooking lenses for '{domain}'...{C.RESET}")
        raw = self._call_model(prompt, user_input, timeout=90)

        parsed = self._parse_stage_json(raw, "cook")
        if not isinstance(parsed, list):
            print(f"{C.RED}Cook failed — model didn't return valid JSON{C.RESET}")
            return []

        # Save lenses to project-local .deep/lenses/<domain>/
        lens_dir = self.working_dir / ".deep" / "lenses" / domain
        lens_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for item in parsed:
            name = item.get("name", "").strip()
            text = item.get("prompt", "").strip()
            if not name or not text:
                continue
            # Sanitize name
            name = re.sub(r'[^a-z0-9_]', '_', name.lower())
            (lens_dir / f"{name}.md").write_text(text, encoding="utf-8")
            results.append((name, text))
            # Preview: first 60 chars
            preview = text[:60] + ("..." if len(text) > 60 else "")
            print(f"  {C.GREEN}{name}{C.RESET}: {C.DIM}{preview}{C.RESET}")

        return results

    def _list_domain_lenses(self, domain):
        """List lens names for a cooked domain. Checks .deep/lenses/ first, then built-in."""
        # Project-local first
        local = self.working_dir / ".deep" / "lenses" / domain
        if local.is_dir():
            return [p.stem for p in sorted(local.glob("*.md"))]
        # Built-in fallback
        builtin = LENS_DIR / domain
        if builtin.is_dir():
            return [p.stem for p in sorted(builtin.glob("*.md"))]
        return []

    def _cmd_lenses(self, arg):
        """/lenses — list all available lenses."""
        # Built-in lenses (top-level .md files in LENS_DIR)
        builtin = []
        for p in sorted(LENS_DIR.glob("*.md")):
            builtin.append(p.stem)

        # Custom domain lenses (subdirectories)
        domains = {}
        for d in sorted(LENS_DIR.iterdir()):
            if d.is_dir() and not d.name.startswith("."):
                names = [p.stem for p in sorted(d.glob("*.md"))]
                if names:
                    domains[d.name] = names

        # Also check .deep/lenses/
        local_dir = self.working_dir / ".deep" / "lenses"
        local_domains = {}
        if local_dir.is_dir():
            for p in sorted(local_dir.glob("*.md")):
                builtin.append(f"{p.stem} (local)")
            for d in sorted(local_dir.iterdir()):
                if d.is_dir():
                    names = [p.stem for p in sorted(d.glob("*.md"))]
                    if names:
                        local_domains[d.name] = names

        # Print
        print(f"\n{C.BOLD}Built-in ({len(builtin)}):{C.RESET}")
        for name in builtin:
            marker = ""
            if self._active_lens_name == name.replace(" (local)", ""):
                marker = f" {C.GREEN}← active{C.RESET}"
            print(f"  {C.CYAN}{name}{C.RESET}{marker}")

        if domains:
            print(f"\n{C.BOLD}Cooked:{C.RESET}")
            for domain, names in domains.items():
                print(f"  {C.BOLD}{domain}/{C.RESET} "
                      f"({len(names)} lenses)")
                for n in names:
                    full = f"{domain}/{n}"
                    marker = ""
                    if self._active_lens_name == full:
                        marker = f" {C.GREEN}← active{C.RESET}"
                    print(f"    {C.DIM}{n}{C.RESET}{marker}")

        if local_domains:
            print(f"\n{C.BOLD}Project-local (.deep/lenses/):{C.RESET}")
            for domain, names in local_domains.items():
                print(f"  {domain}/ ({len(names)}): "
                      f"{', '.join(names)}")

        if not domains and not local_domains:
            print(f"\n  {C.DIM}No custom lenses yet. "
                  f"Use /cook <domain> to generate some.{C.RESET}")

        # Show active
        lens = self._active_lens_name or "none"
        depth = self._chat_mode
        print(f"\n{C.DIM}Active: lens={lens}, "
              f"depth={depth}{C.RESET}")
        print(f"{C.DIM}Use /prism <lens> to activate a lens for chat{C.RESET}\n")

    # ── Deep analysis ────────────────────────────────────────────────────

    def _load_lens(self, name):
        """Load a lens prompt. Supports subdirs: 'readme/promise_credibility'.
        Checks .deep/lenses/ first, then built-in lenses/."""
        # name may contain / for domain subdirs
        rel = pathlib.PurePosixPath(name)
        local = self.working_dir / ".deep" / "lenses" / f"{rel}.md"
        if local.exists():
            return local.read_text(encoding="utf-8")
        path = LENS_DIR / f"{rel}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def _load_intent(self, name, fallback=""):
        """Load prompt from .deep/prompts/ -> shipped prompts/ -> fallback."""
        # Tier 1: project-local override
        local = self.working_dir / ".deep" / "prompts" / f"{name}.md"
        if local.exists():
            return local.read_text(encoding="utf-8")
        # Tier 2: shipped prompts
        shipped = PROMPTS_DIR / f"{name}.md"
        if shipped.exists():
            return shipped.read_text(encoding="utf-8")
        # Tier 3: hardcoded fallback
        return fallback

    def _run_lens_oneshot(self, lens_name, content, question="",
                          model=None):
        """Run a single lens analysis (non-streaming). Returns output text."""
        if model is None:
            model = self.session.model
        prompt = self._load_lens(lens_name)
        if not prompt:
            return f"[Lens '{lens_name}' not found]"
        msg = content
        if question:
            msg = f"{question}\n\n{content}"
        return self._claude.call(prompt, msg, model=model, timeout=120)

    def _resolve_file(self, arg):
        """Resolve a file path relative to working_dir."""
        if not arg:
            return None
        path = pathlib.Path(arg)
        if not path.is_absolute():
            path = self.working_dir / path
        return path if path.exists() else None

    def _get_deep_content(self, file_arg):
        """Get content for deep analysis — from arg or queued files."""
        if file_arg:
            path = self._resolve_file(file_arg)
            if path:
                return path.read_text(encoding="utf-8", errors="replace"), path.name
            else:
                return None, file_arg
        elif self.queued_files:
            parts = []
            names = []
            for fpath in self.queued_files:
                try:
                    parts.append(fpath.read_text(encoding="utf-8", errors="replace"))
                    names.append(fpath.name)
                except Exception:
                    pass
            self.queued_files.clear()
            return "\n\n".join(parts), ", ".join(names)
        return None, None

    @staticmethod
    def _parse_scan_args(arg):
        """Parse /scan arguments into structured dict.

        Returns {"mode", "arg", "target_goal", "deep_goal",
                 "fix_auto", "expand_indices"}.
        Modes: single, full, discover, expand, target, deep, fix.
        """
        result = {"mode": "single", "arg": arg, "target_goal": None,
                  "deep_goal": None, "fix_auto": False,
                  "expand_indices": None, "expand_mode": None}
        if not arg:
            return result

        # 1. Check for deep="..." or deep=N
        deep_match = (
            re.search(r'deep\s*=\s*"(.+?)"', arg) or
            re.search(r"deep\s*=\s*'(.+?)'", arg) or
            re.search(r'deep\s*=\s*(\d+)', arg)
        )
        if deep_match:
            val = deep_match.group(1)
            result["mode"] = "deep"
            result["deep_goal"] = int(val) if val.isdigit() else val
            result["arg"] = arg[:deep_match.start()].strip()
            return result

        # 2. Check for target="..." or target=N
        target_match = (
            re.search(r'target\s*=\s*"(.+?)"', arg) or
            re.search(r"target\s*=\s*'(.+?)'", arg) or
            re.search(r'target\s*=\s*(\d+)', arg)
        )
        if target_match:
            val = target_match.group(1)
            result["mode"] = "target"
            result["target_goal"] = int(val) if val.isdigit() else val
            result["arg"] = arg[:target_match.start()].strip()
            return result

        # 3. Check for expand with optional indices + prism mode
        #    expand | expand single | expand full | expand 1,3,5 full
        expand_match = re.search(r'\bexpand\b\s*(.*?)\s*$', arg)
        if expand_match:
            result["mode"] = "expand"
            tail = expand_match.group(1).strip()
            if re.search(r'\bfull\b', tail):
                result["expand_mode"] = "full"
            elif re.search(r'\bsingle\b', tail):
                result["expand_mode"] = "single"
            idx_str = re.sub(r'\b(single|full)\b', '', tail).strip()
            result["expand_indices"] = idx_str if idx_str else None
            result["arg"] = arg[:expand_match.start()].strip() or None
            return result

        # 4. Check for discover full
        disc_full = re.search(r'\bdiscover\s+full\s*$', arg)
        if disc_full:
            result["mode"] = "discover_full"
            result["arg"] = arg[:disc_full.start()].strip() or None
            return result

        # 5. Trailing keywords
        parts = arg.rsplit(maxsplit=2)
        if (len(parts) >= 3 and parts[-2] == "fix"
                and parts[-1] == "auto"):
            result["mode"] = "fix"
            result["fix_auto"] = True
            result["arg"] = " ".join(parts[:-2])
        elif len(parts) >= 2 and parts[-1] == "fix":
            result["mode"] = "fix"
            result["arg"] = " ".join(parts[:-1])
        elif len(parts) >= 2 and parts[-1] in (
                "full", "discover"):
            result["mode"] = parts[-1]
            result["arg"] = " ".join(parts[:-1])
        elif len(parts) == 1 and parts[0] in (
                "full", "discover"):
            result["mode"] = parts[0]
            result["arg"] = None

        return result

    def _cmd_scan(self, arg):
        """/scan <file|text|dir> [mode]

        Single & Full Prism:
          /scan file.py                  — Single Prism (1 L12 call)
          /scan file.py full             — Full Prism (3 calls: L12 → adv → synth)

        Discover & Expand:
          /scan file.py discover         — Single Prism discover (cook areas, list)
          /scan file.py discover full    — Full Prism discover (multi-pass, deeper)
          /scan file.py expand           — pick areas → single/full per area
          /scan file.py expand 1,3 single — areas 1,3 as single prism
          /scan file.py expand 1,3 full  — areas 1,3 as full prism

        Targeted:
          /scan file.py target="X"       — cook goal-specific lens + run
          /scan file.py target=N         — run Nth discover lens
          /scan file.py deep="X"         — cook 3-lens system + run pipeline
          /scan file.py deep=N           — same, Nth discover area

        Fix loop:
          /scan file.py fix              — scan → fix → re-scan (interactive)
          /scan file.py fix auto         — same, automatic

        Project-level:
          /scan src/                     — L12 batch (all files)
          /scan src/ discover            — project-level area discovery
          /scan src/ expand              — project-level expand
        """
        if not arg:
            print(f"{C.YELLOW}Usage: /scan <file|text> "
                  f"[full|discover|deep=\"...\"|target=\"...\"]  {C.RESET}")
            return

        parsed = self._parse_scan_args(arg)
        mode = parsed["mode"]
        arg = parsed["arg"]

        if not arg:
            print(f"{C.YELLOW}Usage: /scan <file|text> "
                  f"[full|discover|deep=\"...\"|target=\"...\"]  {C.RESET}")
            return

        input_arg = arg

        # Try as directory
        resolved = self._resolve_file(input_arg)
        if resolved and resolved.is_dir():
            if mode in ("discover", "discover_full", "expand"):
                # Project-level discover/expand
                project_map = self._build_project_map(resolved)
                if not project_map:
                    print(f"{C.RED}No code files found in "
                          f"{resolved}{C.RESET}")
                    return
                dir_name = resolved.name or str(resolved)
                if mode == "discover":
                    self._run_discover(
                        project_map, dir_name, general=True)
                elif mode == "discover_full":
                    self._run_discover_full(
                        project_map, dir_name, general=True)
                else:
                    self._run_expand(
                        project_map, dir_name,
                        indices_str=parsed["expand_indices"],
                        expand_mode=parsed["expand_mode"],
                        general=True)
                return
            # Default: L12 batch scan
            self._scan_directory(str(resolved))
            return

        # Try as file
        content, name = self._get_deep_content(input_arg)
        is_file = bool(content)

        if not is_file:
            # Text mode: domain-neutral
            content = input_arg
            name = input_arg[:40] + ("..." if len(input_arg) > 40 else "")

        general = not is_file

        if mode == "fix":
            if not is_file:
                print(f"{C.YELLOW}Fix mode requires a file path{C.RESET}")
                return
            self._scan_fix_loop(content, name, auto=parsed["fix_auto"])
            return
        elif mode == "full":
            self._run_full_pipeline(content, name, general=general)
        elif mode == "discover":
            self._run_discover(content, name, general=general)
        elif mode == "discover_full":
            self._run_discover_full(content, name, general=general)
        elif mode == "expand":
            self._run_expand(content, name,
                             indices_str=parsed["expand_indices"],
                             expand_mode=parsed["expand_mode"],
                             general=general)
        elif mode == "deep":
            self._run_deep(content, name, parsed["deep_goal"],
                           general=general)
        elif mode == "target":
            goal = parsed["target_goal"]
            if isinstance(goal, int):
                self._run_target_by_index(content, name, goal,
                                          general=general)
            else:
                self._run_target(content, name, goal, general=general)
        else:
            # Single L12
            lens = "l12" if is_file else "l12_general"
            if not is_file:
                print(f"{C.CYAN}L12 structural analysis (general){C.RESET}")
            else:
                print(f"{C.CYAN}L12 structural analysis{C.RESET}")
            self._run_single_lens_streaming(lens, content, name)

        if is_file:
            self._suggest_next("scan", {"file": name})

    def _scan_fix_loop(self, content, name, auto=False):
        """Closed-loop: scan → extract context → fix → re-scan → done.

        Runs up to 3 iterations. Stops when no new issues found or
        no fixes approved in a pass.
        """
        deep_dir = self.working_dir / ".deep"
        max_iterations = 3
        prev_issues = []

        for iteration in range(1, max_iterations + 1):
            # ── Phase 1: Scan (re-read file on iterations > 1) ──
            if iteration > 1:
                fresh_content, _ = self._get_deep_content(name)
                if fresh_content:
                    content = fresh_content
                print(f"\n  {C.BOLD}{C.CYAN}── Re-scan (iteration "
                      f"{iteration}/{max_iterations}) ──{C.RESET}\n")

            print(f"{C.CYAN}L12 structural analysis{C.RESET}")
            scan_output = self._run_single_lens_streaming(
                "l12", content, name)

            if not scan_output:
                print(f"{C.YELLOW}Scan produced no output{C.RESET}")
                break

            # ── Phase 2: Extract structural context ──
            structural_context = self._extract_structural_context(
                scan_output)
            if structural_context:
                print(f"  {C.DIM}Structural context extracted "
                      f"({len(structural_context)} chars){C.RESET}")

            # ── Phase 3: Extract issues ──
            issues_path = deep_dir / "issues.json"
            if issues_path.exists():
                issues_path.unlink()

            print(f"  {C.DIM}Extracting issues from findings...{C.RESET}")
            issues = self._heal_extract_from_reports(deep_dir)

            if not issues:
                print(f"{C.GREEN}No issues found.{C.RESET}")
                break

            # On re-scan, only fix genuinely new issues
            if iteration > 1:
                issues = self._diff_issues(prev_issues, issues)
                if not issues:
                    print(f"  {C.GREEN}No new issues — loop "
                          f"complete.{C.RESET}")
                    break
                print(f"  {C.DIM}{len(issues)} new issue(s) "
                      f"to fix{C.RESET}")

            self._heal_save_issues(deep_dir, issues)
            prev_issues.extend(issues)

            # ── Phase 4: Fix each issue with structural context ──
            open_issues = [i for i in issues
                           if i.get("status") != "fixed"]
            if not open_issues:
                print(f"  {C.GREEN}All issues already fixed!{C.RESET}")
                break

            print(f"\n  {C.BOLD}{C.CYAN}FIX{C.RESET}  "
                  f"{len(open_issues)} issue(s)"
                  f"{' (auto)' if auto else ''}\n")

            if auto:
                self._auto_mode = True

            approved_count = 0
            for idx, issue in enumerate(open_issues, 1):
                title = issue.get("title", "untitled")
                print(f"  {C.BOLD}{C.CYAN}── Issue {idx}/"
                      f"{len(open_issues)}: {title} ──{C.RESET}")

                attempts = 0
                instructions = ""
                while attempts < 2:
                    attempts += 1
                    fix_issue = dict(issue)
                    if instructions:
                        fix_issue["action"] = (
                            f"{issue.get('action', '')} "
                            f"User instructions: {instructions}")

                    result, snapshots = self._heal_fix_one(
                        fix_issue,
                        structural_context=structural_context)

                    if result == "approved":
                        approved_count += 1
                        _t = self._resolve_file(
                            fix_issue.get("file", ""))
                        pre_fix = (snapshots.get(str(_t))
                                   if _t else None)
                        verdict = self._heal_verify(
                            issue, pre_fix_snapshot=pre_fix)
                        issue["status"] = verdict
                        break
                    elif result == "rejected":
                        break
                    elif result == "instructed":
                        if auto:
                            break
                        try:
                            instructions = input(
                                f"  {C.GREEN}Instructions:"
                                f"{C.RESET} ").strip()
                        except (EOFError, KeyboardInterrupt):
                            print()
                            break
                        if not instructions:
                            break
                        print(f"  {C.DIM}Retrying with "
                              f"instructions...{C.RESET}")
                print()

            self._heal_save_issues(deep_dir, issues)
            self._auto_mode = False

            # Termination: no fixes approved → stop
            if approved_count == 0:
                print(f"  {C.DIM}No fixes approved — stopping "
                      f"loop.{C.RESET}")
                break

            # Last iteration — don't re-scan
            if iteration == max_iterations:
                print(f"  {C.DIM}Max iterations reached "
                      f"({max_iterations}).{C.RESET}")
                break

            # Ask whether to re-scan (interactive only)
            if not auto:
                try:
                    cont = input(
                        f"  {C.GREEN}Re-scan to verify? "
                        f"(y/n):{C.RESET} ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if cont not in ("y", "yes"):
                    break

        # Final summary
        self._suggest_next("scan", {"file": name})

    def _build_project_map(self, dir_path):
        """Build a compact project summary for project-level discover.

        Returns a string with: file tree + first 5 lines of each file
        (signatures, imports, class names). Keeps it under ~4000 chars
        so the cooker can reason about the whole project cheaply.
        """
        files = self._collect_files(str(dir_path))
        if not files:
            return ""

        parts = [f"# Project: {dir_path.name}\n",
                 f"{len(files)} files\n\n## File tree\n"]

        # File tree with sizes
        for f in files:
            try:
                rel = f.relative_to(dir_path)
            except ValueError:
                rel = f.name
            size = f.stat().st_size
            parts.append(f"  {rel} ({size} bytes)")

        # Sample: first 5 lines of each file (imports, class defs)
        parts.append("\n\n## File signatures\n")
        budget = 3000
        for f in files:
            if budget <= 0:
                parts.append(f"\n... ({len(files)} files total)")
                break
            try:
                rel = f.relative_to(dir_path)
            except ValueError:
                rel = f.name
            try:
                lines = f.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()[:5]
                snippet = "\n".join(lines)
                entry = f"\n### {rel}\n```\n{snippet}\n```\n"
                parts.append(entry)
                budget -= len(entry)
            except Exception:
                pass

        return "\n".join(parts)

    def _scan_directory(self, target):
        """Scan all code files in a directory with L12, save findings."""
        files = self._collect_files(target)
        if not files:
            print(f"{C.RED}No files found: {target}{C.RESET}")
            return

        deep_dir = self.working_dir / ".deep" / "findings"
        self._cleanup_old_findings(deep_dir)
        deep_dir.mkdir(parents=True, exist_ok=True)

        print(f"{C.BOLD}Scan: {len(files)} files x L12{C.RESET}")
        print(f"{C.DIM}Saving to .deep/findings/{C.RESET}\n")

        for i, fpath in enumerate(files, 1):
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                print(f"  {C.DIM}[{i}/{len(files)}] {fpath.name}{C.RESET}")
                result = self._run_lens_oneshot("l12", content)
                if result and not result.startswith("["):
                    self._save_deep_finding(fpath.name, "l12", result)
            except Exception as e:
                print(f"  {C.RED}Error: {fpath.name}: {e}{C.RESET}")

        print(f"\n{C.GREEN}Scan complete: {len(files)} files{C.RESET}")
        print(f"  {C.DIM}Findings: .deep/findings/<file>.md{C.RESET}")
        self._suggest_next("scan")

    def _run_full_pipeline(self, content, file_name, general=False):
        """Run the 3-call pipeline: L12 → adversarial → synthesis. All streaming.

        When general=True, uses domain-neutral lenses (l12_general*) instead
        of code-specific ones (l12*).
        """
        # Select lens variants
        if general:
            l12_lens = "l12_general"
            adv_lens = "l12_general_adversarial"
            synth_lens = "l12_general_synthesis"
            content_label = "INPUT"
        else:
            l12_lens = "l12"
            adv_lens = "l12_complement_adversarial"
            synth_lens = "l12_synthesis"
            content_label = "SOURCE CODE"

        # Call 1: L12 structural analysis
        l12_output = self._run_single_lens_streaming(
            l12_lens, content, file_name,
            label=f"L12 structural ── {file_name}")

        if not l12_output or self._interrupted:
            return

        # Call 2: Adversarial challenge
        adv_input = (
            f"# {content_label}\n\n{content}\n\n---\n\n"
            f"# STRUCTURAL ANALYSIS (from previous pass)\n\n{l12_output}"
        )
        adv_output = self._run_single_lens_streaming(
            adv_lens, adv_input, file_name,
            label="Adversarial challenge",
            message=adv_input)

        if not adv_output or self._interrupted:
            return

        # Call 3: Synthesis
        synth_input = (
            f"# {content_label}\n\n{content}\n\n---\n\n"
            f"# ANALYSIS 1: STRUCTURAL ANALYSIS\n\n{l12_output}\n\n---\n\n"
            f"# ANALYSIS 2: CONTRADICTION ANALYSIS\n\n{adv_output}"
        )
        synth_output = self._run_single_lens_streaming(
            synth_lens, synth_input, file_name,
            label="Synthesis",
            message=synth_input)

        # Save combined output
        combined = (
            f"# Full Pipeline: {file_name}\n\n"
            f"## L12 STRUCTURAL\n\n{l12_output}\n\n"
            f"## ADVERSARIAL CHALLENGE\n\n{adv_output}\n\n"
            f"## SYNTHESIS\n\n{synth_output or '(not completed)'}\n\n"
        )
        self._save_deep_finding(file_name, "full", combined)
        print(f"\n  {C.DIM}Use /fix to pick issues, or /fix auto to fix all{C.RESET}")

    @staticmethod
    def _parse_selection(selection_str, max_val):
        """Parse '1,3,5-7' or '*' into sorted list of 1-based ints."""
        if not selection_str or selection_str.strip() == '*':
            return list(range(1, max_val + 1))
        indices = set()
        for part in selection_str.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    start, end = part.split('-', 1)
                    for i in range(int(start), int(end) + 1):
                        if 1 <= i <= max_val:
                            indices.add(i)
                except ValueError:
                    pass
            else:
                try:
                    i = int(part)
                    if 1 <= i <= max_val:
                        indices.add(i)
                except ValueError:
                    pass
        return sorted(indices)

    def _load_cached_pipeline(self, cache_dir):
        """Load cached pipeline lenses from a directory.

        Files named NN_name.md (e.g. 00_primary.md) are loaded in order.
        Returns list of {name, prompt, role, order} dicts, or None.
        """
        if not cache_dir.is_dir():
            return None
        files = sorted(cache_dir.glob("*.md"))
        if len(files) < 2:
            return None
        lenses = []
        for f in files:
            text = f.read_text(encoding="utf-8")
            name = f.stem.split("_", 1)[1] if "_" in f.stem else f.stem
            lenses.append({"name": name, "prompt": text,
                           "role": name, "order": len(lenses)})
        return lenses

    def _run_discover(self, content, file_name, general=False):
        """Discover mode: cook area lenses, show numbered list, stop.

        1. Detect/infer domain from content
        2. Cook lenses if none cached (B3 meta-cooker)
        3. Display numbered list with previews
        4. Save to self._discover_results + .deep/discover.json
        """
        domain = self._infer_domain(content, file_name, general)
        print(f"{C.CYAN}Discover: domain='{domain}'{C.RESET}")

        # Check for cached lenses
        lens_names = self._list_domain_lenses(domain)
        if not lens_names:
            sample = content[:3000] if len(content) > 3000 else content
            results = self._cook_lenses(domain, sample)
            if not results:
                print(f"{C.RED}Could not generate lenses for "
                      f"'{domain}'{C.RESET}")
                return
            lens_names = [name for name, _ in results]
        else:
            print(f"{C.DIM}Using {len(lens_names)} cached lenses from "
                  f"lenses/{domain}/{C.RESET}")

        # Build discover results with lens text previews
        discover = []
        for lens_name in lens_names:
            full_name = f"{domain}/{lens_name}"
            text = self._load_lens(full_name) or ""
            discover.append({
                "name": lens_name,
                "lens_path": full_name,
                "preview": text[:80] + ("..." if len(text) > 80 else ""),
                "domain": domain,
            })

        self._discover_results = discover
        self._save_discover_results(discover, file_name)

        # Display numbered list
        print(f"\n{C.BOLD}Discovered {len(discover)} angles:{C.RESET}\n")
        for i, item in enumerate(discover, 1):
            print(f"  {C.CYAN}{i}.{C.RESET} {C.GREEN}{item['name']}{C.RESET}")
            print(f"     {C.DIM}{item['preview']}{C.RESET}")

        print(f"\n  {C.DIM}expand             pick areas, choose "
              f"single/full per area{C.RESET}")
        print(f"  {C.DIM}expand 1,3 single  run areas 1,3 "
              f"as single prism{C.RESET}")
        print(f"  {C.DIM}expand 1,3 full    run areas 1,3 "
              f"as full prism{C.RESET}")
        print(f"  {C.DIM}discover full      deeper discover "
              f"(multi-pass){C.RESET}")

    def _run_discover_full(self, content, file_name, general=False):
        """Full prism discover: multi-pass area discovery.

        1. Cook a discover pipeline (cooker decides structure)
        2. Run each pass, chaining outputs
        3. Parse final output for area lenses
        4. Save and display as normal discover results

        The cooker generates multiple discovery passes — e.g.
        initial discovery, blind spot check, synthesis — producing
        a more thorough set of areas than single discover.
        """
        domain = self._infer_domain(content, file_name, general)
        sample = content[:3000] if len(content) > 3000 else content

        print(f"{C.CYAN}Discover Full Prism: "
              f"domain='{domain}'{C.RESET}")

        # Step 1: Cook the discover pipeline
        prompt = COOK_DISCOVER_FULL_PROMPT.format(domain=domain)
        user_input = (
            f"Generate a multi-pass discovery pipeline "
            f"for: {domain}\n\n"
            f"Sample artifact:\n\n{sample}")

        print(f"  {C.CYAN}Cooking discover pipeline...{C.RESET}")
        raw = self._call_model(prompt, user_input, timeout=90)

        parsed = self._parse_stage_json(raw, "cook_discover_full")
        if not isinstance(parsed, list) or len(parsed) < 2:
            print(f"{C.RED}Failed to cook discover pipeline"
                  f"{C.RESET}")
            return

        # Step 2: Run the pipeline
        lenses = []
        for i, item in enumerate(parsed):
            name = item.get("name", f"pass_{i + 1}")
            name = re.sub(r'[^a-z0-9_]', '_', name.lower())
            text = item.get("prompt", "")
            role = item.get("role", f"pass_{i + 1}")
            if not text:
                continue
            lenses.append({"name": name, "prompt": text,
                           "role": role})
            preview = text[:60] + (
                "..." if len(text) > 60 else "")
            print(f"    {C.GREEN}{role}{C.RESET} ({name}): "
                  f"{C.DIM}{preview}{C.RESET}")

        if len(lenses) < 2:
            print(f"{C.RED}Need at least 2 passes{C.RESET}")
            return

        outputs = []
        for i, lens in enumerate(lenses):
            role = lens.get("role", lens["name"])
            if i == 0:
                msg = (f"Discover all structural areas worth "
                       f"investigating.\n\n{sample}")
            else:
                parts = [f"# ARTIFACT\n\n{sample}"]
                for j, prev in enumerate(outputs):
                    prev_role = lenses[j].get(
                        "role", lenses[j]["name"]).upper()
                    parts.append(
                        f"# PASS {j + 1}: {prev_role}"
                        f"\n\n{prev}")
                msg = "\n\n---\n\n".join(parts)

            print(f"\n{C.BOLD}{C.BLUE}── Discover {role} ── "
                  f"{file_name} ──{C.RESET}")
            backend = ClaudeBackend(
                model=self.session.model,
                working_dir=str(self.working_dir),
                system_prompt=lens["prompt"],
                tools=False,
            )
            output = self._stream_and_capture(backend, msg)

            if output and not self._interrupted:
                outputs.append(output)
            if not output or self._interrupted:
                break

        if not outputs:
            return

        # Step 3: Extract area lenses from final output
        # Use the regular cooker on the synthesized discovery
        final_context = outputs[-1]
        print(f"\n  {C.CYAN}Extracting area lenses from "
              f"discovery...{C.RESET}")
        cook_prompt = COOK_PROMPT.format(domain=domain)
        cook_input = (
            f"Generate analytical lenses for: {domain}\n\n"
            f"Deep discovery analysis:\n\n{final_context}\n\n"
            f"Sample artifact:\n\n{sample}")

        raw_lenses = self._call_model(
            cook_prompt, cook_input, timeout=90)
        lens_parsed = self._parse_stage_json(
            raw_lenses, "cook_discover_full_lenses")
        if not isinstance(lens_parsed, list):
            print(f"{C.RED}Failed to extract lenses{C.RESET}")
            return

        # Save lenses and build discover results
        lens_dir = (self.working_dir / ".deep" / "lenses"
                    / domain)
        lens_dir.mkdir(parents=True, exist_ok=True)

        discover = []
        for item in lens_parsed:
            lname = item.get("name", "").strip()
            ltext = item.get("prompt", "").strip()
            if not lname or not ltext:
                continue
            lname = re.sub(r'[^a-z0-9_]', '_', lname.lower())
            (lens_dir / f"{lname}.md").write_text(
                ltext, encoding="utf-8")
            full_name = f"{domain}/{lname}"
            discover.append({
                "name": lname,
                "lens_path": full_name,
                "preview": ltext[:80] + (
                    "..." if len(ltext) > 80 else ""),
                "domain": domain,
            })

        self._discover_results = discover
        self._save_discover_results(discover, file_name)

        print(f"\n{C.BOLD}Discovered {len(discover)} "
              f"angles (full prism):{C.RESET}\n")
        for i, item in enumerate(discover, 1):
            print(f"  {C.CYAN}{i}.{C.RESET} "
                  f"{C.GREEN}{item['name']}{C.RESET}")
            print(f"     {C.DIM}{item['preview']}{C.RESET}")

        print(f"\n  {C.DIM}expand             pick areas, choose "
              f"single/full per area{C.RESET}")
        print(f"  {C.DIM}expand 1,3 single  run areas as "
              f"single prism{C.RESET}")
        print(f"  {C.DIM}expand 1,3 full    run areas as "
              f"full prism{C.RESET}")

    def _save_discover_results(self, results, file_name=None):
        """Persist discover results to .deep/discover_{stem}.json."""
        deep_dir = self.working_dir / ".deep"
        deep_dir.mkdir(parents=True, exist_ok=True)
        stem = pathlib.Path(file_name).stem if file_name else "last"
        path = deep_dir / f"discover_{stem}.json"
        path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    def _load_discover_results(self, file_name=None):
        """Load discover results from memory or .deep/discover_{stem}.json."""
        if self._discover_results:
            return self._discover_results
        stem = pathlib.Path(file_name).stem if file_name else "last"
        path = self.working_dir / ".deep" / f"discover_{stem}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._discover_results = data
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        return []

    def _run_target_by_index(self, content, file_name, index, general=False):
        """Run Nth discover lens (1-based index)."""
        results = self._load_discover_results(file_name)
        if not results:
            print(f"{C.YELLOW}No discover results. "
                  f"Run /scan <file> discover first.{C.RESET}")
            return
        if index < 1 or index > len(results):
            print(f"{C.YELLOW}Index {index} out of range "
                  f"(1-{len(results)}){C.RESET}")
            return

        item = results[index - 1]
        lens_path = item.get("lens_path", "")
        if not self._load_lens(lens_path):
            print(f"{C.RED}Lens '{lens_path}' not found{C.RESET}")
            return

        print(f"{C.CYAN}Running discover lens #{index}: "
              f"{item['name']}{C.RESET}")
        self._run_single_lens_streaming(
            lens_path, content, file_name,
            label=f"{item['name']} ── {file_name}")

    def _run_deep(self, content, file_name, goal, general=False):
        """Deep mode: cook a 3-lens system for a specific area + run pipeline.

        1. Resolve goal: int → discover result name, string → direct
        2. Check cache: .deep/lenses/_deep/{slug}/
        3. Cook 3 lenses if not cached (COOK_DEEP_PROMPT)
        4. Run 3-call pipeline: primary → adversarial → synthesis
        """
        # Resolve goal
        if isinstance(goal, int):
            results = self._load_discover_results(file_name)
            if not results:
                print(f"{C.YELLOW}No discover results. "
                      f"Run /scan <file> discover first.{C.RESET}")
                return
            if goal < 1 or goal > len(results):
                print(f"{C.YELLOW}Index {goal} out of range "
                      f"(1-{len(results)}){C.RESET}")
                return
            goal = results[goal - 1]["name"]

        slug = re.sub(r'[^a-z0-9]+', '_', goal.lower()).strip('_')[:40]
        deep_dir = (self.working_dir / ".deep" / "lenses"
                    / "_deep" / slug)

        # Check cache
        primary_path = deep_dir / "primary.md"
        adv_path = deep_dir / "adversarial.md"
        synth_path = deep_dir / "synthesis.md"

        if (primary_path.exists() and adv_path.exists()
                and synth_path.exists()):
            print(f"{C.DIM}Using cached deep lenses: {slug}{C.RESET}")
            primary_prompt = primary_path.read_text(encoding="utf-8")
            adv_prompt = adv_path.read_text(encoding="utf-8")
            synth_prompt = synth_path.read_text(encoding="utf-8")
        else:
            # Cook 3-lens system
            cook_prompt = COOK_DEEP_PROMPT.format(goal=goal)
            sample = content[:2000] if len(content) > 2000 else content
            user_input = (
                f"Generate a 3-lens pipeline for: {goal}\n\n"
                f"Sample artifact:\n\n{sample}")

            print(f"{C.CYAN}Cooking deep lens system for: "
                  f"{goal}{C.RESET}")
            raw = self._call_model(cook_prompt, user_input, timeout=90)

            parsed = self._parse_stage_json(raw, "cook_deep")
            if not isinstance(parsed, list) or len(parsed) < 3:
                print(f"{C.RED}Failed to generate deep lenses "
                      f"(need 3, got {len(parsed) if isinstance(parsed, list) else 0}){C.RESET}")
                return

            # Extract by role
            by_role = {}
            for item in parsed:
                role = item.get("role", "").lower()
                if role in ("primary", "adversarial", "synthesis"):
                    by_role[role] = item

            if len(by_role) < 3:
                # Fallback: assign by position
                roles = ["primary", "adversarial", "synthesis"]
                for i, role in enumerate(roles):
                    if role not in by_role and i < len(parsed):
                        by_role[role] = parsed[i]

            if len(by_role) < 3:
                print(f"{C.RED}Failed to generate all 3 lens "
                      f"roles{C.RESET}")
                return

            # Save to cache
            deep_dir.mkdir(parents=True, exist_ok=True)
            for role in ("primary", "adversarial", "synthesis"):
                text = by_role[role].get("prompt", "")
                name = by_role[role].get("name", role)
                (deep_dir / f"{role}.md").write_text(
                    text, encoding="utf-8")
                preview = text[:60] + ("..." if len(text) > 60 else "")
                print(f"  {C.GREEN}{role}{C.RESET} ({name}): "
                      f"{C.DIM}{preview}{C.RESET}")

            primary_prompt = by_role["primary"]["prompt"]
            adv_prompt = by_role["adversarial"]["prompt"]
            synth_prompt = by_role["synthesis"]["prompt"]

        # Run 3-call pipeline
        content_label = "INPUT" if general else "SOURCE CODE"

        # Call 1: Primary
        print(f"\n{C.BOLD}{C.BLUE}── Primary: {goal} ── "
              f"{file_name} ──{C.RESET}")
        primary_backend = ClaudeBackend(
            model=self.session.model,
            working_dir=str(self.working_dir),
            system_prompt=primary_prompt,
            tools=False,
        )
        primary_output = self._stream_and_capture(
            primary_backend, f"Analyze this deeply.\n\n{content}")

        if primary_output and not self._interrupted:
            self._save_deep_finding(
                file_name, f"deep_{slug}_primary", primary_output)

        if not primary_output or self._interrupted:
            return

        # Call 2: Adversarial
        adv_input = (
            f"# {content_label}\n\n{content}\n\n---\n\n"
            f"# STRUCTURAL ANALYSIS (from previous pass)\n\n"
            f"{primary_output}"
        )
        print(f"\n{C.BOLD}{C.BLUE}── Adversarial: {goal} ──{C.RESET}")
        adv_backend = ClaudeBackend(
            model=self.session.model,
            working_dir=str(self.working_dir),
            system_prompt=adv_prompt,
            tools=False,
        )
        adv_output = self._stream_and_capture(adv_backend, adv_input)

        if adv_output and not self._interrupted:
            self._save_deep_finding(
                file_name, f"deep_{slug}_adversarial", adv_output)

        if not adv_output or self._interrupted:
            return

        # Call 3: Synthesis
        synth_input = (
            f"# {content_label}\n\n{content}\n\n---\n\n"
            f"# ANALYSIS 1: PRIMARY\n\n{primary_output}\n\n---\n\n"
            f"# ANALYSIS 2: ADVERSARIAL\n\n{adv_output}"
        )
        print(f"\n{C.BOLD}{C.BLUE}── Synthesis: {goal} ──{C.RESET}")
        synth_backend = ClaudeBackend(
            model=self.session.model,
            working_dir=str(self.working_dir),
            system_prompt=synth_prompt,
            tools=False,
        )
        synth_output = self._stream_and_capture(
            synth_backend, synth_input)

        if synth_output and not self._interrupted:
            self._save_deep_finding(
                file_name, f"deep_{slug}_synthesis", synth_output)

        # Save combined
        combined = (
            f"# Deep Analysis: {goal} — {file_name}\n\n"
            f"## PRIMARY\n\n{primary_output}\n\n"
            f"## ADVERSARIAL\n\n{adv_output}\n\n"
            f"## SYNTHESIS\n\n{synth_output or '(not completed)'}\n\n"
        )
        self._save_deep_finding(file_name, f"deep_{slug}", combined)
        print(f"\n  {C.DIM}Use /fix to pick issues, or "
              f"/fix auto to fix all{C.RESET}")

    def _run_expand(self, content, file_name, indices_str=None,
                    expand_mode=None, general=False):
        """Expand mode: pick areas from discover, choose single/full per area.

        1. Load discover results (auto-discover if needed)
        2. Show list, prompt for area selection
        3. For each selected area: prompt single/full prism (or use expand_mode)
        4. Single: run existing discover lens (1 call)
        5. Full: cook a full prism pipeline for the area + run (N calls)

        expand_mode="single"|"full" applies to all selected areas.
        expand_mode=None prompts per area (allows mixing).
        """
        # 1. Get discover results
        results = self._load_discover_results(file_name)
        if not results:
            self._run_discover(content, file_name, general)
            results = self._load_discover_results(file_name)
            if not results:
                return

        # 2. Select areas
        if indices_str:
            indices = self._parse_selection(indices_str, len(results))
        else:
            print(f"\n{C.BOLD}Available areas:{C.RESET}\n")
            for i, item in enumerate(results, 1):
                print(f"  {C.CYAN}{i}.{C.RESET} "
                      f"{C.GREEN}{item['name']}{C.RESET}")
                print(f"     {C.DIM}{item['preview']}{C.RESET}")
            try:
                sel = input(
                    f"\n  Select areas (e.g. 1,3,5 or "
                    f"* for all): ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not sel:
                return
            indices = self._parse_selection(sel, len(results))

        if not indices:
            print(f"{C.YELLOW}No valid areas selected{C.RESET}")
            return

        # 3. Per-area mode choice
        area_configs = []
        if expand_mode:
            # Global mode: all areas get the same prism
            for idx in indices:
                area_configs.append(
                    (idx, results[idx - 1], expand_mode))
        else:
            # Interactive: user picks per area (can mix)
            for idx in indices:
                item = results[idx - 1]
                try:
                    choice = input(
                        f"  {C.GREEN}{item['name']}{C.RESET}"
                        f" — [s]ingle / [f]ull prism: "
                    ).strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print()
                    return
                mode = "full" if choice.startswith("f") else "single"
                area_configs.append((idx, item, mode))

        # Summary
        s_count = sum(1 for _, _, m in area_configs if m == "single")
        f_count = sum(1 for _, _, m in area_configs if m == "full")
        print(f"\n  {C.DIM}{len(area_configs)} areas: "
              f"{s_count} single + {f_count} full{C.RESET}\n")

        # 4. Cook and run each area
        for idx, item, mode in area_configs:
            area_name = item["name"]

            if mode == "single":
                lens_path = item.get("lens_path", "")
                print(f"{C.CYAN}Single Prism: {area_name}{C.RESET}")
                self._run_single_lens_streaming(
                    lens_path, content, file_name,
                    label=f"{area_name} ── {file_name}")
            else:
                print(f"{C.CYAN}Full Prism: {area_name}{C.RESET}")
                self._run_expand_full(
                    content, file_name, area_name, general)

            if self._interrupted:
                break

        print(f"\n  {C.DIM}Use /fix to pick issues, or "
              f"/fix auto to fix all{C.RESET}")

    def _run_expand_full(self, content, file_name, area_name,
                         general=False):
        """Cook and run a full prism pipeline for a specific area."""
        slug = re.sub(r'[^a-z0-9]+', '_',
                      area_name.lower()).strip('_')[:40]
        cache_dir = (self.working_dir / ".deep" / "lenses"
                     / "_expand" / slug)

        # Check cache
        cached = self._load_cached_pipeline(cache_dir)
        if cached:
            print(f"  {C.DIM}Using cached pipeline: "
                  f"{slug}{C.RESET}")
            lenses = cached
        else:
            # Cook
            sample = content[:2000] if len(content) > 2000 else content
            prompt = COOK_FULL_PRISM_PROMPT.format(area=area_name)
            user_input = (
                f"Generate an analytical pipeline for: "
                f"{area_name}\n\n"
                f"Sample artifact:\n\n{sample}")

            print(f"  {C.CYAN}Cooking pipeline for: "
                  f"{area_name}{C.RESET}")
            raw = self._call_model(prompt, user_input, timeout=90)

            parsed = self._parse_stage_json(raw, "cook_expand")
            if not isinstance(parsed, list) or len(parsed) < 2:
                print(f"{C.RED}Failed to cook pipeline for "
                      f"{area_name}{C.RESET}")
                return

            # Save to cache
            cache_dir.mkdir(parents=True, exist_ok=True)
            lenses = []
            for i, item in enumerate(parsed):
                name = item.get("name", f"step_{i + 1}")
                name = re.sub(r'[^a-z0-9_]', '_', name.lower())
                text = item.get("prompt", "")
                role = item.get("role", f"step_{i + 1}")
                if not text:
                    continue
                (cache_dir / f"{i:02d}_{name}.md").write_text(
                    text, encoding="utf-8")
                lenses.append({"name": name, "prompt": text,
                               "role": role, "order": i})
                preview = text[:60] + (
                    "..." if len(text) > 60 else "")
                print(f"    {C.GREEN}{role}{C.RESET} ({name}): "
                      f"{C.DIM}{preview}{C.RESET}")

            if len(lenses) < 2:
                print(f"{C.RED}Need at least 2 lenses for "
                      f"full prism{C.RESET}")
                return

        self._run_cooked_pipeline(
            lenses, content, file_name, area_name, general)

    def _run_cooked_pipeline(self, lenses, content, file_name,
                             area_name, general=False):
        """Run an ordered list of lenses as a pipeline.

        First lens gets raw content. Each subsequent lens receives
        the raw content plus all previous analyses.
        """
        content_label = "INPUT" if general else "SOURCE CODE"
        slug = re.sub(r'[^a-z0-9]+', '_',
                      area_name.lower()).strip('_')[:40]
        outputs = []

        for i, lens in enumerate(lenses):
            role = lens.get("role", lens["name"])

            # Build message
            if i == 0:
                msg = f"Analyze this deeply.\n\n{content}"
            else:
                parts = [f"# {content_label}\n\n{content}"]
                for j, prev in enumerate(outputs):
                    prev_role = lenses[j].get(
                        "role", lenses[j]["name"]).upper()
                    parts.append(
                        f"# ANALYSIS {j + 1}: {prev_role}"
                        f"\n\n{prev}")
                msg = "\n\n---\n\n".join(parts)

            print(f"\n{C.BOLD}{C.BLUE}── {role}: "
                  f"{area_name} ── {file_name} ──{C.RESET}")
            backend = ClaudeBackend(
                model=self.session.model,
                working_dir=str(self.working_dir),
                system_prompt=lens["prompt"],
                tools=False,
            )
            output = self._stream_and_capture(backend, msg)

            if output and not self._interrupted:
                self._save_deep_finding(
                    file_name,
                    f"expand_{slug}_{role}", output)
                outputs.append(output)

            if not output or self._interrupted:
                break

        # Save combined
        if outputs:
            combined_parts = [
                f"# Expand Full Prism: {area_name} "
                f"— {file_name}\n"]
            for lens, out in zip(lenses, outputs):
                r = lens.get("role", lens["name"]).upper()
                combined_parts.append(
                    f"## {r}\n\n{out}\n")
            self._save_deep_finding(
                file_name, f"expand_{slug}",
                "\n".join(combined_parts))

    def _stream_and_capture(self, backend, message):
        """Stream output from a ClaudeBackend, capture and return text.

        Shared by _run_deep pipeline calls. Returns captured text or "".
        """
        parser = StreamParser()
        self._interrupted = False
        had_output = False
        output_buffer = []

        original_sigint = signal.getsignal(signal.SIGINT)
        def on_interrupt(sig, frame):
            self._interrupted = True
            backend.kill()
        signal.signal(signal.SIGINT, on_interrupt)

        thinking_shown = False
        try:
            for line in backend.send(message):
                if self._interrupted:
                    break
                for evt, data in parser.parse_line(line):
                    if evt == "text":
                        if thinking_shown:
                            sys.stdout.write(
                                "\r" + " " * 30 + "\r")
                            thinking_shown = False
                        sys.stdout.write(data)
                        sys.stdout.flush()
                        output_buffer.append(data)
                        had_output = True
                    elif evt == "thinking":
                        if not thinking_shown:
                            sys.stdout.write(
                                f"{C.DIM}thinking...{C.RESET}")
                            sys.stdout.flush()
                            thinking_shown = True
                    elif evt == "result":
                        usage = data.get("usage", {})
                        self.session.total_input_tokens += usage.get(
                            "input_tokens", 0)
                        self.session.total_output_tokens += usage.get(
                            "output_tokens", 0)
                        cost = data.get("total_cost_usd",
                                        data.get("cost_usd", 0))
                        if isinstance(cost, (int, float)):
                            self.session.total_cost_usd += cost
        finally:
            signal.signal(signal.SIGINT, original_sigint)
            if self._interrupted:
                print(f"\n{C.YELLOW}interrupted{C.RESET}")
            elif had_output:
                print()
            print()

        return "".join(output_buffer)

    def _run_target(self, content, file_name, goal, general=False):
        """Target mode: cook a goal-specific lens + run it.

        Generates ONE focused lens for the user's specific goal,
        saves it for reuse, then runs it on the input.
        """
        # Slugify goal for filesystem
        slug = re.sub(r'[^a-z0-9]+', '_', goal.lower()).strip('_')[:40]

        # Check cache
        cached_lens = f"_targets/{slug}"
        if self._load_lens(cached_lens):
            print(f"{C.DIM}Using cached lens: {slug}{C.RESET}")
        else:
            # Cook one focused lens
            prompt = COOK_TARGET_PROMPT.format(goal=goal)
            sample = content[:2000] if len(content) > 2000 else content
            user_input = (
                f"Generate one analytical lens for this goal: {goal}\n\n"
                f"Sample artifact:\n\n{sample}")

            print(f"{C.CYAN}Cooking lens for: {goal}{C.RESET}")
            raw = self._call_model(prompt, user_input, timeout=90)

            parsed = self._parse_stage_json(raw, "cook_target")
            if not isinstance(parsed, dict) or "prompt" not in parsed:
                print(f"{C.RED}Failed to generate target lens{C.RESET}")
                return

            name = parsed.get("name", slug)
            name = re.sub(r'[^a-z0-9_]', '_', name.lower())
            text = parsed["prompt"]

            # Save to project-local .deep/lenses/_targets/
            target_dir = self.working_dir / ".deep" / "lenses" / "_targets"
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / f"{slug}.md").write_text(text, encoding="utf-8")

            preview = text[:70] + ("..." if len(text) > 70 else "")
            print(f"  {C.GREEN}{slug}{C.RESET}: {C.DIM}{preview}{C.RESET}")
            cached_lens = f"_targets/{slug}"

        # Run the lens
        self._run_single_lens_streaming(
            cached_lens, content, file_name,
            label=f"{slug} ── {file_name}")

    def _infer_domain(self, content, file_name, general=False):
        """Infer a domain label from content for expand mode lens caching."""
        if not general:
            # Code file — use extension
            ext = pathlib.Path(file_name).suffix.lstrip(".")
            return f"code_{ext}" if ext else "code"
        # For text, derive from first ~50 chars
        slug = re.sub(r'[^a-z0-9]+', '_', content[:50].lower()).strip('_')
        return slug[:30] if slug else "general"

    def _run_single_lens_streaming(self, lens_name, content, file_name,
                                    label=None, message=None):
        """Run a single lens with streaming output. Saves to .deep/findings/.

        Returns captured output text, or "" if interrupted/failed.
        """
        prompt = self._load_lens(lens_name)
        if not prompt:
            print(f"{C.RED}Lens '{lens_name}' not found{C.RESET}")
            return ""

        header = label or f"{lens_name} ── {file_name}"
        print(f"{C.BOLD}{C.BLUE}── {header} ──{C.RESET}")

        backend = ClaudeBackend(
            model=self.session.model,
            working_dir=str(self.working_dir),
            system_prompt=prompt,
            tools=False,
        )
        msg = message or f"Analyze this deeply.\n\n{content}"
        captured = self._stream_and_capture(backend, msg)

        if captured.strip() and not self._interrupted:
            self._save_deep_finding(file_name, lens_name, captured)
        return captured

    # ── Auto-modes ───────────────────────────────────────────────────────

    def _collect_files(self, target, extensions=None):
        """Collect target files from a path (file or directory)."""
        exts = extensions or {".py", ".js", ".ts", ".go", ".rs", ".java",
                              ".rb", ".sh", ".md", ".yaml", ".yml", ".toml"}
        path = self._resolve_file(target)
        if not path:
            return []
        if path.is_file():
            return [path]
        if path.is_dir():
            files = []
            for ext in exts:
                files.extend(path.glob(f"**/*{ext}"))
            # Filter out hidden dirs, node_modules, etc.
            files = [f for f in files
                     if not any(p.startswith(".") or p == "node_modules"
                                for p in f.relative_to(path).parts)]
            # Sort by size (largest first — more interesting)
            files.sort(key=lambda f: f.stat().st_size, reverse=True)
            return files[:20]  # Cap at 20 files
        return []

    def _call_model(self, system_prompt, user_input, timeout=120):
        """Model call using session model."""
        return self._claude.call(system_prompt, user_input,
                                 model=self.session.model, timeout=timeout)

    @staticmethod
    def _cleanup_old_findings(findings_dir, max_age_days=FINDINGS_MAX_AGE_DAYS):
        """Delete *.md files in findings_dir whose mtime is older than max_age_days."""
        if not findings_dir.exists():
            return
        cutoff = time.time() - max_age_days * 86400
        for p in findings_dir.glob("*.md"):
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
            except OSError:
                pass


    # ── Parse helpers ─────────────────────────────────────────────────

    def _log_parse_failure(self, context, raw, error):
        """Append a parse-failure record to .deep/parse_errors.log.

        Falls back to stderr when .deep/ does not yet exist.
        Each record contains: ISO timestamp, context label, error message,
        and a 200-char snippet of the raw model output for debugging.
        """
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        snippet = (raw or "")[:200].replace("\n", "\\n")
        record = (
            f"[{timestamp}] context={context} error={error!r} "
            f"raw_snippet={snippet!r}\n"
        )
        deep_dir = self.working_dir / ".deep"
        if deep_dir.exists():
            log_path = deep_dir / "parse_errors.log"
            try:
                with log_path.open("a", encoding="utf-8") as fh:
                    fh.write(record)
                return
            except OSError:
                pass
        # Fallback: write to stderr so the failure is never silently swallowed
        print(f"{C.DIM}[parse] {record.rstrip()}{C.RESET}", file=sys.stderr)

    @staticmethod
    def _normalize_issue(issue):
        """Map variant field names to canonical schema before validation.

        Handles common Haiku freestyle output: severity→priority,
        fix/suggested_action→action, location→file, what_breaks→description.
        """
        if not isinstance(issue, dict):
            return issue

        # Field name aliases → canonical name (order matters: prefer
        # more specific sources, check each only if target still absent)
        alias_groups = {
            "action": ["fix", "suggested_fix", "suggested_action",
                       "root_cause", "fixable"],
            "description": ["what_breaks"],
            "file": ["location"],
            "title": ["name"],
        }
        for dst, srcs in alias_groups.items():
            if dst not in issue or not issue[dst]:
                for src in srcs:
                    if src in issue and issue[src]:
                        issue[dst] = issue[src]
                        break

        # severity → priority mapping
        if "priority" not in issue and "severity" in issue:
            sev = str(issue["severity"]).upper().strip()
            sev_map = {
                "CRITICAL": "P0",
                "HIGH": "P1",
                "IMPORTANT": "P1",
                "MEDIUM": "P2",
                "LOW-MEDIUM": "P2",
                "LOW": "P3",
                "MINOR": "P3",
            }
            issue["priority"] = sev_map.get(sev, "P2")

        # id: accept string IDs like "STRUCT-001" → hash to int
        raw_id = issue.get("id")
        if isinstance(raw_id, str) and not raw_id.isdigit():
            issue["id"] = abs(hash(raw_id)) % 10000

        # location often contains function names, not filenames —
        # preserve as separate 'location' field for fix targeting
        loc = issue.get("file", "")
        if isinstance(loc, str) and loc and "." not in loc:
            # Looks like a function/method reference, not a file
            issue.setdefault("location", loc)
            issue["file"] = "unknown"
        # Also preserve original location if it came from that field
        if "location" in issue and issue.get("file") != "unknown":
            issue.setdefault("location", issue.get("location", ""))

        return issue

    @staticmethod
    def _validate_issue(issue):
        """Validate and normalise a single issue dict.

        Required fields: id (int), priority (P0-P3), title, description, action.
        Optional fields: file, lens — default to "unknown" when absent.

        Returns a cleaned copy on success, or None when a required field is
        missing/invalid so the caller can skip the issue and log the failure.
        """
        if not isinstance(issue, dict):
            return None

        # Normalize variant fields first
        issue = PrismREPL._normalize_issue(issue)

        # Normalise optional fields before checking required ones
        issue.setdefault("file", "unknown")
        issue.setdefault("lens", "unknown")
        if not issue["file"]:
            issue["file"] = "unknown"
        if not issue["lens"]:
            issue["lens"] = "unknown"

        # id must be an integer (accept strings that parse cleanly)
        raw_id = issue.get("id")
        if raw_id is None:
            return None
        try:
            issue["id"] = int(raw_id)
        except (TypeError, ValueError):
            return None

        # priority must be one of the four canonical values
        priority = issue.get("priority", "")
        if priority not in ("P0", "P1", "P2", "P3"):
            return None

        # Text fields must be non-empty strings
        for field in ("title", "description", "action"):
            val = issue.get(field)
            if not isinstance(val, str) or not val.strip():
                return None
            issue[field] = val.strip()

        return issue

    # ── Heal command ──────────────────────────────────────────────────

    def _load_extract_prompt(self):
        """Load issue extraction prompt from disk or return fallback."""
        for d in [self.working_dir / ".deep" / "skills", GLOBAL_SKILLS_DIR]:
            p = d / "issue_extract.md"
            if p.exists():
                return p.read_text(encoding="utf-8")
        return self._load_intent("issue_extract_fallback", ISSUE_EXTRACT_FALLBACK)

    @staticmethod
    def _unwrap_issues_list(data):
        """Extract a flat list of issue dicts from parsed JSON.

        Handles: bare list, dict with a list-valued key (e.g.
        {"concrete_bugs": [...]}), or nested structure with multiple
        list-valued keys (merges all).
        """
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Collect all list-of-dict values (e.g. concrete_bugs,
            # structural_issues) — skip metadata dicts/scalars
            merged = []
            for v in data.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    merged.extend(v)
            return merged or None
        return None

    @staticmethod
    def _parse_issues_raw(raw):
        """Strip code fences then parse a JSON issues array.

        Returns ``(issues_list, None)`` on success or ``(None, error_str)``
        on failure so callers can decide whether to retry rather than
        silently swallowing malformed output.
        """
        cleaned = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
        cleaned = re.sub(r'^```\s*$', '', cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()
        try:
            parsed = json.loads(cleaned)
            issues = PrismREPL._unwrap_issues_list(parsed)
            if issues is not None:
                return issues, None
            return None, "parsed JSON but found no issue lists"
        except json.JSONDecodeError as exc:
            # Regex fallback: grab the first [...] block and try again
            m = re.search(r'\[.*\]', cleaned, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group()), None
                except json.JSONDecodeError as exc2:
                    return None, str(exc2)
            return None, str(exc)

    def _reextract_with_error(self, report_text, error_msg):
        """Ask haiku to re-extract issues, forwarding the previous error.

        Returns the raw model response string, or ``None`` when the call
        itself fails so the caller can fall back gracefully.
        """
        retry_prompt = (
            self._load_intent("issue_extract_fallback", ISSUE_EXTRACT_FALLBACK)
            + f"\n\nPrevious attempt failed: {error_msg}\n"
            "Output a complete, valid JSON array only. "
            "Every issue MUST have: non-null integer id, "
            "P0/P1/P2/P3 priority, non-empty title, description, action."
        )
        raw = self._call_model(retry_prompt, report_text)
        if not raw or raw.startswith("[Error"):
            self._log_parse_failure(
                "extract_issues:retry_call", raw, "empty or error on retry")
            return None
        return raw

    @staticmethod
    def _parse_bug_table(report_text):
        """Parse bug table directly from L12 output. Zero API calls.

        L12 outputs a markdown table like:
        | # | Location | What Breaks | Severity | Fixable? | Prediction |
        Returns list of issue dicts for fixable bugs, or None (no table found).
        """
        lines = report_text.split("\n")
        table_rows = []
        in_table = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("| #") or stripped.startswith("| **#"):
                in_table = True
                continue
            if in_table and stripped.startswith("|---"):
                continue
            if in_table and stripped.startswith("|"):
                table_rows.append(stripped)
            elif in_table and not stripped.startswith("|"):
                in_table = False

        if not table_rows:
            return None

        sev_map = {"CRITICAL": "P0", "HIGH": "P1", "MEDIUM": "P2",
                   "LOW": "P3", "VERY LOW": "P3", "NONE": "P3"}

        def _clean(s):
            return re.sub(r'\*\*([^*]*)\*\*', r'\1', s).replace('`', '').strip()

        issues = []
        for row in table_rows:
            cells = [c.strip() for c in row.split("|")[1:-1]]
            if len(cells) < 5:
                continue

            num = _clean(cells[0])
            location = _clean(cells[1])
            what_breaks = _clean(cells[2])
            severity = _clean(cells[3]).upper()
            fixable = _clean(cells[4]) if len(cells) > 4 else ""

            fixable_lower = fixable.lower()
            pre_paren = fixable_lower.split("(")[0]
            if ("no" in pre_paren or "structural" in fixable_lower
                    or "not fixable" in fixable_lower
                    or "by design" in fixable_lower
                    or "unfixable" in fixable_lower):
                print(f"      TABLE SKIP #{num}: structural ({fixable[:40]})")
                continue
            if "none" in fixable_lower or fixable_lower.startswith("n/a"):
                print(f"      TABLE SKIP #{num}: n/a")
                continue

            hint_match = re.search(r'\(([^)]+)\)', fixable)
            action = hint_match.group(1) if hint_match else fixable

            priority = "P2"
            for sev_key, prio in sev_map.items():
                if sev_key in severity:
                    priority = prio
                    break

            issues.append({
                "id": len(issues) + 1,
                "priority": priority,
                "title": f"#{num}: {what_breaks[:60]}",
                "file": "unknown",
                "location": location,
                "description": what_breaks,
                "action": action,
            })

        if issues:
            print(f"      Parsed bug table: {len(table_rows)} rows, "
                  f"{len(issues)} fixable")
        return issues if issues else None

    def _extract_issues(self, report_text):
        """Parse report text into structured issue list.

        First tries to parse the L12 bug table directly (zero API calls).
        Falls back to model-based extraction if no table found.

        Parse failures are logged to .deep/parse_errors.log and each issue
        is validated against the required schema before being included in
        the result.

        On JSON parse failure or schema violations (e.g. null id), re-extracts
        once with an explicit error message so the model can self-correct.
        If invalid items remain after retry the user is notified visibly so
        /fix is never silently run against an incomplete list.
        """
        # Try bug table first (zero API calls)
        table_issues = self._parse_bug_table(report_text)
        if table_issues:
            print(f"      Extracted {len(table_issues)} issues from bug table "
                  f"(no API call)")
            # Validate each issue through existing pipeline
            validated = []
            for issue in table_issues:
                cleaned = self._validate_issue(issue)
                if cleaned is not None:
                    cleaned.setdefault("status", "open")
                    validated.append(cleaned)
            if validated:
                return validated

        # Fall back to model-based extraction
        extract_prompt = self._load_extract_prompt()
        raw = self._call_model(extract_prompt, report_text)
        if not raw or raw.startswith("[Error"):
            self._log_parse_failure("extract_issues:call", raw, "empty or error response")
            return []

        # Attempt #1: parse JSON
        issues, parse_err = self._parse_issues_raw(raw)
        if parse_err is not None:
            self._log_parse_failure("extract_issues:primary_parse", raw, parse_err)
            raw = self._reextract_with_error(
                report_text, f"Malformed JSON — {parse_err}")
            if raw is None:
                return []
            issues, parse_err = self._parse_issues_raw(raw)
            if parse_err is not None:
                self._log_parse_failure("extract_issues:retry_parse", raw, parse_err)
                print(
                    f"  {C.YELLOW}Warning: issue extraction failed "
                    f"(JSON still invalid after retry). "
                    f"See .deep/parse_errors.log{C.RESET}"
                )
                return []

        if not isinstance(issues, list):
            self._log_parse_failure(
                "extract_issues:not_a_list", raw, f"got {type(issues).__name__}")
            return []

        # Validate every issue; collect failures for potential retry
        validated, invalid = [], []
        for idx, issue in enumerate(issues):
            cleaned = self._validate_issue(issue)
            if cleaned is None:
                self._log_parse_failure(
                    f"extract_issues:invalid_item[{idx}]",
                    json.dumps(issue, ensure_ascii=False)[:200],
                    "missing or invalid required field")
                invalid.append(issue)
            else:
                cleaned.setdefault("status", "open")
                validated.append(cleaned)

        # Retry once when schema violations are found (e.g. null IDs)
        if invalid:
            error_msg = (
                f"{len(invalid)} of {len(issues)} issue(s) had missing or null "
                "required fields (id, priority, title, description, or action)"
            )
            self._log_parse_failure("extract_issues:schema_fail", raw, error_msg)
            raw2 = self._reextract_with_error(report_text, error_msg)
            if raw2:
                issues2, parse_err2 = self._parse_issues_raw(raw2)
                if parse_err2 is None and isinstance(issues2, list):
                    validated2, invalid2 = [], []
                    for idx, issue in enumerate(issues2):
                        cleaned = self._validate_issue(issue)
                        if cleaned is None:
                            self._log_parse_failure(
                                f"extract_issues:retry_invalid[{idx}]",
                                json.dumps(issue, ensure_ascii=False)[:200],
                                "missing or invalid required field")
                            invalid2.append(issue)
                        else:
                            cleaned.setdefault("status", "open")
                            validated2.append(cleaned)
                    # Accept retry results when they are at least as good
                    if len(invalid2) < len(invalid):
                        validated, invalid = validated2, invalid2

            if invalid:
                print(
                    f"  {C.YELLOW}Warning: {len(invalid)} issue(s) skipped — "
                    f"missing required fields (id/title/priority). "
                    f"See .deep/parse_errors.log{C.RESET}"
                )

        return validated

    def _heal_pick_issues(self, issues):
        """Display issues grouped by priority, return selected list."""
        priority_colors = {
            "P0": C.RED, "P1": C.YELLOW, "P2": C.CYAN, "P3": C.DIM
        }
        priority_labels = {
            "P0": "Critical", "P1": "Important",
            "P2": "Improvement", "P3": "Monitor"
        }

        # Group by priority
        groups = {}
        for issue in issues:
            p = issue.get("priority", "P2")
            groups.setdefault(p, []).append(issue)

        # Display
        open_ids = []
        for p in ["P0", "P1", "P2", "P3"]:
            if p not in groups:
                continue
            color = priority_colors.get(p, "")
            label = priority_labels.get(p, p)
            print(f"\n  {color}{C.BOLD}{p} {label}{C.RESET}")
            for issue in groups[p]:
                iid = issue.get("id", "?")
                title = issue.get("title", "untitled")
                fname = issue.get("file", "")
                lens = issue.get("lens", "")
                status = issue.get("status", "open")
                if status == "fixed":
                    print(f"    {C.DIM}{iid:>2}  [{lens:<15}] {fname:<12} "
                          f"[FIXED] {title}{C.RESET}")
                else:
                    print(f"    {color}{iid:>2}{C.RESET}  "
                          f"{C.DIM}[{lens:<15}]{C.RESET} "
                          f"{fname:<12} {title}")
                    open_ids.append(iid)
        print()

        if not open_ids:
            print(f"  {C.GREEN}All issues fixed!{C.RESET}")
            return []

        # Parse selection
        for _ in range(3):
            try:
                sel = input(
                    f"  {C.GREEN}Select: number, range (1-3), "
                    f"comma (1,3), all, q{C.RESET}\n  > "
                ).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                return []

            if sel == "q":
                return []

            if sel == "all":
                return [i for i in issues if i.get("status") != "fixed"]

            # Parse numbers
            selected_ids = set()
            try:
                for part in sel.split(","):
                    part = part.strip()
                    if "-" in part:
                        lo, hi = part.split("-", 1)
                        for n in range(int(lo), int(hi) + 1):
                            selected_ids.add(n)
                    else:
                        selected_ids.add(int(part))
            except ValueError:
                print(f"  {C.YELLOW}Invalid selection. Try again.{C.RESET}")
                continue

            result = [i for i in issues
                      if i.get("id") in selected_ids
                      and i.get("status") != "fixed"]
            if result:
                return result
            print(f"  {C.YELLOW}No open issues matched. Try again.{C.RESET}")

        return []

    @staticmethod
    def _extract_structural_context(findings_text):
        """Extract conservation law + meta-law from L12 output.

        Returns a compact string for injection into fix prompts.
        Graceful: returns "" if nothing found.
        """
        if not findings_text:
            return ""

        parts = []

        # Conservation law: ## Conservation Law, ## 12. CONSERVATION LAW, etc.
        cl_match = re.search(
            r'^##\s+(?:\d+\.\s*)?(?:The\s+)?Conservation\s+Law[^\n]*\n(.*?)(?=\n##\s|\Z)',
            findings_text, re.MULTILINE | re.DOTALL | re.IGNORECASE)
        if cl_match:
            body = cl_match.group(1).strip()
            if len(body) > 300:
                body = body[:300].rsplit(" ", 1)[0] + "..."
            parts.append(f"Conservation law: {body}")

        # Meta-law: ## Meta-Law, ## 15. META-CONSERVATION LAW, ## 16. Meta-Law, etc.
        ml_match = re.search(
            r'^##\s+(?:\d+\.\s*)?(?:The\s+)?Meta[-\s](?:Conservation\s+)?Law[^\n]*\n(.*?)(?=\n##\s|\Z)',
            findings_text, re.MULTILINE | re.DOTALL | re.IGNORECASE)
        if ml_match:
            body = ml_match.group(1).strip()
            if len(body) > 200:
                body = body[:200].rsplit(" ", 1)[0] + "..."
            parts.append(f"Meta-law: {body}")

        return "\n\n".join(parts)

    @staticmethod
    def _diff_issues(old_issues, new_issues):
        """Return issues from new_issues not present in old_issues.

        Compares by (location, description[:50]) signature.
        """
        def _sig(issue):
            loc = issue.get("location", issue.get("file", ""))
            desc = issue.get("description", "")[:50].lower().strip()
            return (loc, desc)

        old_sigs = {_sig(i) for i in old_issues}
        return [i for i in new_issues if _sig(i) not in old_sigs]

    def _heal_fix_one(self, issue, structural_context=""):
        """Apply a fix for one issue. Returns 'approved'/'rejected'/'instructed'."""
        fname = issue.get("file", "unknown")
        title = issue.get("title", "")
        desc = issue.get("description", "")
        action = issue.get("action", "")
        location = issue.get("location", "")

        # Extract location from description/action if not provided
        if not location:
            desc_funcs = re.findall(r'(_\w{5,})\(\)', f"{desc} {action}")
            if desc_funcs:
                location = desc_funcs[0]

        # Resolve target file
        target = self._resolve_file(fname) if fname != "unknown" else None
        snapshots = {}

        if target and target.exists():
            snapshots[str(target)] = target.read_text(
                encoding="utf-8", errors="replace")

        # Pre-grep: extract relevant code snippet around the location
        snippet = ""
        if target and target.exists() and (location or desc or action):
            snippet = self._heal_grep_context(
                target, location, desc=desc, action=action)

        # Build specific fix message
        fix_msg = (
            f"Fix this specific issue in {fname}:\n\n"
            f"Title: {title}\n"
            f"Description: {desc}\n"
        )
        if location:
            fix_msg += f"Location: {location}\n"
        if action:
            fix_msg += f"Suggested action: {action}\n"
        if snippet:
            fix_msg += (
                f"\nRelevant code (with line numbers):\n"
                f"```\n{snippet}\n```\n"
            )
        if structural_context:
            fix_msg += (
                f"\n## Structural context (from L12 analysis)\n"
                f"{structural_context}\n\n"
                f"This issue is fixable. Do not fight structural "
                f"constraints — work within them.\n"
            )
        fix_msg += (
            "\nLocate the exact method and line before editing. "
            "Make exactly one change: replace a variable or statement, "
            "insert a new block, or add a guard clause. "
            "If this fix requires changes in 3+ locations, fix only the "
            "most critical one. Don't refactor unrelated code."
        )
        if target:
            fix_msg += f"\n\nFile path: {target}"

        self._send_and_stream(fix_msg)

        result = self._heal_review_diff(snapshots, issue)
        return result, snapshots

    @staticmethod
    def _heal_grep_context(target, location, context_lines=65,
                           desc="", action=""):
        """Extract code around a function/method name for fix targeting.

        Searches for method definitions first (``def _method``), then
        falls back to identifier matching.  Returns numbered lines
        around the first match, or "" if not found.

        Accepts desc/action strings to mine additional search terms
        beyond the location field (functions, constants, identifiers).
        """
        try:
            lines = target.read_text(
                encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return ""

        combined = f"{location} {desc} {action}"

        # Location-specific: match both public and private methods
        search_terms = []
        if location:
            loc_funcs = re.findall(r'(\w{4,})\(\)', location)
            for f in loc_funcs:
                search_terms.append(f"def {f}")
            if not loc_funcs:
                search_terms.append(f"def {location}")
                search_terms.append(location)

        # Extract function/method names from all fields
        funcs = re.findall(r'(_\w{5,})\(\)', combined)
        if not funcs:
            funcs = re.findall(r'(_\w{5,})', location)

        # Definitions first
        for f in funcs[:3]:
            search_terms.append(f"def {f}")

        # ALL_CAPS constants (e.g. ALLOWED_TOOLS)
        caps = re.findall(r'[A-Z][A-Z_]{3,}', combined)
        search_terms.extend(caps[:3])

        # Quoted identifiers from action
        quoted = re.findall(r"'([_a-zA-Z]\w{4,})'", action)
        search_terms.extend(quoted[:2])

        # Snake_case identifiers (long ones only)
        for text in [action, desc]:
            snakes = re.findall(r'[a-z]\w*_\w{3,}', text)
            search_terms.extend(s for s in snakes
                                if len(s) > 7 and s not in search_terms)

        # Session-specific routing
        combined_lower = combined.lower()
        if "session" in combined_lower and any(
                kw in combined_lower
                for kw in ("persist", "migration", "model_name",
                           "schema version")):
            search_terms.insert(0, "def load(")
            search_terms.insert(1, "def save(")

        # Fallback: bare identifiers
        if not search_terms:
            search_terms = [t for t in re.findall(r'\w+', location)
                           if len(t) > 4 and not t[0].isupper()]
        # Final fallback: function names without "def "
        for f in funcs:
            if f not in search_terms:
                search_terms.append(f)

        if not search_terms:
            return ""

        # Dedupe preserving order
        seen = set()
        unique = [t for t in search_terms
                  if t not in seen and not seen.add(t)]

        for term in unique[:8]:
            for i, line in enumerate(lines):
                if term in line:
                    start = max(0, i - 5)
                    end = min(len(lines), i + context_lines)
                    numbered = [f"{n+1:>4}  {lines[n]}"
                               for n in range(start, end)]
                    return "\n".join(numbered)

        # Whole-file fallback for small files
        if len(lines) <= 500:
            return "\n".join(f"{n+1:>4}  {lines[n]}"
                             for n in range(len(lines)))
        return ""

    def _heal_review_diff(self, snapshots, issue):
        """Show diff of changes and get user approval."""
        has_changes = False

        for filepath, original in snapshots.items():
            path = pathlib.Path(filepath)
            if not path.exists():
                continue
            current = path.read_text(encoding="utf-8", errors="replace")
            if current != original:
                has_changes = True
                print(f"\n  {C.BOLD}Changes in {path.name}:{C.RESET}")
                self._show_inline_diff(original, current, path.name)

        # Fallback: check git diff if no snapshot changes detected
        if not has_changes:
            try:
                result = subprocess.run(
                    ["git", "diff"], capture_output=True, text=True,
                    encoding="utf-8", cwd=self.working_dir, timeout=10,
                )
                git_diff = result.stdout.strip()
                if git_diff:
                    has_changes = True
                    print(f"\n  {C.BOLD}Changes (git diff):{C.RESET}")
                    lines = git_diff.split("\n")
                    for line in lines[:60]:
                        if line.startswith("+") and not line.startswith("+++"):
                            print(f"  {C.GREEN}{line}{C.RESET}")
                        elif line.startswith("-") and not line.startswith("---"):
                            print(f"  {C.RED}{line}{C.RESET}")
                        elif line.startswith("@@"):
                            print(f"  {C.CYAN}{line}{C.RESET}")
                        else:
                            print(f"  {line}")
                    if len(lines) > 60:
                        print(f"  {C.DIM}... ({len(lines) - 60} more lines){C.RESET}")
            except Exception:
                pass

        if not has_changes:
            print(f"\n  {C.YELLOW}No changes detected{C.RESET}")
            return "rejected"

        return self._heal_prompt_approval(snapshots)

    def _show_inline_diff(self, original, current, filename=""):
        """Show colored unified diff."""
        orig_lines = original.splitlines(keepends=True)
        curr_lines = current.splitlines(keepends=True)
        diff = list(difflib.unified_diff(
            orig_lines, curr_lines,
            fromfile=f"a/{filename}", tofile=f"b/{filename}",
            lineterm="",
        ))
        if not diff:
            print(f"  {C.DIM}(no diff){C.RESET}")
            return

        shown = 0
        total = len(diff)
        for line in diff:
            line = line.rstrip("\n")
            if shown >= 60:
                remaining = total - shown
                print(f"  {C.DIM}... ({remaining} more lines) "
                      f"Show full? [y/n]{C.RESET}", end=" ", flush=True)
                try:
                    ans = input().strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if ans != "y":
                    break
                shown = 0  # Reset counter for the rest
            if line.startswith("+") and not line.startswith("+++"):
                print(f"  {C.GREEN}{line}{C.RESET}")
            elif line.startswith("-") and not line.startswith("---"):
                print(f"  {C.RED}{line}{C.RESET}")
            elif line.startswith("@@"):
                print(f"  {C.CYAN}{line}{C.RESET}")
            else:
                print(f"  {line}")
            shown += 1

    def _heal_prompt_approval(self, snapshots):
        """Prompt user to approve, reject, or instruct. Returns status string."""
        if getattr(self, "_auto_mode", False):
            print(f"  {C.GREEN}Auto-approved{C.RESET}")
            return "approved"
        print()
        try:
            ans = input(
                f"  {C.BOLD}(y){C.RESET} approve  "
                f"{C.BOLD}(n){C.RESET} discard  "
                f"{C.BOLD}(i){C.RESET} instruct\n  > "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            self._heal_restore(snapshots)
            return "rejected"

        if ans == "n":
            self._heal_restore(snapshots)
            print(f"  {C.YELLOW}Changes discarded{C.RESET}")
            return "rejected"
        elif ans == "i":
            self._heal_restore(snapshots)
            return "instructed"
        else:
            return "approved"

    def _heal_restore(self, snapshots):
        """Restore files from snapshots."""
        for filepath, content in snapshots.items():
            pathlib.Path(filepath).write_text(content, encoding="utf-8")

    def _heal_verify(self, issue, pre_fix_snapshot=None):
        """Verify a fix: 1 API call + py_compile syntax check."""
        fname = issue.get("file", "unknown")
        target = self._resolve_file(fname)
        if not target or not target.exists():
            return "fixed"

        # Syntax check (zero API cost)
        if target.suffix == ".py":
            try:
                import py_compile
                py_compile.compile(str(target), doraise=True)
            except py_compile.PyCompileError as e:
                print(f"  {C.RED}Syntax error: {e}{C.RESET}")
                return "unfixed"

        # Single API call: issue + current code → verdict
        print(f"  {C.DIM}Verifying fix...{C.RESET}")
        content = target.read_text(encoding="utf-8", errors="replace")
        verify_input = (
            f"ISSUE:\n{issue.get('title', '')}: "
            f"{issue.get('description', '')}\n\n"
            f"CURRENT CODE ({fname}):\n{content[:8000]}"
        )
        output = self._call_model(
            self._load_intent("heal_verify", HEAL_VERIFY_PROMPT),
            verify_input)

        # Parse verdict
        result = "fixed"
        if output:
            for line in output.strip().split("\n"):
                upper = line.strip().upper()
                if upper.startswith("VERDICT:"):
                    v = upper.split(":", 1)[1].strip().split()[0]
                    if v in ("FIXED", "PARTIAL", "UNFIXED"):
                        result = v.lower()
                elif upper.startswith("REGRESSION:") and "YES" in upper:
                    detail = ""
                    for dl in output.strip().split("\n"):
                        if dl.strip().upper().startswith("DETAIL:"):
                            detail = dl.split(":", 1)[1].strip()
                    print(f"  {C.YELLOW}Warning: possible regression"
                          f"{' — ' + detail if detail else ''}{C.RESET}")

        color = {"fixed": C.GREEN, "partial": C.YELLOW,
                 "unfixed": C.RED}.get(result, C.DIM)
        print(f"  {color}{result.upper()}{C.RESET}")
        return result

    def _heal_extract_from_reports(self, deep_dir):
        """Extract issues from all available reports in .deep/."""
        all_issues = []
        sources = []

        report_path = deep_dir / "report.md"
        if report_path.exists():
            sources.append(report_path)
        for bp in sorted(deep_dir.glob("brain_*.md")):
            sources.append(bp)
        findings_dir = deep_dir / "findings"
        if findings_dir.is_dir():
            for fp in sorted(findings_dir.glob("*.md")):
                sources.append(fp)

        for src in sources:
            text = src.read_text(encoding="utf-8")
            issues = self._extract_issues(text)
            if issues:
                # Backfill "unknown" file fields from findings filename
                # e.g. findings/prism.md → prism.py
                src_stem = src.stem
                for iss in issues:
                    if iss.get("file") == "unknown" and src_stem != "report":
                        # Try common extensions
                        for ext in (".py", ".js", ".ts", ".go", ".rs"):
                            candidate = self._resolve_file(src_stem + ext)
                            if candidate and candidate.exists():
                                iss["file"] = src_stem + ext
                                break
                print(f"  {C.DIM}Extracted {len(issues)} issues "
                      f"from {src.name}{C.RESET}")
                all_issues.extend(issues)

        # Re-number sequentially and deduplicate by title
        seen = set()
        deduped = []
        for issue in all_issues:
            title = issue.get("title", "").lower().strip()
            if title and title in seen:
                continue
            seen.add(title)
            deduped.append(issue)
        for i, issue in enumerate(deduped, 1):
            issue["id"] = i

        return deduped

    def _cmd_heal(self, arg):
        """/fix [file] [deep] [auto] — interactive fix pipeline with diff review."""
        # Parse modifiers
        deep_mode = False
        auto_mode = False
        file_arg = None
        if arg:
            parts = arg.split()
            modifiers = {"deep", "auto"}
            flags = [p for p in parts if p in modifiers]
            file_parts = [p for p in parts if p not in modifiers]
            deep_mode = "deep" in flags
            auto_mode = "auto" in flags
            file_arg = file_parts[0] if file_parts else None
            if deep_mode and not file_arg:
                print(f"{C.YELLOW}Usage: /fix <file> deep{C.RESET}")
                return

        # Deep mode: always rescan with full prism (3 calls)
        if deep_mode:
            content, name = self._get_deep_content(file_arg)
            if not content:
                print(f"{C.RED}File not found: {file_arg}{C.RESET}")
                return
            self._run_full_pipeline(content, name)
            # Clear cached issues so we re-extract from fresh findings
            issues_path = self.working_dir / ".deep" / "issues.json"
            if issues_path.exists():
                issues_path.unlink()
            arg = name  # fall through to heal with file filter
            file_arg = name

        deep_dir = self.working_dir / ".deep"
        issues_path = deep_dir / "issues.json"

        # Load or extract issues
        issues = []
        if issues_path.exists():
            try:
                data = json.loads(issues_path.read_text(encoding="utf-8"))
                self._ensure_version(data)
                issues = data if isinstance(data, list) else data.get("issues", [])
                extracted_at = None
                if isinstance(data, dict):
                    extracted_at = data.get("extracted_at")
                # Stale check
                if extracted_at:
                    try:
                        ts = time.mktime(time.strptime(
                            extracted_at, "%Y-%m-%dT%H:%M:%S"))
                        age_hours = (time.time() - ts) / 3600
                        if age_hours > 24:
                            print(f"  {C.YELLOW}Issues may be stale "
                                  f"({int(age_hours)}h old). "
                                  f"Re-run /scan?{C.RESET}")
                    except (ValueError, OverflowError):
                        pass
                # File drift check — warn if source files have been
                # manually edited since findings were generated.
                file_mtimes = (data.get("file_mtimes", {})
                               if isinstance(data, dict) else {})
                drifted = []
                for _fname, _saved_mtime in file_mtimes.items():
                    _target = self._resolve_file(_fname)
                    if _target and _target.exists():
                        try:
                            if _target.stat().st_mtime > _saved_mtime + 1:
                                drifted.append(_fname)
                        except OSError:
                            pass
                if drifted:
                    print(f"  {C.YELLOW}Warning: {len(drifted)} file(s) "
                          f"modified since findings were generated:{C.RESET}")
                    for _df in drifted:
                        print(f"    {C.DIM}{_df}{C.RESET}")
                    print(f"  {C.YELLOW}Verification may compare against a "
                          f"stale baseline — re-run /scan to refresh."
                          f"{C.RESET}")
            except (json.JSONDecodeError, OSError):
                issues = []

        # No issues found — auto-scan with single prism, then extract
        if not issues and not deep_mode:
            if file_arg:
                content, name = self._get_deep_content(file_arg)
                if not content:
                    print(f"{C.RED}File not found: {file_arg}{C.RESET}")
                    return
                print(f"{C.CYAN}No scan results — running single prism...{C.RESET}")
                self._run_single_lens_streaming("l12", content, name)
            else:
                print(f"{C.YELLOW}No scan results. "
                      f"Specify a file: /fix <file>{C.RESET}")
                return
            # Re-extract from fresh findings
            deep_dir.mkdir(parents=True, exist_ok=True)
            issues_path = deep_dir / "issues.json"
            if issues_path.exists():
                issues_path.unlink()
            print(f"  {C.DIM}Extracting issues from reports...{C.RESET}")
            issues = self._heal_extract_from_reports(deep_dir)
            if not issues:
                print(f"{C.GREEN}No issues found.{C.RESET}")
                return
            self._heal_save_issues(deep_dir, issues)

        # Filter by file if specified
        if file_arg:
            issues = [i for i in issues
                      if file_arg in i.get("file", "")]
            if not issues:
                print(f"{C.YELLOW}No issues for '{file_arg}'{C.RESET}")
                return

        total = len(issues)
        open_count = sum(1 for i in issues if i.get("status") != "fixed")
        print(f"\n  {C.BOLD}{C.CYAN}FIX{C.RESET}  "
              f"{total} issues ({open_count} open)")

        if auto_mode:
            selected = [i for i in issues if i.get("status") != "fixed"]
            if not selected:
                print(f"  {C.GREEN}All issues already fixed!{C.RESET}")
                return
            self._auto_mode = True
            max_passes = 3
        else:
            selected = self._heal_pick_issues(issues)
            if not selected:
                print(f"{C.DIM}Cancelled{C.RESET}")
                return
            self._auto_mode = False
            max_passes = 1

        grand_stats = {"approved": 0, "rejected": 0, "fixed": 0,
                       "partial": 0, "unfixed": 0}

        for pass_num in range(1, max_passes + 1):
            if pass_num > 1:
                selected = [i for i in issues
                            if i.get("status") in ("unfixed", "partial")]
                if not selected:
                    break
                print(f"\n  {C.BOLD}{C.CYAN}── Pass {pass_num}: "
                      f"retrying {len(selected)} unfixed ──{C.RESET}\n")

            if pass_num == 1:
                print(f"\n  Fixing {len(selected)} issue(s)"
                      f"{f' (auto, up to {max_passes} passes)' if auto_mode else ''}\n")

            stats = {"approved": 0, "rejected": 0, "fixed": 0,
                     "partial": 0, "unfixed": 0}

            for idx, issue in enumerate(selected, 1):
                title = issue.get("title", "untitled")
                print(f"  {C.BOLD}{C.CYAN}── Issue {idx}/{len(selected)}: "
                      f"{title} ──{C.RESET}")

                attempts = 0
                instructions = ""
                while attempts < 3:
                    attempts += 1

                    fix_issue = dict(issue)
                    if instructions:
                        fix_issue["action"] = (
                            f"{issue.get('action', '')} "
                            f"User instructions: {instructions}"
                        )

                    result, snapshots = self._heal_fix_one(fix_issue)

                    if result == "approved":
                        stats["approved"] += 1
                        _t = self._resolve_file(fix_issue.get("file", ""))
                        pre_fix = snapshots.get(str(_t)) if _t else None
                        verdict = self._heal_verify(
                            issue, pre_fix_snapshot=pre_fix)
                        stats[verdict] = stats.get(verdict, 0) + 1
                        issue["status"] = verdict
                        break

                    elif result == "rejected":
                        stats["rejected"] += 1
                        break

                    elif result == "instructed":
                        if auto_mode:
                            stats["rejected"] += 1
                            break
                        try:
                            instructions = input(
                                f"  {C.GREEN}Instructions:{C.RESET} "
                            ).strip()
                        except (EOFError, KeyboardInterrupt):
                            print()
                            stats["rejected"] += 1
                            break
                        if not instructions:
                            stats["rejected"] += 1
                            break
                        print(f"  {C.DIM}Retrying with instructions "
                              f"(attempt {attempts + 1}/3)...{C.RESET}")
                print()

            for k in grand_stats:
                grand_stats[k] += stats.get(k, 0)

            self._heal_save_issues(deep_dir, issues)

            fixed_now = sum(1 for i in issues
                           if i.get("status") == "fixed")
            if auto_mode:
                print(f"  {C.BOLD}Pass {pass_num}:{C.RESET} "
                      f"{stats.get('fixed', 0)} fixed, "
                      f"{stats.get('unfixed', 0)} unfixed "
                      f"({fixed_now}/{total} total)")

        self._auto_mode = False

        # Summary
        print(f"\n  {C.BOLD}Summary:{C.RESET} "
              f"{grand_stats['approved']} approved, "
              f"{grand_stats.get('fixed', 0)} fixed, "
              f"{grand_stats.get('partial', 0)} partial, "
              f"{grand_stats.get('unfixed', 0)} unfixed, "
              f"{grand_stats['rejected']} rejected")
        print()

    def _heal_save_issues(self, deep_dir, issues):
        """Save issues to .deep/issues.json."""
        deep_dir.mkdir(parents=True, exist_ok=True)
        issues_path = deep_dir / "issues.json"
        # Snapshot the current mtime of every referenced file so we can
        # detect manual edits that happen between scan and approval time.
        file_mtimes = {}
        for issue in issues:
            fname = issue.get("file", "")
            if fname and fname not in file_mtimes:
                target = self._resolve_file(fname)
                if target and target.exists():
                    try:
                        file_mtimes[fname] = target.stat().st_mtime
                    except OSError:
                        pass
        data = {
            "_version": 1,
            "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "file_mtimes": file_mtimes,
            "issues": issues,
        }
        issues_path.write_text(
            json.dumps(data, indent=2), encoding="utf-8")
        print(f"  {C.DIM}Saved: .deep/issues.json "
              f"({len(issues)} items){C.RESET}")
    def _parse_stage_json(self, raw, stage_name):
        """Parse JSON from a stage response. Returns parsed data or None."""
        if not raw or raw.startswith("[Error"):
            self._log_parse_failure(f"{stage_name}:call", raw, "empty or error")
            return None
        # Strip markdown code fences
        cleaned = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
        cleaned = re.sub(r'^```\s*$', '', cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback: find JSON array or object anywhere
            for pattern in (r'\[.*\]', r'\{.*\}'):
                m = re.search(pattern, cleaned, re.DOTALL)
                if m:
                    try:
                        return json.loads(m.group())
                    except json.JSONDecodeError:
                        continue
            self._log_parse_failure(f"{stage_name}:parse", raw[:500], "no valid JSON")
            return None

    # ── Message building ─────────────────────────────────────────────────

    def _build_message(self, user_input):
        """Prepend queued file contents to user input.

        Structural context (lens findings) goes into the system prompt
        via _enriched_system_prompt, NOT here. This keeps the user message
        clean — just the files and the request.
        """
        parts = []
        for fpath in self.queued_files:
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                parts.append(f"<file path=\"{fpath}\">\n{content}\n</file>")
            except Exception as e:
                parts.append(f"[Error reading {fpath}: {e}]")
        parts.append(user_input)
        return "\n\n".join(parts)

    # ── Streaming ────────────────────────────────────────────────────────

    def _send_and_stream(self, message):
        """Send message to Claude and stream the response to stdout.

        Validates session consistency before each send: if a previous turn caused
        a session ID change (network hiccup / expiry), the user must explicitly
        acknowledge the divergence before we continue.
        """
        if self._session_diverged and not self._confirm_session_diverged():
            return  # User declined to continue in a diverged context

        # Use enriched system prompt if lens analysis was injected,
        # otherwise fall back to base system prompt.
        active_prompt = getattr(self, '_enriched_system_prompt', None)
        if active_prompt:
            self._enriched_system_prompt = None  # one-shot, reset after use
        base = active_prompt or self.system_prompt
        # Prepend active lens if set via /prism <lens>.
        # Only for chat — skip if enriched prompt is set (implies /fix or /scan context).
        if self._active_lens_prompt and not active_prompt:
            base = self._active_lens_prompt + "\n\n" + base
        self.backend = ClaudeBackend(
            model=self.session.model,
            working_dir=str(self.working_dir),
            session_id=self.session.session_id,
            system_prompt=base,
        )
        parser = StreamParser()
        self._interrupted = False
        had_output = False
        thinking_shown = False
        tools_used = set()

        original_sigint = signal.getsignal(signal.SIGINT)

        def on_interrupt(sig, frame):
            self._interrupted = True
            if self.backend:
                self.backend.kill()

        signal.signal(signal.SIGINT, on_interrupt)

        try:
            for line in self.backend.send(message):
                if self._interrupted:
                    break

                for evt, data in parser.parse_line(line):
                    if evt == "text":
                        if thinking_shown:
                            sys.stdout.write("\r" + " " * 30 + "\r")
                            thinking_shown = False
                        sys.stdout.write(data)
                        sys.stdout.flush()
                        had_output = True

                    elif evt == "thinking":
                        if not thinking_shown:
                            sys.stdout.write(f"{C.DIM}thinking...{C.RESET}")
                            sys.stdout.flush()
                            thinking_shown = True

                    elif evt == "tool_use":
                        if thinking_shown:
                            sys.stdout.write("\r" + " " * 30 + "\r")
                            thinking_shown = False
                        if had_output:
                            print()
                            had_output = False
                        tools_used.add(data)
                        print(f"  {C.MAGENTA}[{data}]{C.RESET}")

                    elif evt == "result":
                        self._handle_result(data)

        except Exception as e:
            print(f"\n{C.RED}Error: {e}{C.RESET}")

        finally:
            signal.signal(signal.SIGINT, original_sigint)
            if thinking_shown:
                sys.stdout.write("\r" + " " * 30 + "\r")
            if self._interrupted:
                print(f"\n{C.YELLOW}interrupted{C.RESET}")
            elif had_output:
                print()  # Final newline after text
            self._post_response_hint(tools_used)
            print()  # Blank line before next prompt

    # ── Session integrity ─────────────────────────────────────────────────

    def _on_session_transition(self, old_sid, new_sid):
        """Handle an unexpected session ID change: log it, warn the user, set diverged flag."""
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        entry = {
            "timestamp": ts,
            "old_session_id": old_sid,
            "new_session_id": new_sid,
            "turn": self.session.turn_count,
        }
        self._session_transition_log.append(entry)
        self._session_diverged = True
        self._write_transition_log(entry)

        # Immediate visible warning (printed mid-stream before the result line)
        print(f"\n{C.RED}{C.BOLD}⚠  SESSION ID CHANGED{C.RESET}")
        print(f"  {C.RED}Previous: ...{old_sid[-16:]}{C.RESET}")
        print(f"  {C.RED}New:      ...{new_sid[-16:]}{C.RESET}")
        print(f"  {C.YELLOW}Context from turns 1–{self.session.turn_count} "
              f"may be lost (network hiccup or session expiry).{C.RESET}")
        print(f"  {C.DIM}Transition logged to .deep/session_transitions.log{C.RESET}")

    def _write_transition_log(self, entry):
        """Append a session transition record to .deep/session_transitions.log."""
        try:
            deep_dir = self.working_dir / ".deep"
            deep_dir.mkdir(parents=True, exist_ok=True)
            log_path = deep_dir / "session_transitions.log"
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except OSError:
            pass  # Non-fatal: log write failure should not break the REPL

    def _confirm_session_diverged(self):
        """Gate for session-diverged state: warn and require explicit user acknowledgment.

        Returns True to proceed, False to abort the pending send.
        Clears the diverged flag on acknowledgment so the gate fires only once per
        transition unless another divergence occurs.
        """
        transitions = len(self._session_transition_log)
        print(f"\n{C.RED}{C.BOLD}⚠  SESSION CONTEXT DIVERGED{C.RESET}")
        print(f"  {C.YELLOW}{transitions} session transition(s) detected "
              f"since turn {self._session_transition_log[0]['turn'] if transitions else '?'}.{C.RESET}")
        print(f"  {C.YELLOW}Claude may not remember your earlier turns.{C.RESET}")
        print(f"  {C.DIM}Options: /clear to start fresh | "
              f"/load <name> to restore a saved checkpoint{C.RESET}")
        try:
            ack = input(
                f"  {C.GREEN}Continue in diverged context? [y/N]:{C.RESET} "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if ack == "y":
            self._session_diverged = False  # Cleared — user explicitly acknowledged
            print(f"  {C.DIM}Continuing. Consider /save to checkpoint the current session.{C.RESET}\n")
            return True
        print(f"  {C.YELLOW}Aborted. Use /clear or /load to restore context.{C.RESET}\n")
        return False

    def _handle_result(self, data):
        """Extract session_id, usage, and cost from the result event.

        Detects session ID changes (old non-None → new different non-None) that
        indicate a reconnect or network hiccup, and triggers the divergence workflow.
        """
        sid = data.get("session_id")
        if sid:
            old_sid = self.session.session_id
            if old_sid and sid != old_sid:
                # Session ID changed mid-conversation — context may be lost
                self._on_session_transition(old_sid, sid)
            self.session.session_id = sid

        usage = data.get("usage", {})
        self.session.total_input_tokens += usage.get("input_tokens", 0)
        self.session.total_output_tokens += usage.get("output_tokens", 0)

        cost = data.get("total_cost_usd", data.get("cost_usd", 0))
        if isinstance(cost, (int, float)):
            self.session.total_cost_usd += cost

        self.session.turn_count += 1


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Prism — structural code analysis through analytical lenses",
    )
    ap.add_argument("-m", "--model", default="haiku",
                    choices=["haiku", "sonnet", "opus"],
                    help="model (default: haiku)")
    ap.add_argument("-d", "--dir", default=".",
                    help="working directory (default: cwd)")
    ap.add_argument("-r", "--resume", default=None, metavar="SESSION",
                    help="resume a saved session")
    ap.add_argument("--review", default=None, metavar="PATH",
                    help="non-interactive review: run lenses, output report")
    ap.add_argument("-o", "--output", default=None, metavar="FILE",
                    help="write review output to file (default: stdout)")
    ap.add_argument("--lens", default=None,
                    help="comma-separated lenses for review (default: all)")
    ap.add_argument("--json", action="store_true", dest="json_output",
                    help="output review as JSON instead of markdown")
    args = ap.parse_args()

    if args.review:
        repl = PrismREPL(
            model=args.model,
            working_dir=args.dir,
        )
        lenses = args.lens.split(",") if args.lens else None
        code = repl.review(
            path=args.review,
            lenses=lenses,
            json_output=args.json_output,
            output_file=args.output,
        )
        sys.exit(code)

    repl = PrismREPL(
        model=args.model,
        working_dir=args.dir,
        resume_session=args.resume,
    )
    repl.run()


if __name__ == "__main__":
    main()
