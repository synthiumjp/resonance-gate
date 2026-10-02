# sourcedrecall

A small, local memory for AI agents. It listens to your conversations, keeps
what **you** said -- in your own words, with when you said it -- and gives
your agent a short, honest briefing: what it knows, what has changed, and
that anything else is unknown.

- **Local.** Runs on your machine over MCP (Claude Code, Claude Desktop, any
  MCP client). Nothing leaves it.
- **Nothing is generated.** Facts are read out of your sentences by a
  deterministic grammar parser, never written by a language model, so the
  memory cannot invent something you did not say. Every fact keeps the
  sentence it came from.
- **Honest.** Ask about something you never mentioned and it says so. Change
  your mind and the old fact is marked *no longer true*.

## Quick start

```bash
git clone <this repo> rg && cd rg
python3 -m venv .venv && . .venv/bin/activate
# CPU torch first: otherwise pip pulls ~4 GB of CUDA wheels this never uses
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ./server
```

Use `-e` (editable): the server loads its memory code from this checkout.
Then download the models, once:

```bash
sourcedrecall-setup
```

That fetches the English parser (Stanza, ~320 MB) and four small
non-generative models (~600 MB, cached under `~/.cache/huggingface`) and
reports where each went. It is the only step that touches the network: the
server itself runs fully offline.

Add it to your MCP client, e.g. `.mcp.json` for Claude Code or
`claude_desktop_config.json` for Claude Desktop:

```json
{
  "mcpServers": {
    "sourcedrecall": {
      "command": "/absolute/path/to/rg/.venv/bin/sourcedrecall",
      "env": { "SOURCEDRECALL_OWNER": "Your Name" }
    }
  }
}
```

`SOURCEDRECALL_OWNER` is whose memory this is; facts are written about that
person. Memory lives in `~/.sourcedrecall/conversations` (set
`RG_MEMORY_DIR` to move it).

## The tools you will use

| tool | what it does |
|---|---|
| `profile_ingest(turns, owner_name)` | store one conversation: `turns` is `[{"role": "user"\|"assistant", "content": "..."}]`. Only what the **user** asserts becomes a fact; questions, hypotheticals, hedges and other people's opinions do not. |
| `profile_context(query=None)` | the briefing to put in your agent's prompt -- everything, or just what bears on `query` |
| `profile_recall(query)` | look one thing up; returns the answering facts with their quotes and dates, or an honest "never seen" |
| `profile_correct(action, attribute, value)` | `deny` a fact that is wrong, `confirm` one that is right |

Your agent has to call `profile_ingest` to remember a conversation -- ask it
to at the end of a chat, or wire it into a hook.

What the agent receives from `profile_context`:

```
[MEMORY: what the user has told you]
- Dana Cole works as a nurse at St Vincent's  ["I work as a nurse at St Vincent's and I live in Fitzroy." · 2026-10-02]
- Dana Cole is allergic to penicillin  ["I'm allergic to penicillin, which matters at work." · 2026-10-02]
- (no longer true) Dana Cole drinks coffee  ["I drink a lot of coffee." · 2026-09-01]
[MEMORY RULES] Each line is something the user told you: a short summary, then their exact words in quotes, and when. Lines marked (no longer true) were replaced by something they said later. Anything about the user not listed here is UNKNOWN: say you don't know rather than guessing.
```

## What is (and is not) inside

**No generative model is in the request path** -- nothing in this server can
write a sentence, so nothing in it can invent a fact. Three small
non-generative models score text that is already stored:

| model | used by | what it does |
|---|---|---|
| `bge-small` + `ms-marco-MiniLM` cross-encoder | `profile_recall`, `profile_context` | ranks stored facts against a question |
| `nli-deberta-v3-xsmall` | `profile_conflicts`, `profile_context` | decides whether two stored values contradict |
| MiniLM sentence encoder | the explicit-triples tools below | string -> vector |

