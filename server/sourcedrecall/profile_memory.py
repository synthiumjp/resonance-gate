"""profile_memory: bridges the p2 profile/world memory (experiments/p2) into
this MCP server -- the dogfood-v1 READ + CORRECT slice. Live ingestion (turning
new conversations into the extraction cache) is not in scope here; this module
only ever REPLAYS an existing cache, so the request path stays LLM-free, same
guarantee as the rest of this server.

Five tools sit on top of experiments/p2's already-validated query contract
(memory_api.Memory): profile_recall, profile_context, profile_correct,
profile_status, profile_rehydrate. See mcp_server.py for the registered tool
wrappers.

REHYDRATION (the "virtual context window"): the fact graph built by Memory is
a page table -- corroborated, receipted, but deliberately compressed. The raw
export (conversations.json) is the backing store. A receipt's date +
conversation_id is a page-table entry; rehydrate() is the page fault that
pages the verbatim conversation slice back in from the backing store, on
demand, instead of the memory holding every transcript resident at all
times.

Env:
  RG_MEMORY_DIR   data dir containing conversations.json (+ profile_cache*.jsonl,
                  corrections.jsonl, owner_facts.jsonl). REQUIRED -- there is no
                  default that falls back to a real home path, so a forgetful
                  test run never touches a real user's data. Raises clearly the
                  first time any tool is called with it unset.
  RG_EXTRACT_V2 / RG_EXTRACT_V3 / RG_EXTRACT_V4
                  pass through unchanged to run_wire.build_facts's cache-file
                  selection (profile_cache_v2/_v3/_v4.jsonl vs the base cache).

Loading is a LAZY module-level singleton: the first tool call builds Memory
from the cache (can take tens of seconds on a big export) and keeps it in
process; reload() rebuilds it (also reachable via profile_status(reload=True)).
"""

import json
import os
import sys
import threading

# Packaging debt (v1): experiments/p2 is a script directory, not an installed
# package. Bridge it onto sys.path here, and only here, so the rest of the
# server never has to know p2 isn't packaged yet.
_P2_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "experiments", "p2")
if _P2_ROOT not in sys.path:
    sys.path.insert(0, _P2_ROOT)

from memory_api import Memory  # noqa: E402 -- after the sys.path bridge

_VALID_ACTIONS = ("deny", "confirm", "retype")
_SOURCE = "rg-p2-memory"

_lock = threading.RLock()
_state = {"mem": None, "audit_pass": None, "needs_reload": False,
          "uncached_turns": None, "transcripts": None}


class MemoryNotConfigured(RuntimeError):
    """RG_MEMORY_DIR is unset. Raised, not swallowed -- a misconfigured data
    dir is an operator error, distinct from an honest recall miss."""


def _data_dir():
    d = os.environ.get("RG_MEMORY_DIR")
    if not d:
        raise MemoryNotConfigured(
            "RG_MEMORY_DIR is not set -- point it at the p2 data dir "
            "(conversations.json + profile_cache*.jsonl + corrections.jsonl) "
            "before calling a profile_* tool.")
    return d


def _conversations_path():
    return os.path.join(_data_dir(), "conversations.json")


def _corrections_path():
    return os.path.join(_data_dir(), "corrections.jsonl")


def _build():
    """One cache-only build: facts -> WireGraph -> Memory. Mirrors
    Memory.load's body exactly, except it keeps the uncached-turn count
    (Memory.load discards it) so profile_status can surface it."""
    from run_wire import build_facts  # local: needs the sys.path bridge above
    from wire import WireGraph
    facts, prov, n_convs, titles, n_uncached = build_facts(
        _conversations_path(), min_mentions=2)
    g = WireGraph.from_facts(facts, n_convs=n_convs, provisional=prov)
    return Memory(g, titles), n_uncached


def _reload_locked():
    mem, n_uncached = _build()
    _state["mem"] = mem
    _state["uncached_turns"] = n_uncached
    _state["audit_pass"] = None      # stale after a rebuild; recompute lazily
    _state["needs_reload"] = False
    _state["transcripts"] = None     # stale backing-store index; rebuilt lazily
    return mem


def reload():
    """Rebuild Memory from the cache + corrections.jsonl on disk (picks up a
    retype correction, which a live apply_corrections() cannot do at the fact
    level). Also reachable via profile_status(reload=True)."""
    with _lock:
        return _reload_locked()


def _ensure_loaded():
    with _lock:
        if _state["mem"] is None:
            _reload_locked()
        return _state["mem"]


# --------------------------------------------------------------- the tools

def profile_recall(query):
    mem = _ensure_loaded()
    with _lock:
        out = mem.recall(query)
    out["source"] = _SOURCE
    return out


def profile_context(query=None, max_facts=15):
    mem = _ensure_loaded()
    with _lock:
        block = mem.context_block(query, max_facts)
    return {"block": block}


def profile_correct(action, attribute, value, new_attribute=None, exact=False):
    """Append one correction to corrections.jsonl (owner-authored ground
    truth, per wire.correct_facts). deny/confirm apply immediately to the live
    graph (Memory.apply_corrections is node-level -- retype is not, it needs a
    fact-level rebuild, see wire.correct_facts); retype only flags
    needs_reload=True and is realized on the next reload()."""
    if action not in _VALID_ACTIONS:
        return {"written": None, "applied": None,
                "error": f"action must be one of {list(_VALID_ACTIONS)}"}
    if action == "retype" and not new_attribute:
        return {"written": None, "applied": None,
                "error": "retype requires new_attribute"}

    correction = {"action": action, "attribute": attribute, "value": value}
    if exact:
        correction["exact"] = True
    if action == "retype":
        correction["new_attribute"] = new_attribute

    with _lock:
        data_dir = _data_dir()
        os.makedirs(data_dir, exist_ok=True)
        path = _corrections_path()
        with open(path, "a") as f:
            f.write(json.dumps(correction) + "\n")

        if action == "retype":
            _state["needs_reload"] = True
            return {"written": correction, "applied": "on-reload",
                    "needs_reload": True}

        mem = _ensure_loaded()
        log = mem.apply_corrections([correction])
        _state["audit_pass"] = None   # graph just changed; recompute lazily
        return {"written": correction, "applied": "live", "log": log}


