"""profile_memory: bridges the p2 profile/world memory (experiments/p2) into
this MCP server -- the dogfood-v1 READ + CORRECT + INGEST slice. profile_ingest
turns a conversation into new extraction-cache lines using rgx (the
deterministic parser) and ONLY rgx -- NO language model anywhere in this
module. Every other tool here only ever REPLAYS the cache Memory.load builds
from, so the request/ingest path stays LLM-free end to end, same guarantee as
the rest of this server.

NINE tools sit on top of experiments/p2's already-validated query contract
(memory_api.Memory) plus the rgx cache writer (rgx.facts): profile_recall,
profile_context, profile_correct, profile_status, profile_rehydrate,
profile_ingest, profile_dynamics, profile_quarantine, profile_conflicts.
(e277: this said SIX for as long as there have been nine -- the last three
were added and never propagated into any of the three places that count
them.) See mcp_server.py for the registered tool wrappers.

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
  RG_EXTRACT_V2 / RG_EXTRACT_V3 / RG_EXTRACT_V4 / RG_EXTRACT_V5
                  pass through unchanged to run_wire.build_facts's cache-file
                  selection (profile_cache_v2/_v3/_v4/_v5.jsonl vs the base
                  cache) -- profile_ingest writes to the SAME cache file, via
                  the same suffix rule, so what it writes is what the next
                  reload reads.
  SOURCEDRECALL_OWNER
                  fallback owner_name for profile_ingest when the tool call
                  doesn't pass one and no owner is otherwise discoverable
                  (see profile_ingest's docstring for the full chain).

Loading is a LAZY module-level singleton: the first tool call builds Memory
from the cache (can take tens of seconds on a big export) and keeps it in
process; reload() rebuilds it (also reachable via profile_status(reload=True)).
"""

import datetime
import json
import os
import sys
import threading
import uuid as _uuidlib