`RG_PROFILE_V3=0` drops the retrieval pair (falls back to token overlap);
`RG_NLI=0` drops the NLI model; `RG_PREWARM=0` stops the server loading them
in the background at startup.

Built on the **Resonance Gate** research substrate, a pre-registered study:
[OSF 95e2q](https://osf.io/95e2q/).

---

## Advanced: explicit triples (four more tools)

Separately from conversation memory, the server can store facts you hand it
already structured, as `(subject, relation, object)` triples. These four
tools do not read conversations and do not share storage with the
`profile_*` tools (they live in `SOURCEDRECALL_STATE`, default
`~/.sourcedrecall`).

### The four triple tools

### `remember(subject, relation, object, source="caller-stated")`

Store one explicit structured triple. There is no extraction — the caller
passes the already-structured fact. The write is echo-checked (read back
through the gate before being accepted); a bad write is rejected, not
silently kept.

`source` is provenance, one of `caller-stated` (default), `user-stated`,
`agent-inferred`, `tool-derived`.

Returns:

```json
{"stored": true, "record_id": "r0", "echo_ok": true}
```

### `recall(query, top_k=10)`

Look up stored facts about `query`, resolved as a subject/entity.

Returns:

```json
{
  "resolved": true,
  "facts": [
    {"subject": "...", "relation": "...", "object": "...",
     "source": "...", "record_id": "r0",
     "confidence": {"b": 0.9, "d": 0.0, "u": 0.1}}
  ],
  "conflict": false
}
```

If nothing resolves, the response is an honest empty:
`{"resolved": false, "facts": [], "conflict": false}` — never a fabricated
guess. If contradictory facts are stored under synonymous relation keys
(e.g. "lives in" vs "resides in"), `conflict: true` and **both** facts are
returned, plus an advisory `resolution_hint`. The server does not choose
between them.

### `update(subject, relation, object, source="caller-stated")`

Explicitly correct a fact. Writes the new triple and supersedes prior
active records for the subject under the same or a synonymous relation
(tombstoned via the supersedes-chain; the audit trail is retained, not
erased). This is the **only** path that resolves a conflict by picking a
side — because the caller explicitly asked it to. A passive collision
surfaced by `recall` is never resolved this way on its own.

Returns:

```json
{"updated": true, "new_record_id": "r2", "superseded": ["r0", "r1"]}
```

### `forget(subject, relation=None, object=None)`

Delete stored facts, subtract-and-tombstone (stays deleted).

- `subject` only: forget everything about the subject.
- `subject` + `relation`: forget that relation class (and its synonyms).
- `subject` + `relation` + `object`: forget that exact record.

Returns:

```json
{"forgotten": ["r0"]}
```

### Confidence `{b, d, u}`

Every fact in `recall` carries the gate's opinion: `b` = belief, `d` =
disbelief/ambiguity, `u` = uncertainty/ignorance — they sum to 1. High `d`
signals a conflict; high `u` signals "not resolved".

## Memory browser (read-only)

A read-only page at **http://127.0.0.1:7071** lists every stored record —
subject, relation, object, source, confidence — with active conflicts
highlighted. Port is `SOURCEDRECALL_BROWSER_PORT` (`0` disables it); it binds
loopback only. Writes never happen from the browser — they only ever go
through the four MCP tools above, so provenance stays clean. This is a
trust feature: you can *see* what the memory holds, in human-readable
triples, unlike embedding-only competitors.

## `profile_ingest` (deterministic extraction, no LLM)

`profile_ingest(turns, conversation_id=None, title=None, owner_name=None)` is
the one write path in the `profile_*` bridge (see `sourcedrecall/profile_memory.py`)
that turns raw conversation into new facts. The extractor is **rgx** — a
grammar-rule parser over a dependency parse — never a language model:

- **Never invents content.** A fact is either grounded in the turn's own
  words or it is not emitted. There is no sampling, no prompt, no paraphrase.
- **Tags hearsay.** An assistant clause that reports a claim *about* the
  user ("I remember you mentioning...") is extracted and receipted, but
  filed under its own `hearsay` tier — never asserted or volunteered as the
  user's own fact (see `profile_recall`'s `"hearsay"` key).
