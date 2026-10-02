# Connecting sourcedrecall to clients

sourcedrecall is a local MCP server over stdio. The command is `sourcedrecall`, it takes no arguments, and it reads `SOURCEDRECALL_OWNER` (your name) from its environment. Every JSON snippet below uses the same entry; replace `Your Name`.

```json
"sourcedrecall": {
  "command": "sourcedrecall",
  "env": { "SOURCEDRECALL_OWNER": "Your Name" }
}
```

If the client cannot find `sourcedrecall` on its PATH (GUI apps often have a shorter PATH than your shell), use the absolute path to the executable as `command`. The sections below were checked against each vendor's documentation on 2026-10-03. Where a detail could not be confirmed, the section says so.

## Claude Desktop

File: `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows. Settings, Developer, Edit Config opens it. The documentation lists only macOS and Windows; Claude Desktop on Linux is not covered. Restart the app after editing.

```json
{
  "mcpServers": {
    "sourcedrecall": {
      "command": "sourcedrecall",
      "env": { "SOURCEDRECALL_OWNER": "Your Name" }
    }
  }
}
```

Source: https://modelcontextprotocol.io/docs/develop/connect-local-servers

## Cursor

File: `~/.cursor/mcp.json` for all projects, or `.cursor/mcp.json` in a project. Same `mcpServers` JSON as Claude Desktop. Cursor also accepts `${env:NAME}` in values.

Source: https://cursor.com/docs/mcp

## Windsurf

The Windsurf MCP page now redirects to Devin's documentation and describes this file as belonging to Cascade, the legacy agent: `~/.config/devin/mcp_config.json` (or `$XDG_CONFIG_HOME/devin/mcp_config.json`) on macOS and Linux, `%APPDATA%\devin\mcp_config.json` on Windows. Format is the same `mcpServers` JSON as above. An older `~/.codeium/windsurf/mcp_config.json` path exists in earlier docs; it was not confirmed here. The page says the newer Devin Local agent is configured through its CLI, which was not checked.

Source: https://docs.devin.ai/desktop/cascade/mcp

## Cline (VS Code extension)

Open the Cline panel, click the MCP Servers icon, open the Configure tab, and choose Configure MCP Servers. That opens the settings JSON. The documentation does not give the on-disk path for the extension (only `~/.cline/mcp.json` for the Cline CLI), so use the button. The format is the same `mcpServers` JSON; Cline also accepts `"disabled": false` and `"autoApprove": []`.

Source: https://docs.cline.bot/mcp/configuring-mcp-servers

## Continue

Put a file in `.continue/mcpServers/` at the workspace root. YAML:

```yaml
name: sourcedrecall
version: 0.0.1
schema: v1
mcpServers:
  - name: sourcedrecall
    type: stdio
    command: sourcedrecall
    env:
      SOURCEDRECALL_OWNER: Your Name
```

The documentation says JSON files in the Claude Desktop or Cursor format can also be dropped into that folder. MCP tools work only in Continue's agent mode. A global (user-level) location was not found on the page.

Source: https://docs.continue.dev/customize/deep-dives/mcp

## Zed

Zed calls MCP servers context servers. Add them in settings.json, or through Settings, AI, MCP Servers. The page does not state the settings.json path per OS; open it from within Zed (the "zed: open settings" command).

```json
{
  "context_servers": {
    "sourcedrecall": {
      "command": "sourcedrecall",
      "args": [],
      "env": { "SOURCEDRECALL_OWNER": "Your Name" }
    }
  }
}
```

Source: https://zed.dev/docs/ai/mcp

## Goose

File: `~/.config/goose/config.yaml` (the page names the macOS path and says other systems are similar). Extensions can also be added with `goose configure`.

```yaml
extensions:
  sourcedrecall:
    name: sourcedrecall
    type: stdio
    cmd: sourcedrecall
    args: []
    enabled: true
    envs: { "SOURCEDRECALL_OWNER": "Your Name" }
    timeout: 300
```

Source: https://block.github.io/goose/docs/getting-started/using-extensions

## VS Code (agent mode, Copilot)

Workspace file `.vscode/mcp.json`, or run "MCP: Open User Configuration" for the user-profile file. The top-level key is `servers`, not `mcpServers`. The `env` field for stdio servers is listed in the reference table; the guide's examples do not show one, so the snippet below follows the reference. The per-OS path of the user file is not given. VS Code also reads `.mcp.json` (key `mcpServers`) at the workspace root and `~/.copilot/mcp-config.json`.

```json
{
  "servers": {
    "sourcedrecall": {
      "type": "stdio",
      "command": "sourcedrecall",
      "env": { "SOURCEDRECALL_OWNER": "Your Name" }
    }
  }
}
```

Sources: https://code.visualstudio.com/docs/copilot/customization/mcp-servers and https://code.visualstudio.com/docs/copilot/reference/mcp-configuration

## Gemini CLI

File: `~/.gemini/settings.json` for the user, `.gemini/settings.json` in a project, plus a system file. Under `mcpServers`:

```json
{
  "mcpServers": {
    "sourcedrecall": {
      "command": "sourcedrecall",
      "env": { "SOURCEDRECALL_OWNER": "Your Name" }
    }
  }
}
```

Gemini CLI strips environment variables whose names match patterns such as `*TOKEN*`, `*SECRET*` and `*KEY*` unless they are declared in the server's `env` block. `SOURCEDRECALL_OWNER` is declared there. `gemini mcp add` and `gemini mcp list` manage entries from the command line.

Sources: https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/tools/mcp-server.md and https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/reference/configuration.md

## OpenAI Codex CLI

File: `~/.codex/config.toml`, or `.codex/config.toml` in a trusted project.

```toml
[mcp_servers.sourcedrecall]
command = "sourcedrecall"