def profile_dynamics():
    """How this memory is aging (entry 147): receipt counts, span, how many
    facts are actively reinforced vs faded, and the date the store is read
    as-of. Decay affects WEIGHT only -- no fact is removed, so a faded fact is
    still recallable and still carries its receipts."""
    mem = _ensure_loaded()
    import receipts as RC
    with _lock:
        nodes = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
        return {"dynamics": RC.dynamics(nodes), "source": _SOURCE}


def profile_quarantine():
    """Writes the LEARNED WRITE POLICY blocked at ingest (entry 140), with the
    rule that blocked each. Reversible by design: delete or amend the
    correction in corrections.jsonl and reload."""
    _ensure_loaded()
    import run_wire
    import write_rules as WR
    rules = WR.load(_corrections_path())
    return {"quarantined": run_wire.quarantine(),
            "rules": {"deny": len(rules["deny"]), "retype": len(rules["retype"]),
                      "from_corrections": rules["n_corrections"]},
            "source": _SOURCE}


def profile_conflicts():
    """Open slot conflicts from the live Memory (see memory_api.conflicts)."""
    mem = _ensure_loaded()
    with _lock:
        return {"conflicts": mem.conflicts(), "source": _SOURCE}


def profile_status(reload=False):
    with _lock:
        if reload or _state["mem"] is None:
            _reload_locked()
        mem = _state["mem"]
        if _state["audit_pass"] is None:
            _state["audit_pass"] = bool(mem.g.audit()["pass"])
        return {"loaded": mem is not None,
                "asserted": len(mem.g.nodes),
                "provisional": len(mem.g.provisional),
                "edges": len(mem.g.edges),
                "audit_pass": _state["audit_pass"],
                "needs_reload": _state["needs_reload"],
                "uncached_turns": _state["uncached_turns"],
                "data_dir": _data_dir()}


def _build_transcript_index_locked():
    """Parse conversations.json ONCE, in full, into an in-process
    {uuid: {"title", "date", "turns": [{"role", "text"}]}} dict.

    PERSISTENCE DEBT (dogfood-v1, deliberate): this is a full parse of the
    backing store -- on the real export that's on the order of half a
    gigabyte of JSON -- and every transcript it produces is held resident in
    RAM for the remaining lifetime of the process. There is no eviction, no
    on-disk index, no streaming re-read per call. That's acceptable for a
    single-owner dogfood server where rehydrate() is called occasionally
    against one export already fully loaded into a Memory graph in the same
    process; it is NOT acceptable as the design for a multi-tenant or
    memory-constrained deployment, where this needs to become a real index
    (sqlite/offsets file) built once and queried, not parsed-and-held. Only
    reload() (a fresh RG_MEMORY_DIR or an explicit rebuild) evicts this.
    """
    convs = json.load(open(_conversations_path()))
    index = {}
    for c in convs:
        uuid = c.get("uuid", "")
        if not uuid:
            continue
        turns = []
        for m in (c.get("chat_messages") or []):
            role = (m.get("sender") or "").lower()
            if role not in ("human", "assistant"):
                continue
            txt = m.get("text") or m.get("content") or ""
            if isinstance(txt, list):
                # same block-list handling as run_profile_full.load_stream_and_titles
                txt = " ".join(str(x.get("text", "")) if isinstance(x, dict)
                               else str(x) for x in txt)
            txt = txt.strip()
            if txt:
                turns.append({"role": role, "text": txt})
        index[uuid] = {"title": c.get("name", "") or "(untitled)",
                       "date": c.get("created_at", "")[:10],
                       "turns": turns}
    return index


def _ensure_transcripts_locked():
    if _state["transcripts"] is None:
        _state["transcripts"] = _build_transcript_index_locked()
    return _state["transcripts"]


def rehydrate(conversation_id, max_turns=40, include_assistant=True):
    """The page-fault half of the virtual context window: given a receipt's
    conversation_id (as now returned by every fact's receipts, see
    memory_api.Memory._fact), return the verbatim turns of that conversation
    from the backing store (conversations.json) -- not a paraphrase, not a
    summary, not a reconstruction from the fact graph.

    Non-hallucination contract at this layer: an unknown conversation_id is
    NEVER guessed at or fuzzy-matched to the nearest title -- it is reported
    as not found, exactly like an honest recall abstain one layer up.

    max_turns caps how many turns come back (truncated=True if the
    conversation has more); include_assistant=False restricts to the human's
    own turns. Each turn's text is capped at 2000 chars (marked with a
    trailing "..." when cut) so one huge turn can't blow the response.
    """
    with _lock:
        index = _ensure_transcripts_locked()
        conv = index.get(conversation_id)
        if conv is None:
            return {"found": False,
                    "error": "no such conversation in the backing store"}
        turns = conv["turns"] if include_assistant else [
            t for t in conv["turns"] if t["role"] == "human"]
        n_total = len(turns)
        out_turns = []
        for t in turns[:max_turns]:
            text = t["text"]
            if len(text) > 2000:
                text = text[:2000] + "..."
            out_turns.append({"role": t["role"], "text": text})
        return {"found": True, "conversation_id": conversation_id,
                "title": conv["title"], "date": conv["date"],
                "n_turns_total": n_total, "turns": out_turns,
                "truncated": n_total > max_turns}
