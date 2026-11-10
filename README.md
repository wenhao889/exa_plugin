# secret-guard

A small, complete **OpenHands plugin** you can copy as a starting point. It has
one of every component a plugin can ship, and each component does something
real rather than printing a placeholder:

| Component | File | What it does |
| --- | --- | --- |
| Manifest | `.plugin/plugin.json` | Name, version, entry command |
| Marketplace | `.plugin/marketplace.json` | Catalog entry so the repo loads as a marketplace, not as skills only |
| Skill | `skills/code-style/SKILL.md` | Requirements for writing maintainable code, used by the `implementer` agent |
| Hook | `hooks/hooks.json` + `scripts/block_secret_access.py` | `PreToolUse`: denies tool calls that would print or read secrets |
| Hook | `hooks/hooks.json` + `scripts/log_tool_use.py` | `PostToolUse`: appends a redacted audit line for every tool call |
| Command | `commands/audit.md` | `/secret-guard:audit` summarizes the audit log |
| Agents | `agents/implementer.md`, `reviewer.md`, `test-writer.md` | Delegate targets: write code, review it, add unit tests |

No dependencies beyond `python3`. Hooks are the only executable part, and they
use the standard library.

## Layout

```
secret-guard/
├── .plugin/
│   ├── plugin.json              # manifests: OpenHands reads .plugin/ or .claude-plugin/
│   └── marketplace.json         # catalog: makes this repo installable as a marketplace
├── skills/
│   └── code-style/
│       └── SKILL.md             # one directory per skill
├── hooks/
│   └── hooks.json               # event -> matcher -> [{type, command, timeout}]
├── agents/
│   ├── implementer.md           # writes code from a stated requirement
│   ├── reviewer.md              # reviews a change, reports, does not edit
│   └── test-writer.md           # adds tests and proves they can fail
├── commands/
│   └── audit.md                 # filename becomes the command name
├── scripts/
│   ├── block_secret_access.py   # PreToolUse, exit 2 to deny
│   └── log_tool_use.py          # PostToolUse, never fails the conversation
├── examples/
│   └── load_plugin.py           # loads this plugin with the SDK
└── README.md
```

Optional component this sample deliberately omits: `.mcp.json` for MCP servers.
It is just another file at the plugin root - add it and the loader picks it up.

## One repo, plugin and marketplace

Adding this repository as a plugin source without `.plugin/marketplace.json`
gives:

```
This plugin has no marketplace file, so only its skills will load.
Add .plugin/marketplace.json to load the whole plugin.
```

The loader (`marketplace/registry.py`) looks for a catalog first. When it finds
none, it falls back to `Marketplace.from_skills_dir`, which keeps only
`<name>/SKILL.md` folders - so the hooks, command and agents are silently
dropped even though `plugin.json` is valid. Its log line says it directly:

```
Marketplace '...' is a plugin (.plugin/plugin.json), not a marketplace;
only its skills are loaded, and its hooks, MCP servers, commands and agents
are ignored
```

The catalog lists the plugin at the repo root:

```json
{
  "name": "exa-plugin",
  "owner": { "name": "Example Author" },
  "plugins": [
    { "name": "secret-guard", "source": ".", "version": "1.0.0" }
  ]
}
```

`"source": "."` is intentional: entries are resolved against the marketplace
directory after `lstrip("./")`, so `"."` becomes the repo root itself. The
marketplace is named `exa-plugin` rather than `secret-guard` so the install
reference reads `secret-guard@exa-plugin` instead of repeating one name twice.

`examples/load_plugin.py` resolves the plugin through `MarketplaceRegistry` -
the same path the UI uses - and fails if the source does not land on this repo.

## Load it

Three ways, all equivalent:

```python
# 1. Conversation (fetches and loads in one step)
from openhands.sdk.plugin import PluginSource

conversation = Conversation(
    agent=agent,
    plugins=[PluginSource(source="/path/to/secret-guard")],
    workspace="/path/to/workspace",
)
```

```python
# 2. Direct load
from openhands.sdk.plugin import Plugin

plugin = Plugin.load("/path/to/secret-guard")
agent = agent.model_copy(
    update={"agent_context": plugin.add_skills_to(agent.agent_context)}
)
conversation = Conversation(agent=agent, hook_config=plugin.hooks)
```

```bash
# 3. Local plugin directory, discovered automatically as a read-only "Local" plugin
ln -s "$PWD" ~/.agents/plugins/secret-guard
```

From a git remote, `PluginSource(source="github:owner/secret-guard", ref="v1.0.0")`
works too - pin a tag so a plugin cannot change under a running conversation.

Verify the plugin parses without starting a conversation:

```bash
uv run --with openhands-sdk python examples/load_plugin.py
```

## The three agents

`agents/<name>.md` is a delegate sub-agent: YAML frontmatter for
`name`/`description`/`tools`/`model`, with the Markdown body used as its system
prompt. The main agent hands work to them by name; `model: inherit` reuses the
conversation's model.

| Agent | Job | Notable settings |
| --- | --- | --- |
| `implementer` | Writes the smallest change that meets the requirement, runs the narrow check, reports changed/verified/open | `tools: [file_editor, terminal]`, 60 iterations |
| `reviewer` | Reports findings by `file:line` with severity, never edits | `permission_mode: confirm_risky`, 40 iterations |
| `test-writer` | Adds tests and proves each one can fail | `tools: [file_editor, terminal]`, 50 iterations |

They are written as one loop rather than three unrelated prompts:

```
requirement -> implementer -> reviewer (blockers) -> test-writer -> implementer (fixes)
```