[mcp_servers.sourcedrecall.env]
SOURCEDRECALL_OWNER = "Your Name"
```

`env_vars = ["NAME"]` forwards variables from your own environment instead.

Source: https://learn.chatgpt.com/docs/extend/mcp?surface=cli

## ChatGPT

No local stdio support was found. OpenAI's developer mode connects to remote MCP servers over SSE or streaming HTTP by URL. OpenAI's help page could not be fetched (HTTP 403) when this was written, so this rests on summaries of it and of the developer mode guide. A stdio server could only be used through a separate bridge that exposes it over HTTP, which this project does not provide and which would put your memory on a network endpoint.

Source: https://developers.openai.com/api/docs/guides/developer-mode

## Capturing conversations from Codex CLI and Gemini CLI

The memory only learns from what is ingested. `sourcedrecall-memory ingest [file]` takes JSON Lines of `{"role": "user"|"assistant", "content": "..."}`. Claude Code is covered by `sourcedrecall-hook`. For the other two CLIs there are two parts: where the transcript is, and what runs at the end of a session.

### Gemini CLI

Transcripts are in `~/.gemini/tmp/<project_hash>/chats/`, where the hash is derived from the project root. The documentation lists what is saved (prompts, replies, tool calls, token counts, thoughts) but not the file format.

The format below is read from the source of google-gemini/gemini-cli (`packages/core/src/services/chatRecordingService.ts`), not from the documentation, so it can change without notice. Current source writes `session-<timestamp>-<id>.jsonl`. The first lines carry session metadata (`sessionId`, `projectHash`, `startTime`, `lastUpdated`). Message lines have `type` of `user` or `gemini`, an `id`, and `content`, which is a string or a list of parts with `text`. Other lines edit earlier ones: `{"$rewindTo": id}` drops that message and everything after, `{"$patch": {"removeIds": [...]}}` removes messages, and `{"$set": {...}}` updates metadata. Older versions wrote a single `.json` file with a `messages` array of the same records.

Gemini CLI has a `SessionEnd` hook, defined under `hooks` in `settings.json`. It fires when the CLI exits or the session is cleared (`reason` is `exit`, `clear`, `logout`, `prompt_input_exit` or `other`). It is best effort: the CLI does not wait for it. The hook receives JSON on stdin with `session_id`, `transcript_path` (the session file), `cwd`, `hook_event_name` and `timestamp`. The exact nesting of the `hooks` entry in `settings.json` was not captured, so see the hooks documentation before writing one.

Import a session by hand:

```
sourcedrecall-import gemini ~/.gemini/tmp/<hash>/chats/session-....jsonl
```

The conversation id is the session id from the file, or the file name if there is none. Use `--id`, `--date` and `--scope` to override or add context. Thoughts, tool calls and tool results are not imported. To run it at session end, make a hook script read `transcript_path` from stdin and run that command.

Sources: https://geminicli.com/docs/cli/session-management/ and https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/hooks/reference.md and https://geminicli.com/docs/hooks/

### Codex CLI

Transcripts are rollout files under `~/.codex/sessions/YYYY/MM/DD/rollout-<timestamp>-<id>.jsonl`. This location and the JSONL form come from third-party articles and GitHub issues, not from OpenAI documentation, which does not describe the file. The same sources say the line layout changed around Codex 0.149 (user and assistant text moved from `event_msg` entries of type `user_message` and `agent_message` to an `item_completed` envelope). Because the format is undocumented and moving, `sourcedrecall-import codex` is not implemented; it exits with a message. `importers.codex_turns` carries a TODO.

Codex has hooks. Events include `SessionStart`, `SessionEnd`, `Stop`, `UserPromptSubmit` and others, configured in `~/.codex/hooks.json` or `config.toml`, or in the same files under `<repo>/.codex/`. Every hook gets JSON on stdin with `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `model` and `permission_mode`. `SessionEnd` runs when a conversation closes or after 30 minutes of inactivity, and its `reason` is currently always `other`. Hooks that are not managed need to be reviewed and trusted with `/hooks` first. The exact `hooks.json` layout was not captured.

Until an importer exists, convert a rollout to the JSON Lines shape yourself and pipe it to `sourcedrecall-memory ingest`.

Sources: https://learn.chatgpt.com/docs/hooks and https://github.com/openai/codex/issues/42345
