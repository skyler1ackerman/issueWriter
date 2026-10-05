"""
Thin wrapper around the Claude Code CLI in non-interactive mode (`claude -p`).

Why the CLI and not the `anthropic` SDK: the CLI authenticates with the
Claude.ai subscription already used for the Claude Code desktop app, so runs
count against the subscription's rate limit instead of pay-per-token API
billing. Swapping this module for an SDK call later is a contained change.

Notes on robustness (mostly Windows):
  * The desktop app does NOT put `claude` on PATH. Install the CLI separately
    (`irm https://claude.ai/install.ps1 | iex`) and run `claude auth login`.
  * `--bare` is deliberately NOT used: it disables subscription auth.
  * Long text is sent on stdin and the system prompt via a temp file, so no
    prompt content ever passes through shell quoting.
  * `--json-schema` is only used when the executable is a real binary. The
    npm `.cmd` shim routes argv through cmd.exe, which mangles embedded quotes.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime

DEFAULT_TIMEOUT_SECONDS = 300


class ClaudeCliError(RuntimeError):
    """Raised when the claude CLI is missing, fails, or returns unusable output."""


# ── Locating the executable ──────────────────────────────────────────────────

def find_claude():
    """Return the path to the claude executable, or None if it cannot be found.

    Prefers a native binary over the npm .cmd shim (see module docstring).
    """
    candidates = []

    found = shutil.which("claude")
    if found:
        candidates.append(found)

    home = os.path.expanduser("~")
    candidates.extend([
        os.path.join(home, ".local", "bin", "claude.exe"),
        os.path.join(home, ".local", "bin", "claude"),
        os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd"),
    ])

    existing = [c for c in candidates if c and os.path.isfile(c)]
    if not existing:
        return None

    # Native binaries first, shims last.
    existing.sort(key=lambda p: p.lower().endswith((".cmd", ".bat")))
    return existing[0]


def install_hint():
    return (
        "The `claude` CLI was not found on this machine. The Claude Code desktop app "
        "does not install it. In PowerShell run:\n"
        "    irm https://claude.ai/install.ps1 | iex\n"
        "then `claude auth login` once, and re-run this script."
    )


def _is_shim(executable):
    return executable.lower().endswith((".cmd", ".bat"))


# ── Running a prompt ─────────────────────────────────────────────────────────

def run_claude(
    stdin_text,
    system_prompt,
    json_schema=None,
    model=None,
    allowed_tools=None,
    max_turns=1,
    timeout=DEFAULT_TIMEOUT_SECONDS,
    executable=None,
    cwd=None,
):
    """Run one non-interactive claude call and return the parsed result.

    Args:
        stdin_text:    The task context, piped to claude on stdin.
        system_prompt: Full replacement system prompt (this is not a coding task,
                       so Claude Code's default prompt is replaced, not appended).
        json_schema:   Optional dict. When given, the result is validated against
                       it by the CLI (where supported) and returned as a dict.
        model:         Optional model alias or ID (e.g. "sonnet", "opus").
        allowed_tools: Optional list of permission rules such as
                       "Bash(gh issue view *)". When None, ALL tools are disabled.
        max_turns:     Agentic turn cap. Keep at 1 when no tools are allowed.
        timeout:       Seconds before the subprocess is killed.

    Returns:
        A dict with keys:
            "data"   -> parsed JSON (dict) if json_schema was given, else None
            "text"   -> the raw text result
            "cost"   -> total_cost_usd reported by the CLI (estimate; may be 0.0)
            "raw"    -> the full JSON envelope from --output-format json
    """
    executable = executable or find_claude()
    if not executable:
        raise ClaudeCliError(install_hint())

    use_schema_flag = json_schema is not None and not _is_shim(executable)

    # System prompt goes through a file so it never touches shell quoting.
    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", prefix="issuewriter_sys_", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(system_prompt)
        if json_schema is not None and not use_schema_flag:
            # Shim path: can't pass --json-schema safely, so ask in the prompt.
            fh.write(
                "\n\nRespond with ONLY a single JSON object (no prose, no code fences) "
                "matching this JSON Schema:\n" + json.dumps(json_schema)
            )
        sys_path = fh.name

    cmd = [
        executable,
        "-p",
        "--output-format", "json",
        "--system-prompt-file", sys_path,
        "--no-session-persistence",
        "--strict-mcp-config",          # no --mcp-config given => no MCP servers load
        "--disallowedTools", "mcp__*",  # belt and braces
        "--max-turns", str(max_turns),
    ]

    if allowed_tools:
        cmd += ["--allowedTools", ",".join(allowed_tools)]
        # Restrict the built-in tool surface to Bash only; the allow rules
        # above decide which Bash commands run without a prompt.
        cmd += ["--tools", "Bash"]
    else:
        cmd += ["--tools", ""]

    if model:
        cmd += ["--model", model]

    if use_schema_flag:
        cmd += ["--json-schema", json.dumps(json_schema, separators=(",", ":"))]

    # Short positional prompt; all real content is on stdin.
    cmd.append(
        "Follow the instructions in your system prompt using the issue data provided on stdin."
    )

    try:
        envelope = _run_once(cmd, stdin_text, timeout, cwd)
        if envelope.get("is_error"):
            # One retry: a bare is_error with no message is usually transient
            # (rate limit blip, structured-output validation hiccup).
            envelope = _run_once(cmd, stdin_text, timeout, cwd)
    finally:
        try:
            os.unlink(sys_path)
        except OSError:
            pass

    if envelope.get("is_error"):
        detail = str(envelope.get("result") or "").strip()
        errors = envelope.get("errors") or envelope.get("permission_denials")
        if not detail and errors:
            detail = json.dumps(errors)[:500]
        raise ClaudeCliError(
            f"claude reported an error after retry: {detail[:500] or envelope.get('subtype', 'unknown')}"
        )

    text = envelope.get("result", "") or ""
    data = None
    if json_schema is not None:
        data = envelope.get("structured_output")
        if data is None:
            data = _lenient_json(text)
        if not isinstance(data, dict):
            raise ClaudeCliError(
                f"claude did not return a JSON object. Got: {text[:300]!r}"
            )

    return {
        "data": data,
        "text": text,
        "cost": float(envelope.get("total_cost_usd") or 0.0),
        "usage": usage_from_envelope(envelope),
        "raw": envelope,
    }


USAGE_KEYS = ("input", "output", "cache_read", "cache_create", "turns", "calls")


def empty_usage():
    return {k: 0 for k in USAGE_KEYS}


def usage_from_envelope(envelope):
    """Token counts for one call, normalised to the USAGE_KEYS shape.

    `usage` on the result message is session-wide for that -p run (all turns).
    Falls back to summing `modelUsage` if `usage` is absent.
    """
    u = envelope.get("usage") or {}
    out = empty_usage()
    out["calls"] = 1
    out["turns"] = int(envelope.get("num_turns") or 0)

    if u:
        out["input"] = int(u.get("input_tokens") or 0)
        out["output"] = int(u.get("output_tokens") or 0)
        out["cache_read"] = int(u.get("cache_read_input_tokens") or 0)
        out["cache_create"] = int(u.get("cache_creation_input_tokens") or 0)
        return out

    for m in (envelope.get("modelUsage") or {}).values():
        out["input"] += int(m.get("inputTokens") or 0)
        out["output"] += int(m.get("outputTokens") or 0)
        out["cache_read"] += int(m.get("cacheReadInputTokens") or 0)
        out["cache_create"] += int(m.get("cacheCreationInputTokens") or 0)
    return out


def add_usage(total, part):
    """In-place accumulate one call's usage into a running total."""
    for k in USAGE_KEYS:
        total[k] = total.get(k, 0) + int(part.get(k, 0))
    return total


def format_usage(total, cost=None):
    """Multi-line human summary for the end-of-run report."""
    billed_input = total["input"] + total["cache_create"]
    lines = [
        f"  calls: {total['calls']}   agentic turns: {total['turns']}",
        f"  input tokens: {total['input']:,}   (+ {total['cache_create']:,} written to cache, "
        f"{total['cache_read']:,} read from cache)",
        f"  output tokens: {total['output']:,}",
        f"  total billed-equivalent: {billed_input + total['output']:,} "
        f"(cache reads excluded; they are ~10% cost)",
    ]
    if cost is not None:
        lines.append(f"  CLI cost estimate: ${cost:.2f} (informational on a subscription)")
    return "\n".join(lines)


def _run_once(cmd, stdin_text, timeout, cwd):
    """Run the CLI once and return the parsed JSON envelope."""
    try:
        proc = subprocess.run(
            cmd,
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired as e:
        raise ClaudeCliError(f"claude timed out after {timeout}s") from e

    if proc.returncode != 0 and not proc.stdout.strip():
        raise ClaudeCliError(
            f"claude exited {proc.returncode}: {proc.stderr.strip()[:500]}"
        )
    return _parse_envelope(proc.stdout)


def _parse_envelope(stdout):
    """--output-format json prints one JSON object; tolerate stray leading lines."""
    stdout = stdout.strip()
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        pass
    # Find the last top-level JSON object in the output.
    start = stdout.rfind("\n{")
    if start != -1:
        try:
            return json.loads(stdout[start + 1:])
        except json.JSONDecodeError:
            pass
    raise ClaudeCliError(f"Could not parse claude JSON output: {stdout[:300]!r}")


def _lenient_json(text):
    """Pull a JSON object out of a text reply that may have fences or prose."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    else:
        first, last = text.find("{"), text.rfind("}")
        if first != -1 and last > first:
            text = text[first:last + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ── Result cache ─────────────────────────────────────────────────────────────

class AiCache:
    """Tiny JSON-file cache so re-running the script never re-pays for an issue.

    Layout: {section: {key: {"updated_at": iso, "value": {...}}}}
    A cached entry is reused only if the issue's updated_at is unchanged.
    """

    def __init__(self, path="ai_cache.json"):
        self.path = path
        self._data = {}
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (OSError, json.JSONDecodeError):
                self._data = {}

    @staticmethod
    def key_for(repo_full_name, issue_number):
        return f"{repo_full_name}#{issue_number}"

    def get(self, section, key, updated_at):
        entry = self._data.get(section, {}).get(key)
        if not entry:
            return None
        if entry.get("updated_at") != _iso(updated_at):
            return None
        return entry.get("value")

    def set(self, section, key, updated_at, value):
        self._data.setdefault(section, {})[key] = {
            "updated_at": _iso(updated_at),
            "value": value,
        }
        self.save()

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=1, sort_keys=True)
        os.replace(tmp, self.path)


def _iso(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value is not None else ""
