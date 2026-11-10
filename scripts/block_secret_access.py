#!/usr/bin/env python3
"""PreToolUse hook: deny tool calls that would read or print secrets.

OpenHands passes the hook event as JSON on stdin, for example:

    {"tool_name": "terminal", "tool_input": {"command": "cat .env"}}

Exit codes follow the OpenHands / Claude Code hook contract:
  0 - allow the call to proceed
  2 - block the call; the printed JSON reason is fed back to the agent
  other - a non-blocking error (logged, but the call still runs)

So this script exits 2 only for a deliberate policy denial, and exits 0 for
anything it does not recognise, including malformed input. Failing open on
parser errors keeps a bug in this hook from wedging the conversation.
"""

from __future__ import annotations

import json
import re
import shlex
import sys

# Commands whose whole purpose is to dump process environment.
ENV_DUMP_COMMANDS = {"printenv", "env"}

# Commands that read a file's contents. Paired with a secret path to decide.
READERS = {
    "cat",
    "bat",
    "less",
    "more",
    "head",
    "tail",
    "grep",
    "egrep",
    "fgrep",
    "rg",
    "awk",
    "sed",
    "sort",
    "uniq",
    "strings",
    "xxd",
    "od",
    "base64",
    "cp",
    "scp",
    "rsync",
    "source",
    ".",
    "open",
    "code",
}

# Paths that hold credentials. Matched against each word of the command, so
# absolute paths, relative paths, and ~ all work.
SECRET_FILE_RE = re.compile(
    r"""
    (^|/)\.env(\.[\w-]+)?$          # .env, .env.local, .env.production
    | (^|/)\.envrc$                 # direnv
    | (^|/)id_(rsa|dsa|ecdsa|ed25519)(\.pub)?$
    | (^|/)\.(aws|gcp|azure)/        # cloud credential directories
    | (^|/)\.ssh($|/)
    | (^|/)\.netrc$
    | (^|/)\.pgpass$
    | (^|/)\.npmrc$                 # may carry a registry token
    | (^|/)\.docker/config\.json$
    | (^|/)\.kube/config$
    | (^|/)secrets?\.(json|ya?ml|toml|ini|env)$
    """,
    re.VERBOSE,
)

# Editor tools that take a path instead of a command.
FILE_TOOLS = {"file_editor", "str_replace_editor", "editor"}


def deny(reason: str) -> None:
    """Emit the structured denial and exit 2."""
    print(json.dumps({"decision": "deny", "reason": reason}))
    sys.exit(2)


def words_of(command: str) -> list[str]:
    """Split a shell command into words, tolerating unbalanced quotes."""
    try:
        return shlex.split(command, comments=False, posix=True)
    except ValueError:
        return command.split()


def find_secret_path(words: list[str]) -> str | None:
    """Return the first word that names a credential file, if any."""
    for word in words:
        cleaned = word.strip("'\";|&<>()$`")
        if not cleaned:
            continue
        # Ignore redirection targets like 2>/dev/null and bare flags.
        if cleaned.startswith(("-", "/dev/", "$")):
            continue
        if SECRET_FILE_RE.search(cleaned):
            return cleaned
    return None


def check_terminal(command: str) -> None:
    words = words_of(command)

    # Bare `printenv`, `env`, or `env | grep KEY` dumps the environment.
    head = [w for w in words if w]
    if head and head[0] in ENV_DUMP_COMMANDS:
        deny(
            f"`{head[0]}` dumps the process environment, which holds API keys "
            "and tokens. Name the variable you need instead, for example "
            "`printf '%s' \"$API_KEY\" | wc -c` to check it is set."
        )

    secret_path = find_secret_path(words)
    if secret_path is None:
        return

    readers = {w for w in words if w in READERS}
    if not readers and not re.search(r"[<]\s*[^\s]*" + re.escape(secret_path), command):
        # The path is mentioned but nothing reads it: `ls .env` is fine.
        return

    reader = sorted(readers)[0] if readers else "a shell redirect"
    deny(
        f"`{reader}` on `{secret_path}` would print a credential into the "
        "conversation, tool output, and the audit log. Read `.env.example` "
        "for the documented variable names, or ask the user which variable "
        "you need - do not read the secret file itself."
    )


def check_file_tool(tool_input: dict) -> None:
    path = tool_input.get("path") or tool_input.get("file_path") or ""
    if not isinstance(path, str) or not path:
        return
    if SECRET_FILE_RE.search(path.strip()):
        deny(
            f"`{path}` holds credentials. Reading it would put the value in "
            "the conversation transcript. Use `.env.example` for the shape of "
            "the file, or ask the user which variable name you need."
        )


def main() -> None:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        # Malformed event: allow, but say why so it shows up in the hook log.
        print(json.dumps({"additionalContext": "secret-guard: unparseable hook event, skipping checks"}))
        return

    tool_name = str(event.get("tool_name", ""))
    tool_input = event.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return

    if tool_name == "terminal":
        command = tool_input.get("command")
        if isinstance(command, str) and command.strip():
            check_terminal(command)
    elif tool_name in FILE_TOOLS:
        check_file_tool(tool_input)


if __name__ == "__main__":
    main()