- **Every fact carries receipts.** Session, turn index, role, and (once
  wired) conversation id + date — the same provenance contract every other
  fact in this store carries; ingestion doesn't relax it.
- Re-ingesting a conversation is a safe no-op for turns already seen
  (`skipped_cached` counts them, `model_calls` is always `0` — there is no
  model call anywhere in this path, cached or fresh).

## Persistence

State is a local snapshot (`arrays.npz` + `state.json`) written after every
mutation, in `SOURCEDRECALL_STATE` (default `~/.sourcedrecall`). A restart fully
recovers memory from disk.

Everything is local: no network calls, no API keys, no telemetry. The
embedding model is used from the local Hugging Face cache only — the
server sets `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` by default.

## Install / run (older notes)

The **Quick start** at the top supersedes this section; it is kept for the
running-from-a-research-venv details.

The server is Python (`mcp`, `numpy`, `sentence-transformers`, `torch` —
see `pyproject.toml`). The `rg` substrate itself is a set of numpy-only
flat modules (`substrate/`, `gate/`, `encoder/`) loaded from the repo
checkout at runtime via `RG_ROOT` (default: the repo containing this
server). `mouth/` — the repo's language-model conversation layer — is
deliberately never imported by this server.

### (a) From the repo venv — simplest, works today

```bash
/ABS/PATH/TO/rg/.venv/bin/python -m sourcedrecall.mcp_server
```

with environment:

```
PYTHONPATH=/ABS/PATH/TO/rg/server
RG_ROOT=/ABS/PATH/TO/rg
```

### (b) uvx / pipx — distribution option

```bash
uvx --from /ABS/PATH/TO/rg/server sourcedrecall
```

or

```bash
pipx install /ABS/PATH/TO/rg/server
sourcedrecall
```

Either way, `RG_ROOT=/ABS/PATH/TO/rg` is **required** — even in an isolated
uvx/pipx environment, the server still reads the numpy-only substrate from
the repo on disk (v1 does not bundle it into the wheel).

Note: every model must be present locally before first use -- the server
runs fully offline (`HF_HUB_OFFLINE=1`). `sourcedrecall-setup` installs them
all.

Substitute your actual absolute path for `/ABS/PATH/TO/rg` everywhere
above and below.

## MCP client config

### Claude Code

```bash
claude mcp add sourcedrecall /ABS/PATH/TO/rg/.venv/bin/python \
  -e PYTHONPATH=/ABS/PATH/TO/rg/server \
  -e RG_ROOT=/ABS/PATH/TO/rg \
  -- -m sourcedrecall.mcp_server
```

or as JSON (`.mcp.json` / `claude mcp add-json`):

```json
{
  "mcpServers": {
    "sourcedrecall": {
      "command": "/ABS/PATH/TO/rg/.venv/bin/python",
      "args": ["-m", "sourcedrecall.mcp_server"],
      "env": {
        "PYTHONPATH": "/ABS/PATH/TO/rg/server",
        "RG_ROOT": "/ABS/PATH/TO/rg"
      }
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "sourcedrecall": {
      "command": "/ABS/PATH/TO/rg/.venv/bin/python",
      "args": ["-m", "sourcedrecall.mcp_server"],
      "env": {
        "PYTHONPATH": "/ABS/PATH/TO/rg/server",
        "RG_ROOT": "/ABS/PATH/TO/rg"
      }
    }
  }
}
```

