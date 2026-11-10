---
description: Summarize what the secret-guard hooks recorded for this workspace
argument-hint: "[path to an audit log, defaults to .openhands/secret-guard/audit.jsonl]"
allowed-tools:
  - terminal
  - file_editor
---

Read the secret-guard audit log at `$ARGUMENTS` (default
`.openhands/secret-guard/audit.jsonl` relative to the project directory) and
summarize it for the user.

If the file does not exist, say that no tool calls have been recorded yet and
stop - do not create it.

Otherwise:

1. Count tool calls by `tool` and by `decision` (allowed or denied).
2. List every denied call with its timestamp, tool, and the `reason` the hook
   gave. These are the security-relevant events.
3. Note any command that looks like an attempt to work around a denial, for
   example `sed`, `awk`, `base64`, or an interpreter one-liner aimed at a
   `.env` file. Call these out separately.
4. Keep the report to a short table plus a sentence per denial.

Never print a value from the log that looks like a credential. The hook redacts
common key formats before writing, but report only variable names and file
paths, never values. If you see a value that looks like a live secret, report
its location and recommend rotating it - do not repeat the value.
