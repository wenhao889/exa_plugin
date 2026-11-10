# secret-guard

A small **OpenHands plugin** you can copy as a starting point. It has the
components that matter in practice - manifest, marketplace catalog, skill and
three agents - and each does something real rather than printing a placeholder:

| Component | File | What it does |
| --- | --- | --- |
| Manifest | `.plugin/plugin.json` | Name, version, description |
| Marketplace | `.plugin/marketplace.json` | Catalog entry so the repo loads as a marketplace, not as skills only |
| Skill | `skills/code-style/SKILL.md` | Requirements for writing maintainable code, used by the `implementer` agent |
| Agents | `agents/implementer.md`, `reviewer.md`, `test-writer.md` | Delegate targets: write code, review it, add unit tests |

There is no executable code and no dependency on `python3`: everything here is
configuration and prompts.

## Layout

```
secret-guard/
├── .plugin/
│   ├── plugin.json              # manifests: OpenHands reads .plugin/ or .claude-plugin/
│   └── marketplace.json         # catalog: makes this repo installable as a marketplace
├── skills/
│   └── code-style/
│       └── SKILL.md             # one directory per skill
├── agents/
│   ├── implementer.md           # writes code from a stated requirement
│   ├── reviewer.md              # reviews a change, reports, does not edit
│   └── test-writer.md           # adds tests and proves they can fail
└── README.md
```

Components this sample deliberately omits:

- `hooks/hooks.json` and any scripts it calls
- `commands/` (an `.md` file there becomes `/<plugin>:<filename>`)
- `.mcp.json` for MCP servers

Each is just a file at the plugin root - add it and the loader picks it up.

## One repo, plugin and marketplace

Adding this repository as a plugin source without `.plugin/marketplace.json`
gives:

```
This plugin has no marketplace file, so only its skills will load.
Add .plugin/marketplace.json to load the whole plugin.
```

The loader (`marketplace/registry.py`) looks for a catalog first. When it finds
none, it falls back to `Marketplace.from_skills_dir`, which keeps only
`<name>/SKILL.md` folders - so the agents are silently dropped even though
`plugin.json` is valid. Its log line says it directly:

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
conversation = Conversation(agent=agent)
```

```bash
# 3. Local plugin directory, discovered automatically as a read-only "Local" plugin
ln -s "$PWD" ~/.agents/plugins/secret-guard
```

From a git remote, `PluginSource(source="github:owner/secret-guard", ref="v1.0.0")`
works too - pin a tag so a plugin cannot change under a running conversation.

To check that the catalog resolves to this repo without starting a
conversation:

```bash
uv run --with openhands-sdk python -c "
from openhands.sdk.marketplace import MarketplaceRegistration
from openhands.sdk.marketplace.registry import MarketplaceRegistry

reg = MarketplaceRegistry([MarketplaceRegistration(name='exa-plugin', source='.')])
print(reg.list_plugins(), reg.resolve_plugin('secret-guard').source)
"
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
you can move the name back into a `skills:` field. The skip is only a warning,
so re-read the load log after editing any agent's frontmatter.

The skill is also a keyword-triggered skill, so the main agent picks it up on
words like "code style" or "naming" - one file, usable by both.

The `reviewer` is intentionally not bound to it: a reviewer that shares the
author's checklist grades its own homework. It judges the result against the
request instead.

## License

MIT
