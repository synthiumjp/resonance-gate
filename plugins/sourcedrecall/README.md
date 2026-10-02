# sourcedrecall plugin for Claude Code

Local memory for Claude Code. When a session ends, the facts you stated about
yourself are stored with the sentence and date they came from. When the next
session starts, Claude gets a short summary. A grammar parser extracts the
facts; no language model writes the memory, and nothing leaves your machine.

Install:

```
/plugin marketplace add synthiumjp/resonance-gate#product-p2
/plugin install sourcedrecall@resonance-gate
```

The first session sets up a Python environment and downloads the models in
the background (about 3 to 5 minutes). Requirements: Python 3.10+ and git.

What it adds:
- an MCP server with `profile_recall`, `profile_context`, `profile_correct`
  and related tools
- a SessionEnd hook that stores the session
- a SessionStart hook that adds the memory summary

Memory is kept in `~/.sourcedrecall/conversations` and is not removed when
the plugin is uninstalled. Full documentation: `server/README.md` in the
repository.

License: Apache-2.0.
