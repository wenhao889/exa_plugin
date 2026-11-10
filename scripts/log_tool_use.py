#!/usr/bin/env python3
"""PostToolUse hook: append a redacted audit line for every tool call.

Registered with "async": true in hooks/hooks.json so it never delays the agent.
It must never fail the conversation: every error path exits 0.

Log file: $SECRET_GUARD_LOG, or
$OPENHANDS_PROJECT_DIR/.openhands/secret-guard/audit.jsonl.

One JSON object per line:

    {"ts": "...", "tool": "terminal", "decision": "allowed",
     "args": "git status", "exit_code": 0}
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Anything shaped like a credential gets replaced before it is written.
REDACTIONS = [
    (re.compile(r"\b(sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{8,}|AKIA[0-9A-Z]{12,})"), "[redacted-key]"),
    (re.compile(r"(?i)\b(api[_-]?key|token|password|secret)\b\s*[=:]\s*\S+"), r"\1=[redacted]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{8,}"), "Bearer [redacted]"),
]

MAX_ARGS_CHARS = 300


def log_path() -> Path:
    override = os.environ.get("SECRET_GUARD_LOG")
    if override:
        return Path(override).expanduser()
    project_dir = os.environ.get("OPENHANDS_PROJECT_DIR") or os.getcwd()
    return Path(project_dir) / ".openhands" / "secret-guard" / "audit.jsonl"


def redact(text: str) -> str:
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def summarize(tool_input: dict) -> str:
    """One-line, redacted description of what the tool was asked to do."""
    for key in ("command", "path", "file_path", "query", "thought"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            text = " ".join(value.split())
            return redact(text[:MAX_ARGS_CHARS])
    return ""


def main() -> None:
    try:
        raw = sys.stdin.read()
    except Exception:
        return

    try:
        event = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return
    if not isinstance(event, dict):
        return

    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": str(event.get("tool_name", "unknown")),
        "decision": "denied" if event.get("blocked") else "allowed",
        "args": summarize(tool_input),
    }
    for key in ("session_id", "exit_code"):
        if event.get(key) is not None:
            record[key] = event[key]

    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
    except Exception:
        # An unwritable log must not break the agent's turn.
        return


if __name__ == "__main__":
    main()
