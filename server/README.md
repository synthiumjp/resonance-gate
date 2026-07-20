# rg-memory

A local MCP memory server, LLM-free, over `rg` — a vector-symbolic (VSA)
memory substrate. It stores explicit structured facts as
`(subject, relation, object)` triples and answers queries against them.

There is **no language model in the request path** — no mouth, no
extractor, no judge. The only model anywhere in the server is the
registry's MiniLM sentence-embedding **encoder**: a deterministic
string→vector map, non-generative, loaded lazily the first time a novel
string is written. It cannot generate text and it cannot hallucinate a
fact — this is a correctness property, not just a feature.

> Stores explicit structured facts you write. Does NOT extract facts from
> conversation (no LLM inside — nothing to hallucinate). Detects
> contradictory writes under synonymous keys (validated on synthetic pairs;
> real-world validation pending). Returns honest "no match" when nothing is
> stored. Surfaces conflicts rather than silently picking.

## The four tools

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
highlighted. Port is `RG_MEMORY_BROWSER_PORT` (`0` disables it); it binds
loopback only. Writes never happen from the browser — they only ever go
through the four MCP tools above, so provenance stays clean. This is a
trust feature: you can *see* what the memory holds, in human-readable
triples, unlike embedding-only competitors.

## Persistence

State is a local snapshot (`arrays.npz` + `state.json`) written after every
mutation, in `RG_MEMORY_STATE` (default `~/.rg-memory`). A restart fully
recovers memory from disk.

Everything is local: no network calls, no API keys, no telemetry. The
embedding model is used from the local Hugging Face cache only — the
server sets `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` by default.

## Install / run

The server is Python (`mcp`, `numpy`, `sentence-transformers`, `torch` —
see `pyproject.toml`). The `rg` substrate itself is a set of numpy-only
flat modules (`substrate/`, `gate/`, `encoder/`) loaded from the repo
checkout at runtime via `RG_ROOT` (default: the repo containing this
server). `mouth/` — the repo's language-model conversation layer — is
deliberately never imported by this server.

### (a) From the repo venv — simplest, works today

```bash
/ABS/PATH/TO/rg/.venv/bin/python -m rg_memory.mcp_server
```

with environment:

```
PYTHONPATH=/ABS/PATH/TO/rg/server
RG_ROOT=/ABS/PATH/TO/rg
```

### (b) uvx / pipx — distribution option

```bash
uvx --from /ABS/PATH/TO/rg/server rg-memory
```

or

```bash
pipx install /ABS/PATH/TO/rg/server
rg-memory
```

Either way, `RG_ROOT=/ABS/PATH/TO/rg` is **required** — even in an isolated
uvx/pipx environment, the server still reads the numpy-only substrate from
the repo on disk (v1 does not bundle it into the wheel).

Note: the MiniLM model (`sentence-transformers/all-MiniLM-L6-v2`) must be
present in the local Hugging Face cache before first use — the server runs
fully offline (`HF_HUB_OFFLINE=1`), so an uncached model means the first
novel write fails loudly rather than silently phoning home. Prime the cache
once (e.g. by loading `sentence-transformers/all-MiniLM-L6-v2` in a normal,
non-offline Python session) and every write and recall after that is local.

Substitute your actual absolute path for `/ABS/PATH/TO/rg` everywhere
above and below.

## MCP client config

### Claude Code

```bash
claude mcp add rg-memory /ABS/PATH/TO/rg/.venv/bin/python \
  -e PYTHONPATH=/ABS/PATH/TO/rg/server \
  -e RG_ROOT=/ABS/PATH/TO/rg \
  -- -m rg_memory.mcp_server
```

or as JSON (`.mcp.json` / `claude mcp add-json`):

```json
{
  "mcpServers": {
    "rg-memory": {
      "command": "/ABS/PATH/TO/rg/.venv/bin/python",
      "args": ["-m", "rg_memory.mcp_server"],
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
    "rg-memory": {
      "command": "/ABS/PATH/TO/rg/.venv/bin/python",
      "args": ["-m", "rg_memory.mcp_server"],
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
    "rg-memory": {
      "command": "/ABS/PATH/TO/rg/.venv/bin/python",
      "args": ["-m", "rg_memory.mcp_server"],
      "env": {
        "PYTHONPATH": "/ABS/PATH/TO/rg/server",
        "RG_ROOT": "/ABS/PATH/TO/rg"
      }
    }
  }
}
```

The uvx distribution option (b) works the same way in any of the above:
`"command": "uvx", "args": ["--from", "/ABS/PATH/TO/rg/server", "rg-memory"]`,
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
