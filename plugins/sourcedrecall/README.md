# sourcedrecall plugin for Claude Code

Local memory for Claude Code. When a session ends, the facts you stated about
yourself are stored with the sentence and date they came from. When the next
session starts, Claude gets a short summary. A grammar parser extracts the
facts; no language model writes the memory, and nothing leaves your machine.

Install:

```
/plugin marketplace add synthiumjp/sourcedrecall
/plugin install sourcedrecall@sourcedrecall
```

It asks for your name (facts are written about it). The first session sets
up a Python environment and downloads about 0.7 GB of models in the
background (a few minutes). Requirements: Claude Code 2.1.83 or later,
Python 3.10 to 3.13 and git. To check that it works, start a new session
and type `! sourcedrecall-run memory status`; `! sourcedrecall-run memory
show` prints what is stored.

What it adds:
- an MCP server with `profile_recall`, `profile_context`, `profile_correct`
  and related tools
- a SessionEnd hook that stores the session
- a SessionStart hook that adds the memory summary (the `briefing` option
  turns it off; the tools still work) and shows you what was saved since
  you last looked

Memory is kept in `~/.sourcedrecall/conversations` and is not removed when
the plugin is uninstalled. Full documentation: `server/README.md` in the
repository.

License: Apache-2.0.