### Cursor (`~/.cursor/mcp.json` or project `.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "sourcedrecall": {
      "command": "/ABS/PATH/TO/rg/.venv/bin/python",
      "args": ["-m", "sourcedrecall.mcp_server"],
      "env": {
        "PYTHONPATH": "/ABS/PATH/TO/rg/server",
        "RG_ROOT": "/ABS/PATH/TO/rg"
      }
    }
  }
}
```

The uvx distribution option (b) works the same way in any of the above:
`"command": "uvx", "args": ["--from", "/ABS/PATH/TO/rg/server", "sourcedrecall"]`,
with `"env": {"RG_ROOT": "/ABS/PATH/TO/rg"}`.

## Quickstart: example calls

**1. `remember` a fact**

```json
// call
{"subject": "Maria Garcia", "relation": "works at", "object": "Acme Labs",
 "source": "user-stated"}
// result
{"stored": true, "record_id": "r0", "echo_ok": true}
```

**2. `recall` — a hit**

```json
// call
{"query": "Maria Garcia"}
// result
{"resolved": true,
 "facts": [{"subject": "Maria Garcia", "relation": "works at",
            "object": "Acme Labs", "source": "user-stated",
            "record_id": "r0", "confidence": {"b": 0.92, "d": 0.0, "u": 0.08}}],
 "conflict": false}
```

**3. `recall` — an honest miss**

```json
// call
{"query": "Someone Nobody Ever Mentioned"}
// result
{"resolved": false, "facts": [], "conflict": false}
```

**4. A near-synonym collision**

```json
// remember("Maria Garcia", "lives in", "Lisbon")   -> record r1
// remember("Maria Garcia", "resides in", "Boston")  -> record r2
// call
{"query": "Maria Garcia"}
// result
{"resolved": true,
 "facts": [
   {"subject": "Maria Garcia", "relation": "lives in", "object": "Lisbon",
    "source": "caller-stated", "record_id": "r1",
    "confidence": {"b": 0.4, "d": 0.5, "u": 0.1}},
   {"subject": "Maria Garcia", "relation": "resides in", "object": "Boston",
    "source": "caller-stated", "record_id": "r2",
    "confidence": {"b": 0.4, "d": 0.5, "u": 0.1}}
 ],
 "conflict": true,
 "resolution_hint": {"by_recency": "r2", "by_resolution": "r1"}}
```

`"lives in"` and `"resides in"` are in the same relation-synonym class, so
this is caught even though the phrasing differs. `resolution_hint` is
advisory: `by_recency` points at the most-recently-written record,
`by_resolution` at the one the gate leans toward — the server surfaces
both and picks neither; only an explicit `update` picks.

**5. `update` — explicit correction (supersede)**

```json
// call
{"subject": "Maria Garcia", "relation": "lives in", "object": "Boston",
 "source": "user-stated"}
// result
{"updated": true, "new_record_id": "r3", "superseded": ["r1", "r2"]}
```

Both prior records (the `lives in`/Lisbon and the synonymous `resides
in`/Boston one) are tombstoned; a fresh `recall("Maria Garcia")` now
resolves cleanly to Boston with `conflict: false`.

**6. `forget`**

```json
// call
{"subject": "Tom Baker"}
// result
{"forgotten": ["r4", "r5"]}
```

## Limitations / deferred

- **No fact extraction from text.** You pass structured triples; the
  server does not read prose and infer facts. Extraction is a possible
  opt-in v2, not present here.
- **Fixed relation-synonym table.** Exactly two classes today:
  `works at` / `is employed by`, and `lives in` / `resides in`. Relations
  outside these classes are treated as distinct keys, even if they mean
  the same thing in English.
- **Near-duplicate subject surface forms are not detected.** "Maria" vs
  "Maria's" is not caught by the collision detector — that axis is
  deferred to write-time canonicalization. See `docs/COLLISION_FIX.md` in
  the repo root.
- **Collision detection is validated on synthetic pairs only** — real-world
  validation is pending. The server never claims it "never contradicts
  itself"; the disciplined claim is that it detects and surfaces
  contradictory writes under synonymous keys.
- **No standalone wheel bundling the substrate yet.** v1 reads
  `substrate/`, `gate/`, `encoder/` from the repo checkout via `RG_ROOT`
  at runtime; a self-contained package is a future packaging item.
