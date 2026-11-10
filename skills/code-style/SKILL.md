---
name: code-style
description: Requirements for writing code that stays maintainable - naming, function shape, error handling, types, comments, and tests. Apply to every change before calling it done.
trigger:
  type: keyword
  keywords:
    - code style
    - code quality
    - naming
    - readability
    - error handling
    - clean code
---

# Writing code

These are requirements, not preferences. Where the project's own conventions
disagree, the project wins - match the files around you and treat this as the
default when there is nothing to copy.

## 1. Fit the codebase

- Match the formatting, naming, and structure of the neighbouring files. Run
  the project's formatter on files you touched; do not reformat files you did
  not.
- Do not add a second way to do something the repo already does (a second HTTP
  client, error type, date library, logger). Find the existing helper first.
- A new dependency is a decision, not a detail: prefer the standard library,
  then an already-installed package. Justify anything else in the report.

## 2. Names carry the meaning

- Names say what the thing is or does, not how it works.
- Booleans read as assertions: `is_ready`, `has_token`, `can_retry` - not
  `flag`, `status`, `check`.
- Functions are verb phrases: `parse_header`, `retry_request`. If a name needs
  "and" (`load_and_validate`), it is two functions.
- No invented abbreviations, and no single letters outside loop indices.

## 3. One job per function

- A function should have one reason to change. If describing it needs a
  paragraph, split it.
- Keep nesting to three levels; use early returns instead of `if` pyramids.
- Aim for four or fewer parameters. More usually means the function knows too
  much - group the data or split the call.
- No hidden work: a getter does not write, a lookup does not send email. Side
  effects belong in a function whose name admits them.

## 4. Failure is part of the design

- Never swallow an error. No bare `except:`/`catch (e) {}`, no empty handler,
  no `pass`. Catch the narrowest type that you can actually handle; if ignoring
  it is correct, say why in a comment.
- Do not mix signaling styles. In a codebase that raises, raise; do not return
  `-1`, `""`, or `None` to mean "failed" as well as "absent".
- Validate at the boundary - user input, HTTP, files, environment, message
  queues - and trust internal calls. Do not re-check the same invariant in
  every layer.
- Error text answers: what failed, with which input (redacted), and what to do
  next. Never include secrets or whole file contents.
- Release what you acquire: context managers, `try/finally`, `defer`, closed
  handles, cancelled timers.

## 5. Data and types

- Annotate public functions and module-level constants where the language
  supports it; let the checker catch what a reader would.
- Be explicit about absence. Treat empty, missing, and default as three
  different cases and decide each one.
- Prefer immutable values and return new objects; mutate only state you own.
- Never use binary floating point for money or exact quantities.
- Parse into a real type at the edge (datetime, Decimal, enum) rather than
  passing strings around and re-parsing them.

## 6. Comments explain why, not what

- Comment the non-obvious: a workaround, a surprising constraint, a deliberate
  tradeoff. Link the issue or spec when one exists.
- Do not narrate code that already reads clearly. Delete commented-out code -
  version control remembers it.
- Document the public surface (purpose, arguments, returns, raises) and keep it
  true when the signature changes.

## 7. Nothing secret, nothing temporary

- Configuration comes from the environment with a safe default. No keys,
  tokens, or passwords in code, fixtures, tests, logs, or error messages.
- Remove debug output (`print`, `console.log`, `dbg!`) before finishing; use
  the project's logger at the right level.
- No dead flags, half-finished branches, or TODOs that should be issues.

## 8. A change includes its proof

- Behavior that changed gets a test that fails without the change. Ask the
  `test-writer` agent if the coverage is substantial.
- Never make a suite green by skipping, loosening an assertion, widening a
  timeout, or adding a suppression. If the check is wrong, fix the check and
  say so.
- Run the narrowest check that covers the change and read its output - not just
  its exit code summary.

## 9. Stay inside the request

- Implement what was asked, at the smallest size that fully does it. No
  drive-by refactors, renames for taste, or speculative abstraction.
- Leave unrelated failing checks as you found them, and report them.
- If the right fix is bigger than the request, say so and propose it instead of
  smuggling it in.

## Before you call it done

- [ ] The diff contains only what the requirement needs.
- [ ] Names, structure, and error handling match the surrounding code.
- [ ] Failure paths are handled and surfaced, not swallowed.
- [ ] No secret, stray debug output, or commented-out code.
- [ ] The narrowest relevant check ran, and its output was read.
- [ ] The report lists what changed, what was verified, and what was left open.
