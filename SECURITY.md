# Security

sourcedrecall keeps a memory of what you said to your AI assistants, on
your machine. Please report anything that could expose that memory or let
someone else write to it.

## Reporting

Open a private security advisory on GitHub (the repository's Security
tab, "Report a vulnerability"). You should get a reply within a week.
Please do not open a public issue for an unfixed problem.

## What counts

- Text you did not write stored or shown as yours: pasted material, tool
  output, a compaction summary, another session's messages, or anything an
  agent or a web page can make the memory record as your own words.
- A way for an agent or a document to plant a standing instruction, or a
  fact that outranks what you said (for example through the MCP tools).
- A credential that gets past the filter into the stored memory
  (`server/sourcedrecall/secrets.py`; the filter reads English).
- Reading or writing the memory folder from outside your user account, or
  a path in an import file that writes outside it.
- Forget leaving the forgotten text recoverable beyond what the README
  says.

## How the memory is protected now

- Nothing is sent anywhere: models run on your machine and the server runs
  offline after setup.
- The memory folder (`~/.sourcedrecall`) is readable by your user only on
  macOS and Linux; on Windows it uses the folder's normal permissions.
- Text you paste in is marked as written by someone else and is not read
  as your facts or instructions; standing instructions are not stored from
  the MCP ingest tool.
- The MCP tools tell the host which ones change or delete the memory, so it
  can ask you first.

What forget erases, and what it does not yet, is in the README's
"What it does" section.