# Packaging debt (v1): experiments/p2 is a script directory, not an installed
# package. Bridge it onto sys.path here, and only here, so the rest of the
# server never has to know p2 isn't packaged yet.
_RG_ROOT = os.environ.get(
    "RG_ROOT",
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_P2_ROOT = os.path.join(_RG_ROOT, "experiments", "p2")
for _p in (_RG_ROOT, _P2_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from memory_api import Memory  # noqa: E402 -- after the sys.path bridge
import rgx.facts as _rgx_facts  # noqa: E402 -- same bridge; the rgx package

_VALID_ACTIONS = ("deny", "confirm", "retype")
_SOURCE = "rg-p2-memory"

_lock = threading.RLock()
_state = {"mem": None, "audit_pass": None, "needs_reload": False,
          "uncached_turns": None, "transcripts": None}
# profile_ingest's Extractor: a stanza pipeline load is tens of seconds, so
# it's kept as a lazy module-level singleton, rebuilt only if owner_name
# changes (one owner per server process, in practice).
_ingest_state = {"extractor": None, "owner": None}


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


def _owner_facts_path():
    return os.path.join(_data_dir(), "owner_facts.jsonl")


def _cache_suffix():
    """Mirrors run_wire.build_facts's cache-file selection exactly, so what
    profile_ingest writes is the file the next reload() actually reads."""
    return ("_v5" if os.environ.get("RG_EXTRACT_V5")
            else "_v4" if os.environ.get("RG_EXTRACT_V4")
            else "_v3" if os.environ.get("RG_EXTRACT_V3")
            else "_v2" if os.environ.get("RG_EXTRACT_V2") else "")


def _cache_path():
    return os.path.join(_data_dir(), f"profile_cache{_cache_suffix()}.jsonl")


def _build():
    """One cache-only build: facts -> WireGraph -> Memory. Mirrors
    Memory.load's body exactly, except it keeps the uncached-turn count
    (Memory.load discards it) so profile_status can surface it."""
    from run_wire import build_facts  # local: needs the sys.path bridge above
    from wire import WireGraph
    # 2026-10-02 (second new-user test): on a fresh install the very first
    # profile_recall raised "No such file or directory: conversations.json".
    # Nothing stored is a STATE, not an error -- an empty memory answers
    # "never seen" like any other miss.
    if not os.path.exists(_conversations_path()):
        g = WireGraph.from_facts([], n_convs=0, provisional=[], hearsay=[])
        return Memory(g, {}, owner=os.environ.get("SOURCEDRECALL_OWNER")), 0
    sources = {}
    facts, prov, hearsay, n_convs, titles, n_uncached = build_facts(
        _conversations_path(), min_mentions=2, sources=sources)
    g = WireGraph.from_facts(facts, n_convs=n_convs, provisional=prov,
                              hearsay=hearsay)
    from memory_api import _attach_sources
    _attach_sources(g, sources)
    from memory_api import _mark_ceased   # endings AND state changes, one hook
    _mark_ceased(g, titles)
    # e281: the server knows the owner (it hands the same name to the
    # extractor); give it to the Memory so grounding can ignore the name.
    # Without this the dogfood store had no `name` fact, the index's owner was
    # None, and "What is Alex Reyes's blood type?" grounded on every record.
    owner = _ingest_state.get("owner")
    if not owner:
        try:
            owner = _discover_owner_name()
        except Exception:
            owner = None
    return Memory(g, titles, owner=owner), n_uncached


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


def _get_extractor(owner_name):
    if (_ingest_state["extractor"] is None
            or _ingest_state["owner"] != owner_name):
        from rgx import Extractor
        _ingest_state["extractor"] = Extractor(owner_name=owner_name)
        _ingest_state["owner"] = owner_name
    return _ingest_state["extractor"]


def _discover_owner_name():
    """Best-effort fallback for profile_ingest's owner_name chain, step 3:
    owner_facts.jsonl (ground truth, if the owner has ever been seeded) first,
    else the currently-loaded Memory's best-evidenced name= fact. Never
    raises; None if nothing is found -- Extractor(owner_name=None) is a valid,
    supported call (see rgx.Extractor), just without third-person name
    substitution."""
    owner_path = _owner_facts_path()
    if os.path.exists(owner_path):
        for line in open(owner_path):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if str(d.get("attribute", "")).lower().strip() == "name":
                v = str(d.get("value", "")).strip()
                if v:
                    return v
    mem = _state.get("mem")
    if mem is not None:
        cands = [nd for nd in
                 list(mem.g.nodes.values()) + list(mem.g.provisional.values())
                 if nd.get("attr") == "name"]
        if cands:
            best = max(cands, key=lambda nd: nd.get("n_mentions", 0))
            v = str(best.get("value", "")).strip()
            if v:
                return v.title()
    return None


def _iso_date(date):
    """Normalise a caller's date to the sortable form conversations.json
    uses. Raises ValueError on something that is not a date -- a silently
    mis-ordered history is worse than a refused call."""
    d = str(date).strip()
    try:
        if len(d) == 10:
            return datetime.datetime.strptime(d, "%Y-%m-%d").strftime(
                "%Y-%m-%dT00:00:00Z")
        dt = datetime.datetime.fromisoformat(d.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(datetime.timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise ValueError(f"date must be ISO, e.g. 2026-09-25 -- got {date!r}")


def profile_ingest(turns, conversation_id=None, title=None, owner_name=None,
                   date=None):
    """Turn ONE conversation into new profile-memory facts -- the only WRITE
    path in this module that runs an extractor, and it is rgx: a deterministic
    parser, NOT a language model. No prompt, no sampling, no invented text --
    a fact is either grounded in the turn's own words or it is not emitted.

    turns: [{"role": "user"|"assistant", "content": str}, ...], one dialogue.

    Steps, all under the module reload lock (same discipline as reload()):
      (a) append (or create) this conversation's record in the data dir's
          conversations.json, in the shape run_profile_full.load_stream_and_
          titles reads (uuid, name, created_at, chat_messages:[{sender,text}]).
      (b) run rgx.Extractor over every non-empty turn (owner_name from the
          argument, else env SOURCEDRECALL_OWNER, else an existing profile's
          own name if one is discoverable, else None) and append one cache
          line per NEW turn (by sha1 of its truncated text -- the same hash
          run_wire.build_facts looks up) to the cache file build_facts reads;
          a turn already in the cache is skipped, never re-extracted.
      (c) reload the profile memory, so the next profile_recall/profile_
          context/profile_status sees the new facts immediately.
      (d) return receipts: how many turns were seen, how many carried a new
          (non-hearsay) fact, how many were hearsay (an assistant clause
          reporting a claim ABOUT the user, see run_wire.build_facts), how
          many turns were already cached and skipped, and model_calls=0 --
          always 0, since nothing here is a model call.
    """
    turns = turns or []
    if not turns:
        # Safe no-op: nothing to append, nothing to extract, no reload
        # forced, no extractor loaded. conversation_id is echoed back
        # unchanged (None if not given) -- nothing was created.
        return {"conversation_id": conversation_id, "turns": 0, "facts": 0,
                "hearsay": 0, "skipped_cached": 0, "model_calls": 0}
    with _lock:
        data_dir = _data_dir()
        os.makedirs(data_dir, exist_ok=True)

        owner = (owner_name or os.environ.get("SOURCEDRECALL_OWNER")
                  or _discover_owner_name())

        conv_id = conversation_id or str(_uuidlib.uuid4())
        # 2026-10-02: when the conversation HAPPENED, if the caller knows.
        # Conversation order (and so which statement is "no longer true")
        # follows this; stamping every import with the import time made a
        # week-old chat indistinguishable from today's.
        if date:
            created_at = _iso_date(date)
        else:
            created_at = datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ")

        # ---- (a) conversations.json: append or create ----
        conv_path = _conversations_path()
        convs = []
        if os.path.exists(conv_path):
            try:
                convs = json.load(open(conv_path))
            except Exception:
                convs = []
        record = next((c for c in convs if c.get("uuid") == conv_id), None)
        if record is None:
            record = {"uuid": conv_id, "name": title or "(untitled)",
                       "created_at": created_at, "chat_messages": []}
            convs.append(record)
        elif title:
            record["name"] = title
        chat_messages = record.setdefault("chat_messages", [])
        for t in turns:
            sender = "human" if t.get("role", "user") == "user" else "assistant"
            chat_messages.append(
                {"sender": sender, "text": str(t.get("content", ""))})
        with open(conv_path, "w", encoding="utf-8") as fh:
            json.dump(convs, fh)

        # ---- (b) rgx extraction, cache-append, skip-if-already-cached ----
        ex = _get_extractor(owner)
        cache_path = _cache_path()
        cached_hashes = set()
        if os.path.exists(cache_path):
            for line in open(cache_path):
                try:
                    cached_hashes.add(json.loads(line)["h"])
                except Exception:
                    pass

        n_turns = n_facts = n_hearsay = n_skipped = 0
        new_lines = []
        for ti, t in enumerate(turns):
            role = t.get("role", "user")
            text = str(t.get("content", "")).strip()[:1800]
            if not text:
                continue
            n_turns += 1
            h = _rgx_facts.turn_hash(text)
            if h in cached_hashes:
                n_skipped += 1
                continue
            recs = ex.extract_turn(text, role=role, session=0, turn=ti)
            facts = [f for f in (_rgx_facts.to_fact(r) for r in recs)
                     if f is not None]
            for f in facts:
                if f.get("evidential") == "report":
                    n_hearsay += 1
                else:
                    n_facts += 1
            new_lines.append(json.dumps({"h": h, "f": facts}))
            cached_hashes.add(h)

        if new_lines:
            with open(cache_path, "a", encoding="utf-8") as fh:
                for line in new_lines:
                    fh.write(line + "\n")

        # ---- (c) reload ----
        _reload_locked()

    # ---- (d) receipts ----
    return {"conversation_id": conv_id, "turns": n_turns, "facts": n_facts,
            "hearsay": n_hearsay, "skipped_cached": n_skipped,
            "model_calls": 0}


# --------------------------------------------------------------- the tools

def profile_recall(query):
    """RG_PROFILE_V3=1 routes the read through retrieval v3 (e258): the
    champion retriever measured since e132, which until now only ever ran on
    the benchmark QA path. The product shipped token overlap. Off by default
    -- it loads two small local models (~150MB, non-generative) on first use,
    so the zero-model request-path guarantee changes shape and that is the
    caller's decision, not ours."""
    mem = _ensure_loaded()
    with _lock:
        out = _recall(mem, query)
    out["source"] = _SOURCE
    return out


def _recall(mem, query):
    """e277: v3 IS NOW THE DEFAULT.

    e258 measured the product read path at 5/10 rank-1 against v3's 9/10 and
    concluded "the product never got the retriever we validated". It then
    shipped v3 behind `RG_PROFILE_V3=1` -- which nothing sets. Not the server,
    not the README, not any install path. So the conclusion of e258 was still
    true after e258: a fresh install got the weak retriever.

    Default flipped, with `RG_PROFILE_V3=0` to opt out. v3 loads two small
    local models (~150MB, non-generative) on first use, so a deployment that
    cannot afford that -- or an environment without transformers -- FALLS BACK
    rather than failing: the older path is worse, not broken.
    """
    if os.environ.get("RG_PROFILE_V3") == "0":
        return mem.recall(query)
    try:
        return mem.recall_v3(query)
    except Exception:
        # No models available, or v3 unusable in this environment. The
        # token-overlap path is a real, tested retriever; degrade to it.
        return mem.recall(query)


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
