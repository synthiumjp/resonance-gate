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

To store Cursor agent conversations automatically as well, add the hooks described under "Capturing conversations automatically" below.

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

## Capturing conversations automatically

The memory only learns from what is ingested. Claude Code is covered by the plugin hooks. This section covers the other three agents that can run a program when a session starts or ends. For each one it says what the hook receives, where the format was checked, and what the hook stores. The commands are `sourcedrecall-hook` (hooks) and `sourcedrecall-import` (by hand). `sourcedrecall-memory ingest [file]` takes JSON Lines of `{"role": "user"|"assistant", "content": "..."}` for anything else.

All three hooks were written against the documentation or source named below and tested with made-up inputs shaped from them. They have not been run inside the live applications, so check the first stored session with `sourcedrecall-memory recall` or the `MEMORY.md` file.

Use the absolute path of `sourcedrecall-hook` in the `command` fields if it is not on the PATH that the agent uses.

### Codex CLI

What Codex provides. Codex has lifecycle hooks, configured in `~/.codex/hooks.json` or `[hooks]` in `~/.codex/config.toml`, or the same files under `<repo>/.codex/`. Events include `SessionStart`, `SessionEnd`, `Stop`, `UserPromptSubmit` and others. Every command hook receives JSON on stdin with `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `model` and `permission_mode`. For `SessionEnd`, `transcript_path` is the path of the rollout file (it can be null), the file is flushed before the hook runs, `reason` is always `other`, and the matcher value is `other`. `SessionEnd` runs when a root session shuts down and is not run for sub-agents. Its timeout defaults to 1 second and is capped at 3, so the hook only starts a background process. `SessionStart` accepts `hookSpecificOutput.additionalContext` and `systemMessage` in its output. Hooks that are not managed must be reviewed with `/hooks` before they run.

Config:

```json
{
  "hooks": {
    "SessionStart": [{"matcher": "startup|resume|clear",
      "hooks": [{"type": "command", "timeout": 30,
        "command": "sourcedrecall-hook session-start --agent codex --owner 'Your Name'"}]}],
    "SessionEnd": [{"hooks": [{"type": "command", "timeout": 3,
        "command": "sourcedrecall-hook session-end --agent codex --owner 'Your Name'"}]}]
  }
}
```

Stored: the text you typed and the assistant's messages. Not stored: reasoning, tool calls and their output, and the user-role messages Codex adds itself (AGENTS.md instructions, environment context, shell command echoes, skill and hook text, compaction summaries). If the process is killed before it shuts down, `SessionEnd` does not run; import that rollout by hand.

By hand:

```
sourcedrecall-import codex ~/.codex/sessions/2026/10/05/rollout-<timestamp>-<id>.jsonl
```

The conversation id is `codex:<thread id>` (the hook uses the same one, so a session stored both ways is stored once). `--id`, `--date` and `--scope` override. Rollouts compressed to `.jsonl.zst` need Python 3.14 or the `zstandard` package, or decompress them first.

Rollout format, from the open-source repository openai/codex (Rust, `codex-rs`), at main commit 7f892275e3 (2026-10-04; latest release tag then `rust-v0.160.0`). OpenAI's documentation does not describe it, so it can change. The same rules are in the docstring of `server/sourcedrecall/importers.py`.

- Files are `~/.codex/sessions/YYYY/MM/DD/rollout-<timestamp>-<thread id>.jsonl`. Before 2025-07-17 they were directly in `~/.codex/sessions/` (commit fcbcc40f51).
- Layout A, from 2025-05-07 (commit 42617f8726, `codex-rs/core/src/rollout.rs`) to `rust-v0.32.0`: line 1 is a header `{"id", "timestamp", "instructions"}`; every later line is a raw `ResponseItem` such as `{"type": "message", "role": "user", "content": [{"type": "input_text", "text": ...}]}`, plus `{"record_type": "state", ...}` lines.
- Layout B, from `rust-v0.33.0`: each line is `{"timestamp", "type", "payload"}` with `type` one of `session_meta`, `response_item`, `event_msg`, `compacted`, `turn_context` and later additions. `RolloutLine` and `RolloutItem` are in `codex-rs/protocol/src/protocol.rs` at that tag and in `codex-rs/history/src/lib.rs` and `rollout_payload.rs` now. A `response_item` payload is the same `ResponseItem` as in layout A (`codex-rs/protocol/src/models.rs`).
- `codex-rs/rollout/src/policy.rs`: `ResponseItem::Message` is written in every mode; the `event_msg` copies (`user_message`, `agent_message`) only in legacy history mode. The importer reads the `response_item` messages.
- Injected user-role text is recognised by `codex-rs/core/src/context/contextual_user_message.rs` and the fragment definitions beside it; the importer applies the same patterns.
- An `event_msg` of type `thread_rolled_back` with `num_turns` removes the last turns (`core/src/context_manager/history.rs`); the importer does the same.

Codex also has an older `notify` setting that runs a program after each turn with a JSON argument holding `thread-id`, `cwd`, `input-messages` and `last-assistant-message`. It does not carry the rollout path, so the hooks above are the way to wire this up.

Sources: https://learn.chatgpt.com/docs/hooks, `codex-rs/hooks/schema/generated/*.json`, `codex-rs/hooks/src/events/session_end.rs`, `codex-rs/hooks/src/legacy_notify.rs`, `codex-rs/config/src/hook_config.rs`, all in https://github.com/openai/codex.

### Gemini CLI

What Gemini CLI provides. Hooks are defined under `hooks` in `~/.gemini/settings.json` or `.gemini/settings.json`. Each event holds a list of `{"matcher"?, "hooks": [{"type": "command", "command", "name"?, "timeout"? (milliseconds, default 60000)}]}`. For `SessionStart` and `SessionEnd` the matcher is compared as an exact string with the trigger (`startup`, `resume`, `clear`; `exit`, `clear`, `logout`, `prompt_input_exit`, `other`), so leave it out to match all of them. Every hook receives JSON on stdin with `session_id`, `transcript_path`, `cwd`, `hook_event_name` and `timestamp`. `transcript_path` is the chat recording file (`getConversationFilePath()` in `packages/core/src/hooks/hookEventHandler.ts`), and is an empty string when there is no recording. `SessionEnd` fires when the CLI exits or on `/clear`; the CLI does not wait for it. `SessionStart` accepts `hookSpecificOutput.additionalContext` and `systemMessage`. Hooks are on unless `hooksConfig.enabled` is false. The hooks guide warns that project-level hooks from an untrusted repository are risky and that a changed hook is treated as new.

Config:

```json
{
  "hooks": {
    "SessionStart": [{"hooks": [{"name": "sourcedrecall-start", "type": "command",
        "timeout": 30000,
        "command": "sourcedrecall-hook session-start --agent gemini --owner 'Your Name'"}]}],
    "SessionEnd": [{"hooks": [{"name": "sourcedrecall-end", "type": "command",
        "timeout": 10000,
        "command": "sourcedrecall-hook session-end --agent gemini --owner 'Your Name'"}]}]
  }
}
```

Stored: prompts and replies. Not stored: thoughts, tool calls and tool results.

By hand:

```
sourcedrecall-import gemini ~/.gemini/tmp/<project_hash>/chats/session-....jsonl
```

The conversation id is the session id from the file, or the file name if there is none (the hook uses the same). `--id`, `--date` and `--scope` override.

Transcript format, read from the source of google-gemini/gemini-cli (`packages/core/src/services/chatRecordingService.ts`, checked at commit fb972b2f87, 2026-10-02), not from the documentation, so it can change. Current source writes `session-<timestamp>-<id>.jsonl`. The first lines carry session metadata (`sessionId`, `projectHash`, `startTime`, `lastUpdated`). Message lines have `type` of `user` or `gemini`, an `id`, a `timestamp` and `content`, which is a string or a list of parts with `text` (parts marked `thought` are skipped). Other lines edit earlier ones: `{"$rewindTo": id}` drops that message and everything after, `{"$patch": {"removeIds": [...]}}` removes messages, and `{"$set": {...}}` updates metadata. Older versions wrote a single `.json` file with a `messages` array of the same records.

Sources: https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/hooks/reference.md, `docs/hooks/index.md`, `docs/reference/configuration.md` (`hooksConfig`), `packages/core/src/hooks/hookPlanner.ts` and `hookEventHandler.ts` in https://github.com/google-gemini/gemini-cli.

### Cursor

What Cursor provides. Cursor's hooks (https://cursor.com/docs/hooks) are configured in `~/.cursor/hooks.json` or `<project>/.cursor/hooks.json` as `{"version": 1, "hooks": {"<event>": [{"command": "..."}]}}`. Every event carries `conversation_id`, `generation_id`, `model`, `hook_event_name`, `workspace_roots` and `transcript_path` (a path, or null when transcripts are off). The events used here:

- `beforeSubmitPrompt`: `prompt` (the text the user typed) and `attachments`. It must answer `{"continue": true}` or the prompt is not sent.
- `afterAgentResponse`: `text`, the assistant's message.
- `stop`: `status` (`completed`, `aborted`, `error`), when the agent loop ends.
- `sessionStart`: may answer `{"additional_context": "..."}`; fire-and-forget. It has no field for a message to the user.
- `sessionEnd`: `reason` and `duration_ms`; fire-and-forget.

Cursor does not document the format of the transcript file or where chat history is kept, so there is no importer for either, and `sourcedrecall-import` has no `cursor` mode. The hook uses the documented prompt and response texts instead. It appends each to `~/.sourcedrecall/cursor-spool/<conversation_id>.jsonl`, stores the conversation at each `stop`, and stores it again and deletes the file at `sessionEnd`. Storing again only adds turns not already stored. A crash of the hook never blocks a prompt: it answers `{"continue": true}` whatever happens.

Config (the same command for every event; it tells them apart by `hook_event_name`):

```json
{
  "version": 1,
  "hooks": {
    "sessionStart":       [{"command": "sourcedrecall-hook cursor --owner 'Your Name'"}],
    "beforeSubmitPrompt": [{"command": "sourcedrecall-hook cursor --owner 'Your Name'"}],
    "afterAgentResponse": [{"command": "sourcedrecall-hook cursor --owner 'Your Name'"}],
    "stop":               [{"command": "sourcedrecall-hook cursor --owner 'Your Name'"}],
    "sessionEnd":         [{"command": "sourcedrecall-hook cursor --owner 'Your Name'"}]
  }
}
```

Limits: only prompts and replies that passed through these hooks are stored, so conversations from before the hooks were installed are not. The "saved N new things" line that Claude Code shows is not available, so the session-start summary has no notice and nothing is marked as reported. Hooks in `~/.cursor/hooks.json` do not run in Cursor's cloud agents; project hooks do, but `sessionStart` and `sessionEnd` do not, and `stop` still stores the conversation. Use the MCP setup above for tool access to the memory in all cases.

Source: https://cursor.com/docs/hooks (the Reference section; the markdown version is at https://cursor.com/docs/hooks.md).
