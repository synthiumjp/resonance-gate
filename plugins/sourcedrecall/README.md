# sourcedrecall plugin for Claude Code

Local memory for Claude Code that keeps the record. When a session ends,
what you said is stored in your words with its date, and what the session
did (failed and passing commands, fixes, commits, decisions) is kept per
project. When the next session starts, Claude gets a short summary, leaving
out what the project's own MEMORY.md already says; `/recall how did we fix
the login test` searches past sessions. A grammar parser reads your
messages; no language model writes the memory, and the memory stays on
your machine (what Claude is given goes to Claude like any other context).

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
- an MCP server with `profile_recall`, `profile_context`, `profile_correct`,
  `history_search` (past coding sessions in this project: what failed, what
  fixed it, why) and related tools
- `/recall <what>`: search your memory and past sessions yourself;
  `! sourcedrecall-run memory history <what>` does the same in a terminal
- a SessionEnd hook that stores the session
- a SessionStart hook that adds the memory summary (the `briefing` option
  turns it off; the tools still work) and shows you what was saved since
  you last looked

Memory is kept in `~/.sourcedrecall/conversations` and is not removed when
the plugin is uninstalled. Full documentation: `server/README.md` in the
repository.

License: Apache-2.0.
