#!/usr/bin/env python3
"""Load this plugin with the OpenHands SDK and print what it found.

Run from the repository root:

    uv run --with openhands-sdk python examples/load_plugin.py

No API key is needed: this only exercises plugin parsing, not a conversation.
"""

import tempfile
from pathlib import Path

from openhands.sdk.plugin import Plugin
from openhands.sdk.subagent.registry import register_plugin_agents

PLUGIN_DIR = Path(__file__).resolve().parent.parent

plugin = Plugin.load(PLUGIN_DIR)

print(f"name:        {plugin.name}")
print(f"version:     {plugin.version}")
print(f"description: {plugin.description}")
print(f"path:        {plugin.path}")
print(f"entry:       {plugin.entry_slash_command}")

print("\nskills:")
for skill in plugin.skills:
    print(f"  - {skill.name}: {skill.description}")
    if skill.trigger is not None:
        print(f"    trigger: {skill.trigger}")

print("\ncommands (also exposed as keyword-triggered skills):")
for command in plugin.commands:
    hint = f" {command.argument_hint}" if command.argument_hint else ""
    print(f"  - /{plugin.name}:{command.name}{hint} - {command.description}")

print("\nagents:")
for agent in plugin.agents:
    tools = ", ".join(agent.tools) or "(inherits)"
    skills = ", ".join(agent.skills) or "(none)"
    print(f"  - {agent.name} (model={agent.model}, tools={tools}, skills={skills})")
    print(f"    {agent.description[:90]}")

print("\nhooks:")
hooks = plugin.hooks
assert hooks is not None, "hooks/hooks.json did not load"
for matcher in hooks.pre_tool_use:
    for hook in matcher.hooks:
        print(f"  - PreToolUse  matcher={matcher.matcher!r}  {hook.command}")
for matcher in hooks.post_tool_use:
    for hook in matcher.hooks:
        print(f"  - PostToolUse matcher={matcher.matcher!r}  {hook.command}")

# A plugin is only worth loading if its components survived parsing.
skill_names = {skill.name for skill in plugin.skills}
assert "code-style" in skill_names, f"code-style skill missing, got {skill_names}"
assert plugin.commands, "no commands loaded from commands/"
assert len(plugin.agents) == 3, f"expected 3 agents, got {len(plugin.agents)}"
assert hooks.pre_tool_use and hooks.post_tool_use, "expected both hook events"

# Registering is the real test: a definition that names a skill the SDK cannot
# resolve is skipped with a warning, and that agent silently disappears from the
# delegate registry. Parsing alone would not catch it.
with tempfile.TemporaryDirectory() as work_dir:
    registered = register_plugin_agents(plugin.agents, work_dir=work_dir)

expected = {agent.name for agent in plugin.agents}
assert set(registered) == expected, (
    f"registered {sorted(registered)}, expected {sorted(expected)}"
)
print(f"\nregistered agents: {sorted(registered)}")

print("\nOK: plugin loaded with all components")
