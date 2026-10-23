---
description: Search your memory and past coding sessions (sourcedrecall)
argument-hint: what to look for, e.g. how did we fix the login test
allowed-tools: mcp__plugin_sourcedrecall_sourcedrecall__history_search, mcp__plugin_sourcedrecall_sourcedrecall__profile_recall
---

Look this up in the user's sourcedrecall memory: $ARGUMENTS

Call history_search with it (all_projects=false; if nothing in this project matches, try again with all_projects=true). If it is about the user rather than the code (who they are, what they prefer), call profile_recall too.

Answer from what comes back, briefly, with the date and session of each thing you use. If nothing matches, say so plainly; do not guess.