Each prompt states what its agent must *not* do - the reviewer may not edit,
the test-writer may not change production code to make a test pass, the
implementer may not refactor beyond the ask - because a specialist agent is
only useful if its scope is enforced.

Plugin agents take precedence over project-level `.agents/agents/*.md` and
user-level agents (only programmatic registration outranks them), so a plugin
can deliberately override a repo's own agent of the same name. Keep names
distinct if you do not want that.

## The code-style skill

`skills/code-style/SKILL.md` states how code has to be written: names that carry
meaning, one job per function, failure handled explicitly instead of swallowed,
types and absence made explicit, comments that explain *why*, no secrets or
debug leftovers, tests shipped with behavior changes, and no work outside the
request. It ends with a checklist, so "done" is checkable rather than a
feeling.

The `implementer` prompt names the skill and restates its checklist, because a
plugin **cannot** attach its own skill to its own agent declaratively. Writing

```yaml
skills:
  - code-style
```

in `agents/implementer.md` looks right and parses fine, but registration
resolves skill names with `load_available_skills(work_dir, include_user=True,
include_project=True, include_public=False)` - project and user skill
directories only, never the plugin's own `skills/`. The lookup raises, and
`register_plugin_agents` catches it and **skips the whole agent**:

```
WARNING Skipping plugin agent 'implementer':
Skill 'code-style' not found but was given to agent 'implementer'.
```

So the frontmatter stays free of `skills:`, the implementer carries the
checklist in its prompt, and the skill file remains the canonical, longer text.
If you install `code-style` into `.agents/skills/code-style/` at project level,
you can move the name back into a `skills:` field. `examples/load_plugin.py`
now runs registration and fails loudly if any agent was skipped, because this
failure mode is otherwise just a log line.

The skill is also a keyword-triggered skill, so the main agent picks it up on
words like "code style" or "naming" - one file, usable by both.

The `reviewer` is intentionally not bound to it: a reviewer that shares the
author's checklist grades its own homework. It judges the result against the
request instead.

## How the hooks work

`openhands.sdk` passes each hook its event as JSON on **stdin**, and reads the
result from **stdout** plus the exit code:

| Exit code | Meaning |
| --- | --- |
| `0` | allow; stdout may carry `{"decision", "reason", "additionalContext"}` |
| `2` | **block** - the printed `reason` goes back to the agent |
| anything else | non-blocking error: logged, the call still runs |

Only `2` blocks. Exit `1` - the usual Unix failure code - lets the call
through, which is the single easiest hook bug to ship.

`block_secret_access.py` denies:

- `printenv`, `env`, `env | sort` - whole-environment dumps
- a reading command (`cat`, `grep`, `head`, `base64`, `cp`, ...) applied to a
  credential path: `.env`, `.env.*`, `.envrc`, `id_rsa`, `~/.ssh/*`,
  `~/.aws/*`, `~/.netrc`, `~/.pgpass`, `~/.npmrc`, `~/.kube/config`
- `file_editor` reads of those same paths

It allows everything else, including `ls .env` - listing a file reveals no
values. (`grep -o '^[A-Z_]*=' .env` is denied too: the policy is that the
secret file is never read, so `.env.example` carries the variable names.)
Malformed hook input fails **open** (allow, with a note) so a parser bug cannot
wedge a conversation.

`log_tool_use.py` is registered with `"async": true`, so it never delays the
agent. It writes JSONL to `.openhands/secret-guard/audit.jsonl` and redacts
common key shapes (`sk-...`, `ghp_...`, `AKIA...`, `token=...`,
`Bearer ...`) before writing. Every failure path exits 0 on purpose: an
unwritable log must not break the user's turn.

Environment variables available to a plugin's command hooks:

| Variable | Value |
| --- | --- |
| `PLUGIN_ROOT` | absolute path of the loaded plugin, set by the SDK |
| `OPENHANDS_PROJECT_DIR` | the conversation's workspace |
| `OPENHANDS_TOOL_NAME` | the tool the hook belongs to (e.g. `terminal`) |

That is why `hooks.json` addresses its scripts as
`python3 "$PLUGIN_ROOT/scripts/block_secret_access.py"` rather than a relative
path: the plugin may be loaded from a cache directory, and the hook runs with
the workspace as its working directory.

## Test the hooks by hand

Feed an event on stdin and check the exit code:

```bash
# deny -> prints {"decision": "deny", ...}, exit 2
echo '{"tool_name": "terminal", "tool_input": {"command": "cat .env"}}' \
  | PLUGIN_ROOT="$PWD" python3 scripts/block_secret_access.py; echo "exit=$?"

# allow -> silent, exit 0
echo '{"tool_name": "terminal", "tool_input": {"command": "git status"}}' \
  | PLUGIN_ROOT="$PWD" python3 scripts/block_secret_access.py; echo "exit=$?"

# audit line
echo '{"tool_name": "terminal", "tool_input": {"command": "curl -H \"Authorization: Bearer abc123456789\" example.com"}}' \
  | OPENHANDS_PROJECT_DIR="$PWD" python3 scripts/log_tool_use.py
tail -n 1 .openhands/secret-guard/audit.jsonl
```

## Limits worth knowing

This is a sample, not a sandbox. It pattern-matches commands, so it stops
accidents and obvious mistakes, not a determined agent: `python -c` reading the
file directly, `git show HEAD:.env`, or a renamed copy all slip past. Real
secrets policy belongs in what the agent is *given* - scoped tokens, a
workspace without the credential file - with hooks as a second layer and the
audit log as evidence of what happened.

## License

MIT
