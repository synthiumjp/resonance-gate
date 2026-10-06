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
import re
import sys
import threading
import uuid as _uuidlib

# Packaging debt (v1): experiments/p2 is a script directory, not an installed
# package. Bridge it onto sys.path here, and only here, so the rest of the
# server never has to know p2 isn't packaged yet.
from sourcedrecall._bridge import code_roots as _code_roots
_RG_ROOT, _P2_ROOT = _code_roots()
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
    try:
        conv_scopes = {c.get("uuid"): c.get("scope")
                       for c in json.load(open(_conversations_path()))}
    except Exception:
        conv_scopes = {}
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
    mem = Memory(g, titles, owner=owner)
    mem.conv_scopes = conv_scopes
    from memory_api import _unparsed_sentences
    mem.unparsed = _unparsed_sentences(_conversations_path(), g)
    return mem, n_uncached


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
        from sourcedrecall.paths import use_installed_parser
        use_installed_parser()
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
                   date=None, scope=None):
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
    # 2026-10-02: credentials never enter the memory -- not the stored
    # transcript, not a fact, not a quoted sentence (sourcedrecall.secrets).
    from sourcedrecall.secrets import scrub, MARK
    turns = [dict(t, content=scrub(t.get("content")))
             if isinstance(t, dict) and isinstance(t.get("content"), str) else t
             for t in turns]
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
        # 2026-10-02: the project this conversation happened in (a path), so
        # its facts about the world stay in that project. None: no scope.
        if scope and not record.get("scope"):
            from sourcedrecall.paths import project_scope
            record["scope"] = project_scope(scope)
        elif title:
            record["name"] = title
        chat_messages = record.setdefault("chat_messages", [])
        # 2026-10-02: re-ingesting a conversation was documented as a safe
        # no-op but appended every message again; only the extraction was
        # skipped. A session-end hook re-sends the WHOLE transcript every
        # time a session is resumed and ended, so the store grew a copy per
        # resume. Messages already in this conversation are not appended
        # again (matched by sender + exact text).
        have = {(m.get("sender"), m.get("text")) for m in chat_messages}
        for t in turns:
            sender = "human" if t.get("role", "user") == "user" else "assistant"
            msg = {"sender": sender, "text": str(t.get("content", ""))}
            if (msg["sender"], msg["text"]) in have:
                continue
            have.add((msg["sender"], msg["text"]))
            chat_messages.append(msg)
        # atomic: a crash mid-write must not leave half a memory (review
        # 2026-09-05 E, non-atomic conversations.json)
        _tmp = conv_path + ".tmp"
        with open(_tmp, "w", encoding="utf-8") as fh:
            json.dump(convs, fh)
        os.replace(_tmp, conv_path)

        # ---- (b) rgx extraction, cache-append, skip-if-already-cached ----
        ex = _get_extractor(owner)
        # 2026-10-02: the entities and names the user has linked to
        # themselves ("my dog Biscuit", "the billing service") survive
        # between sessions; each session-end ingest is a new process.
        world_path = os.path.join(_data_dir(), "world.json")
        try:
            with open(world_path, encoding="utf-8") as fh:
                saved = json.load(fh)
            if isinstance(saved, dict):
                for k, v in saved.items():
                    ex._world.setdefault(k, v)
        except (OSError, ValueError):
            pass
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
        # parse the conversation's new messages in batches first (6x faster
        # for a long conversation or an imported history; same parses)
        todo = []
        for t in turns:
            text = str(t.get("content", "")).strip()[:1800]
            if text and _rgx_facts.turn_hash(text) not in cached_hashes:
                todo.append(_prose_only(text))
        if len(todo) > 1 and hasattr(ex, "prefetch"):
            ex.prefetch(todo)
        prev = None     # the assistant message before a user turn (rgx.fragments)
        for ti, t in enumerate(turns):
            role = t.get("role", "user")
            text = str(t.get("content", "")).strip()[:1800]
            if not text:
                continue
            before, prev = prev, (text if role == "assistant" else None)
            n_turns += 1
            h = _rgx_facts.turn_hash(text)
            if h in cached_hashes:
                n_skipped += 1
                continue
            ptext = _prose_only(text)
            if not ptext:
                continue
            recs = ex.extract_turn(ptext, role=role, session=0, turn=ti,
                                   prev=before if role == "user" else None)
            facts = [f for f in (_rgx_facts.to_fact(r) for r in recs)
                     if f is not None and MARK not in str(f.get("value"))
                     and MARK not in str(f.get("text"))]
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
            tmp = world_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(ex._world, fh)
            os.replace(tmp, world_path)

        # ---- (c) reload ----
        _reload_locked()
    _export_quietly()       # MEMORY.md reflects every write

    # ---- (c2) optional model-written notes (notes.py; off by default) ----
    model_calls = 0
    from sourcedrecall import notes as _notes
    if _notes.enabled() and owner and n_turns > n_skipped:
        try:
            written = _notes.write_notes(owner, created_at[:10], turns)
            model_calls = 1
            _save_notes(conv_id, created_at[:10], written)
        except Exception as e:      # a model that is down must not lose the session
            print(f"sourcedrecall: notes not written ({e})", file=sys.stderr)

    # ---- (d) receipts ----
    return {"conversation_id": conv_id, "turns": n_turns, "facts": n_facts,
            "hearsay": n_hearsay, "skipped_cached": n_skipped,
            "model_calls": model_calls}


# --------------------------------------------------------------- the tools

def _set_scope(mem, scope):
    from sourcedrecall.paths import current_scope
    mem.scope = current_scope(scope)


def profile_recall(query, scope=None):
    """RG_PROFILE_V3=1 routes the read through retrieval v3 (e258): the
    champion retriever measured since e132, which until now only ever ran on
    the benchmark QA path. The product shipped token overlap. Off by default
    -- it loads two small local models (~150MB, non-generative) on first use,
    so the zero-model request-path guarantee changes shape and that is the
    caller's decision, not ours.

    `scope`: the project to read in (2026-10-02). Default: the project Claude
    Code is running in, if any; facts about the world from other projects are
    hidden, facts about the user are not."""
    mem = _ensure_loaded()
    with _lock:
        _set_scope(mem, scope)
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
        # 2026-10-03: but SAY so -- a bug in recall_v3 was silently turned
        # into "never seen" by this fallback.
        import traceback
        print("sourcedrecall: recall_v3 failed, using the fallback retriever:\n"
              + traceback.format_exc(), file=sys.stderr, flush=True)
        return mem.recall(query)


def _message_of(conversation_id, said):
    """-> (the user's whole message that contains `said`, the turn just
    before it) from conversations.json, or (None, None).

    2026-10-04 (LoCoMo dev): the answer was often in the rest of the message
    ("...a gift from my grandma in Sweden. It stands for love, faith and
    strength.") or in a reply to the other side's question ("How long have
    you been married?"). Sentences the user asked to forget are taken out of
    the message before it is quoted."""
    if not conversation_id or not said:
        return None, None
    import re as _re
    from memory_api import _SENT_SPLIT, _denied_sentence
    with _lock:
        try:
            conv = _ensure_transcripts_locked().get(conversation_id)
        except (OSError, ValueError):
            return None, None
    if not conv:
        return None, None
    norm = lambda t: _re.sub(r"\W+", " ", t or "").strip().lower()  # noqa: E731
    key = norm(said)
    turns = conv["turns"]
    for i, t in enumerate(turns):
        if t["role"] != "human" or not key or key not in norm(t["text"]):
            continue
        denied, denied_said = [], []
        try:
            for line in open(_corrections_path()):
                c = json.loads(line)
                if c.get("action") == "deny":
                    if c.get("said"):
                        denied_said.append(c["said"])
                    if c.get("value"):
                        denied.append(str(c["value"]))
        except (OSError, ValueError):
            pass
        sents = [x for x in _SENT_SPLIT.split(t["text"].strip())
                 if not _denied_sentence(x, denied, denied_said)]
        prev = (turns[i - 1]["text"] if i and turns[i - 1]["role"] == "assistant"
                else None)
        return " ".join(sents) or None, prev
    return None, None


# 2026-10-05 (multi-project coding set): a message with a pasted code block
# reached the parser whole -- "...for the record I always use tabs, never
# spaces, in any code you write for me." ran into the C++ that followed and
# nothing was stored. The parser reads the prose only; the stored message
# keeps the code for quoting.
def _prose_only(text):
    from prose import prose_only
    return prose_only(text)


def _denied_lists():
    denied, denied_said = [], []
    try:
        for line in open(_corrections_path()):
            c = json.loads(line)
            if c.get("action") == "deny":
                if c.get("said"):
                    denied_said.append(c["said"])
                if c.get("value"):
                    denied.append(str(c["value"]))
    except (OSError, ValueError):
        pass
    return denied, denied_said


def _links():
    """{"home country": "Sweden"} -- the phrases the user linked to a name
    (rgx._link), from world.json."""
    try:
        with open(os.path.join(_data_dir(), "world.json"), encoding="utf-8") as fh:
            w = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {k[1:]: v for k, v in w.items() if k.startswith("=") and v}


# 2026-10-06 (LongMemEval single-session-preference, 30 questions): a
# request for advice addressed to the assistant ("Can you recommend...",
# "any tips for...", "what should I...") is answered by something the user
# mentioned owning or liking, which the ms-marco cross-encoder ranks low.
# Those questions rank by embeddings with a little BM25 (session recall@5
# 90.0% -> 100%, @1 56.7% -> 70.0%; weights chosen on those 30, so not a
# held-out figure). The pattern matched 24 of the 30 and none of the other
# 470 LongMemEval questions or LoCoMo's 1,986.
_ADVICE_Q = re.compile(
    r"\b(?:can|could|would) you (?:please )?(?:recommend|suggest|give me (?:some|any)|"
    r"help me (?:find|choose|pick|plan|decide))"
    r"|\bany (?:tips|ideas|advice|suggestions|recommendations)\b"
    r"|\bwhat should i\b|\bwhich (?:\w+ )?should i\b"
    r"|\bdo you have any (?:tips|ideas|advice|suggestions|recommendations)\b"
    r"|\b(?:recommend|suggest) (?:me|some|a few)\b"
    r"|\bi(?:'d| would) (?:love|like) (?:some|a few) (?:tips|ideas|suggestions|recommendations)\b",
    re.I)


def _messages_for(query, k=3):
    """2026-10-04: the user's own messages that best match the question,
    ranked by the same models as facts (retrieve_v3) -- for answers the
    parser never made a fact of. -> [{"text", "date", "asked", "score"}].
    The index is rebuilt when the transcripts change."""
    import retrieve_v3 as _RV3
    from memory_api import _SENT_SPLIT, _denied_sentence
    with _lock:
        try:
            tr = _ensure_transcripts_locked()
        except (OSError, ValueError):
            return []
        cached = _state.get("msg_index")
        if cached is None or cached[0] is not tr:
            denied, denied_said = _denied_lists()
            docs = []
            for cid, conv in tr.items():
                turns = conv["turns"]
                for i, t in enumerate(turns):
                    if t["role"] != "human" or "[MEMORY" in t["text"]:
                        continue
                    sents = [x for x in _SENT_SPLIT.split(t["text"].strip())
                             if not _denied_sentence(x, denied, denied_said)]
                    text = " ".join(sents).strip()
                    if len(text.split()) < 3:
                        continue
                    prev = (turns[i - 1]["text"] if i and turns[i - 1]["role"]
                            == "assistant" else None)
                    docs.append({"attr": "", "value": text, "text": text,
                                 "date": conv["date"], "asked": prev,
                                 "conv": cid})
            cached = (tr, _RV3.IndexV3(None, facts=docs) if docs else None)
            _state["msg_index"] = cached
    if cached[1] is None:
        return []
    hits = _RV3.retrieve_facts_v3(cached[1], query, k=60, dense_k=30,
                                  top_n=k, with_scores=True,
                                  fuse=(tuple(float(x) for x in os.environ.get(
                                      "RG_FUSE3_W", "0.3/0.3").split("/"))
                                        if os.environ.get("RG_FUSE3") == "1"
                                        else (0.2, 0.0) if (_ADVICE_Q.search(query or "")
                                                            and os.environ.get("RG_ADVICE_ROUTE", "1") != "0")
                                        else None),
                                  colbert=(0.3, 1.0, 0.3) if os.environ.get("RG_COLBERT_DIR") else None)
    return [dict(h, score=sc) for h, sc in hits]


def profile_context(query=None, max_facts=None, scope=None):
    # 2026-10-04 (LoCoMo dev): 5 lines per speaker answered as well as 10
    # (58.8% at 568 tokens vs 58.4% at 899), so a question gets 8 lines by
    # default; the profile summary keeps 15
    if max_facts is None:
        max_facts = 8 if query else 15
    mem = _ensure_loaded()
    with _lock:
        _set_scope(mem, scope)
        if os.environ.get("RG_MESSAGE_QUOTES") != "0":
            mem.message_of = _message_of
        if os.environ.get("RG_MESSAGE_RECALL", "1") != "0":
            mem.messages_for = _messages_for
        from sourcedrecall import notes as _notes
        mem.notes_for = _notes_for if _notes.enabled() else None
        mem.links = _links()
        block = mem.context_block(query, max_facts)
    return {"block": block}


def profile_correct(action, attribute, value, new_attribute=None, exact=False,
                    said=None):
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
    if said:
        # the sentence the fact came from: a forgotten fact's words must not
        # come back as a quote after a reload (review round 3)
        correction["said"] = said

    with _lock:
        data_dir = _data_dir()
        os.makedirs(data_dir, exist_ok=True)
        path = _corrections_path()
        with open(path, "a") as f:
            f.write(json.dumps(correction) + "\n")
        if action == "deny":
            _drop_embeddings()
            _drop_notes(said or (value if attribute == "said" else None))

        if action == "retype":
            _state["needs_reload"] = True
            return {"written": correction, "applied": "on-reload",
                    "needs_reload": True}

        mem = _ensure_loaded()
        log = mem.apply_corrections([correction])
        _state["audit_pass"] = None   # graph just changed; recompute lazily
    _export_quietly()
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


_NEG_HEAD = re.compile(r"^\s*(?:not|no longer|never|no)\b\s*", re.I)
_CLAIM_SUBJ = [
    (re.compile(r"\bthe user's\b", re.I), "my"),
    (re.compile(r"^\s*the user\b", re.I), "I"),
    (re.compile(r"\bthe user\b", re.I), "me"),
    (re.compile(r"\b(?:currently|presently|still)\s+", re.I), ""),
]


def _claim_text(claim, owner):
    """'The user currently lives in Northcote.' -> 'I live in Northcote.' The
    parser reads a claim the way it reads something the user said."""
    t = " ".join(str(claim or "").split())
    for rx, rep in _CLAIM_SUBJ:
        t = rx.sub(rep, t)
    if owner:
        t = re.sub(rf"^\s*{re.escape(owner)}'s\b", "my", t)
        t = re.sub(rf"^\s*{re.escape(owner)}\b", "I", t)
    # third-person verb after a first-person subject reads badly to the
    # parser ("I lives"); the common cases
    t = re.sub(r"^I (is)\b", "I am", t)
    t = re.sub(r"^I (has)\b", "I have", t)
    t = re.sub(r"^I (\w+?)(ies)\b", lambda m: f"I {m.group(1)}y", t)
    t = re.sub(r"^I (\w+?[^s])s\b", r"I \1", t)
    return t[:1].upper() + t[1:]


_NEG_WORDS = re.compile(r"\b(not|never|no|nobody|none|neither|nor|without|"
                        r"\w+n't|cannot)\b", re.I)
_HEDGED = re.compile(
    r"\b(would|could|wish|maybe|perhaps|might|(?:might|would|could|should|must)'ve|"
    r"thinking (?:about|of)|considering|"
    r"think about it|no idea|not decided|undecided|dunno|remains to be seen|"
    r"ought|should|reckons?|keeps? telling|telling me|saying|says|said I|"
    r"apparently|supposedly|heard|rumou?r\w*|"
    r"if|unless|in case|someday|some day|at some point|doubt|not sure|wonder\w*|"
    r"plan(?:ning)? to|going to|want to|hope|hoping|whether|either|or not|thinks? I|"
    r"people|everyone|they say)\b", re.I)
# a clause that opens like a question, with or without its "?"
def _ends_value(clause, words, window=4):
    """Does an ending word in `clause` govern one of `words`? The value
    follows the ending word closely ("sold the Corolla", "left Acme") or
    precedes "anymore" / "no longer" / "any more" closely."""
    import currency
    toks = re.findall(r"[a-z0-9'-]+", (clause or "").lower())
    stems = [currency._stem(t) for t in toks]
    for m in _ENDED.finditer(clause or ""):
        k = len(re.findall(r"[a-z0-9'-]+", clause[:m.start()].lower()))
        kw = m.group(0).lower()
        if kw in ("anymore", "any more", "no longer"):
            span = stems[max(0, k - window):k]
        else:
            span = stems[k + len(kw.split()):k + len(kw.split()) + window]
        if set(span) & set(words):
            return True
    return False


def _is_name(word):
    """A capitalised word that is not an ordinary English word (WordNet)."""
    if not word or not word[0].isupper():
        return False
    try:
        from nltk.corpus import wordnet as wn
        return not wn.synsets(word.lower())
    except Exception:
        return False


_QUESTION_OPEN = re.compile(r"^\s*(what|how|why|which|who|where|when|whether|is|are|"
                            r"do|does|did|can|could|should|would|will|am)\b", re.I)
# an ending or a replacement: "I sold the Corolla" is not evidence that the
# user drives one now -- it is evidence that they did and no longer do
_ENDED = re.compile(r"\b(quit|quitting|sold|dropped|left|gave up|giving up|stopped|"
                    r"ended|cancel+ed|moved (?:away|out)|no more|no longer|anymore|"
                    r"any more|ex-|former|used to)\b", re.I)
# ("moved to", "switched to", "instead" name the NEW state: "We relocated to
# Coburg" supports "lives in Coburg")
_INSTEAD = re.compile(r"\s*\b(?:instead of|rather than|in place of|replacing)\b.*$", re.I)


def _neg_split(value):
    """-> (negated, value without the negation or an 'instead of X' tail).
    "Fatima instead of Mark" is a value of Fatima, not of Mark (dev stale2)."""
    v = str(value or "").strip().lower()
    neg = bool(_NEG_HEAD.match(v))
    v = _INSTEAD.sub("", _NEG_HEAD.sub("", v)).strip()
    return neg, v


# how close (bge-small cosine) a later message with a change word must be to
# the message that supports a claim to count as possibly changing it
# (profile_check). On the readable sets the replacing messages scored
# 0.53-0.65 against the original, unrelated ones about 0.47; the adversarial
# review found unrelated pairs at 0.50-0.52 ("I got engaged" after "plays the
# cello"), so the floor is 0.6 and some real changes are missed.
CHECK_LATER_COS = float(os.environ.get("RG_CHECK_LATER_COS", "0.6"))


def _families_by_message(mem):
    """{normalised message text fragment: set of state families} from the
    stored facts' own sentences."""
    import currency
    out = []
    for st in (mem.g.nodes, mem.g.provisional):
        for nd in st.values():
            fams = {fam for fam, _k in currency._families(nd.get("attr"), nd.get("value"))}
            src = (nd.get("source") or "").strip().lower()
            if fams and src:
                out.append((src, fams))
    return out


def _later_changes(claim, said, after, hits=None, cfams=None):
    """Messages after `after` that may have changed what `said` states: in
    the message search for the claim, dated later, with a change word ("now",
    "since", "instead", "without", "cancelled"...), and close in meaning to
    a supporting message ("Cancelled the gym membership" after "I train at
    Anytime Fitness" shares no word with it)."""
    import retrieve_v3 as _RV3
    from memory_api import _CHANGE
    hits = hits if hits is not None else _messages_for(claim, k=8)
    said = [t for t in said if t]
    cands = [m for m in hits if (m.get("date") or "") > (after or "")
             and (m.get("text") or "").strip().lower() not in
             {t.strip().lower() for t in said}
             and (_CHANGE.search(m.get("text") or "")
                  or re.search(r"\b(without|cancel+ed|ended|over|ex-)\b",
                               m.get("text") or "", re.I))]
    if not cands or not said:
        return []
    if cfams:
        # a later message about a different kind of state does not change
        # this one: a move is not a change of job
        known = _families_by_message(_ensure_loaded())
        keep = []
        for m in cands:
            low = (m.get("text") or "").lower()
            mf = set().union(*[f for src, f in known if src and src in low]) if known else set()
            if mf and not (mf & cfams):
                continue
            keep.append(m)
        cands = keep
        if not cands:
            return []
    bi, _ = _RV3._models()
    sv = bi.encode(said, normalize_embeddings=True)
    out = []
    for m in cands:
        mv = bi.encode([m["text"]], normalize_embeddings=True)[0]
        cos = float(max(sv @ mv))
        if cos >= CHECK_LATER_COS:
            out.append(dict(m, cos=round(cos, 3)))
    return out


def profile_check(claim, scope=None):
    """Did the user say this? (2026-10-05)

    For something an agent is about to rely on -- "The user lives in
    Fitzroy", a tool argument -- the verdict and the user's own dated words:

      said           the user said it; `since` says what is known about it
                     after that: "no longer true" (a later statement replaced
                     it), "may have changed" (a later message on the topic,
                     returned too), or "no later change found" -- which is
                     not a promise that it is still true
      contradicted   the user said otherwise (a negation, or a current
                     different value of the same thing)
      unconfirmed    only the assistant said it; the user never confirmed it
      not_found      nothing the user said was found about this (absence of
                     evidence: a claim in very different words can be missed)
      unclear        the user's messages touch the topic but do not settle it
                     (the closest messages are returned)

    Deterministic: the parser reads the claim as it reads a message, and the
    claim's facts are compared with the stored ones by attribute and by the
    kind of state (home, job, partner...), with the same value comparison
    the "no longer true" marking uses. No language model is called (the
    message search uses the small ranking models)."""
    import currency
    from memory_api import fact_id
    mem = _ensure_loaded()
    owner = (_ingest_state.get("owner") or os.environ.get("SOURCEDRECALL_OWNER")
             or _discover_owner_name() or "User")
    text = _claim_text(claim, owner)
    ex = _get_extractor(owner)
    recs = ex.extract_turn(text, role="user")
    cfacts = [f for f in (_rgx_facts.to_fact(r) for r in recs) if f]
    with _lock:
        _set_scope(mem, scope)
        stored = [f for f in _all_facts(mem)]
        visible = {fact_id(nd) for st in (mem.g.nodes, mem.g.provisional,
                                         getattr(mem.g, "hearsay", {}) or {})
                   for nd in st.values() if mem._visible(nd)}
    stored = [f for f in stored if f["id"] in visible]
    by_id = {f["id"]: f for f in stored}

    def ev(f, status):
        r = (f.get("receipts") or [{}])[0]
        return {"id": f["id"], "status": status, "fact": f.get("text"),
                "said": f.get("said"), "date": r.get("date")}

    found = {"supported": [], "no_longer_true": [], "contradicted": [],
             "unconfirmed": []}
    claim_fams = {fam for cf in cfacts
                  for fam, _k in currency._families(cf["attribute"], _neg_split(cf["value"])[1])}
    for cf in cfacts:
        cattr, _ = currency.canon_state_attr(cf["attribute"])
        cneg, cval = _neg_split(cf["value"])
        cfam = {fam: set(k) if not isinstance(k, str) else k
                for fam, k in currency._families(cf["attribute"], cval)}
        for sf in stored:
            sattr, _ = currency.canon_state_attr(sf.get("attribute"))
            sneg, sval = _neg_split(sf.get("value"))
            sfam = {fam: set(k) if not isinstance(k, str) else k
                    for fam, k in currency._families(sf.get("attribute"), sval)}
            shared = set(cfam) & set(sfam)
            if sattr != cattr and not shared:
                continue
            if shared:
                same = not any(currency._different(fam, cfam[fam], sfam[fam])
                               for fam in shared)
            else:
                same = currency._same_value(cval, sval)
            hearsay = sf.get("_tier") == "hearsay"
            if same and cneg != sneg:
                if not hearsay and sf.get("current") is not False:
                    found["contradicted"].append(ev(sf, "contradicts"))
                continue
            if same:
                if hearsay:
                    found["unconfirmed"].append(ev(sf, "assistant said it"))
                elif sf.get("current") is False:
                    e = ev(sf, "no longer true")
                    new = by_id.get(fact_id_of_node(mem, sf.get("superseded_by")))
                    if new:
                        e["replaced_by"] = ev(new, "current")
                    found["no_longer_true"].append(e)
                else:
                    found["supported"].append(ev(sf, "supports"))
            elif shared and not hearsay and sf.get("current") is not False \
                    and not cneg and not sneg:
                found["contradicted"].append(ev(sf, "a different current value"))

    # a supporting fact older than a current different value of the same
    # single-valued state was replaced even if the marking missed it
    if found["supported"] and found["contradicted"]:
        last_sup = max(e["date"] or "" for e in found["supported"])
        newer = [e for e in found["contradicted"] if (e["date"] or "") > last_sup]
        if newer:
            for e in found["supported"]:
                e["status"] = "may have changed"
                e["replaced_by"] = newer[-1]
            found["no_longer_true"] += found["supported"]
            found["supported"] = []

    # 2026-10-05 (check_eval, dev v1): "Back in Porto since the start of
    # the month" and "Cancelled the gym membership" replaced earlier facts
    # without a word in common, so nothing was marked. "supported" needs no
    # LATER message on the topic: the message search for the claim finds
    # one, it is shown, and the verdict is "may_have_changed".
    if found["supported"]:
        last = max(e["date"] or "" for e in found["supported"])
        said = [(e.get("said") or "").strip() for e in found["supported"]]
        later = _later_changes(claim, said, last, cfams=claim_fams)
        if later:
            for e in found["supported"]:
                e["status"] = "may have changed"
            found["may_have_changed"] = found.pop("supported") + [
                {"status": "later message", "said": m.get("text"),
                 "date": m.get("date"), "similarity": m.get("cos")}
                for m in later[:2]]
            found["supported"] = []

    if found["supported"]:
        verdict = "supported"
    elif found.get("may_have_changed"):
        verdict = "may_have_changed"
    elif found["no_longer_true"]:
        verdict = "no_longer_true"
    elif found["contradicted"]:
        verdict = "contradicted"
    elif found["unconfirmed"]:
        verdict = "unconfirmed"
    else:
        verdict = None
    evidence = [e for k in ("supported", "may_have_changed", "no_longer_true",
                            "contradicted", "unconfirmed") for e in found.get(k, [])]
    # the user's messages that carry the claim's words: the claim was said
    # in other words than the stored fact, or never became a stored fact
    # (fragments such as "Fourth week as a paramedic", negations such as
    # "I don't smoke"). Same project rule as the memory block.
    cneg_claim = bool(_NEG_WORDS.search(text))
    cwords = currency._content(" ".join([f["text"] for f in cfacts] or [text]))
    cwords -= currency._content(owner) | {"user"}
    vwords = currency._content(" ".join(f["value"] for f in cfacts)) - \
        currency._content(owner) if cfacts else set()
    key_word = None
    for f in cfacts:
        ws = [w for w in re.findall(r"[a-z0-9]+", (f.get("value") or "").lower())
              if currency._stem(w) in currency._content(w)]
        if ws:
            key_word = currency._stem(ws[-1])
    pred_words = set()
    for f in cfacts:
        pred_words |= currency._content(" ".join(re.split(r"[_:]", f.get("attribute") or "")))
    pred_words -= {"is", "are", "be", "have", "has", "had", "do", "does"} | currency._content(owner)
    msg_ev = None
    if cwords and verdict in (None, "contradicted"):
        conv_scope = getattr(mem, "conv_scopes", {}) or {}
        for m in _messages_for(claim, k=6):
            if scope and conv_scope.get(m.get("conv")) not in (None, scope):
                continue
            mw = currency._content(m.get("text"))
            if len(cwords & mw) < max(1, round(0.6 * len(cwords))):
                continue
            # names alone (a project, a person) are not the claim
            names = {w for w in currency._content(" ".join(
                re.findall(r"\b[A-Z][\w-]+", claim)))} - vwords
            if not ((cwords & mw) - names):
                continue
            # the claim's own values must be there: "I teach history" in
            # Sheffield is not "teaches in Leeds"; and its key word (the last
            # content word of the value, the object) must be: "allergic to
            # penicillin" is not "allergic to peanuts" (adversarial review)
            if vwords and len(vwords & mw) < max(1, round(0.6 * len(vwords))):
                continue
            if key_word and key_word not in mw:
                continue
            # the claim's verb too, unless it is only "be" / "have": "Thanks
            # for the tips on pasta" does not say the user likes pasta
            if pred_words and not (pred_words & mw):
                continue
            # negation is read in the clause that carries the claim's words:
            # "Got my own one-bedroom in Yarraville, no more sharing the
            # bathroom" does not deny the one-bedroom
            clauses = [c for c in re.split(r"[.!?;]+|,|\bbut\b", m.get("text") or "")
                       if c.strip()]
            # the clause that holds the claim's key word ("I drink tea, never
            # coffee": the "never coffee" clause), else the one with most of
            # its words
            keyed = [c for c in clauses if key_word and key_word in currency._content(c)]
            best = (keyed[0] if keyed else
                    max(clauses, key=lambda c: len(cwords & currency._content(c)), default=""))
            # negation is read in the sentence that carries the claim's words
            # and at the start of the next one ("Not me." after a sentence
            # about someone else)
            sents = [x for x in re.split(r"(?<=[.!?])\s+", m.get("text") or "") if x.strip()]
            si = max(range(len(sents)), key=lambda i: len(cwords & currency._content(sents[i])),
                     default=0)
            sent = sents[si] if sents else best
            nxt = sents[si + 1] if si + 1 < len(sents) else ""
            mneg = bool(_NEG_WORDS.search(best)) or bool(
                re.match(r"^\s*(no|not|never|nope)\b", nxt, re.I))
            # a hedge, question, wish or someone else's report is not the
            # user saying it ("My dad keeps telling me I'm too stubborn",
            # "Do you think we should try Bun?", "Maybe we rewrite it in Rust")
            hedge = _HEDGED.search(best)
            if hedge and re.search(rf"\b{re.escape(hedge.group(0))}\b", text, re.I):
                hedge = None        # the claim is about wanting / hoping itself
            if hedge or "?" in (m.get("text") or "").split(best)[-1][:2] \
                    or best.strip().endswith("?") or _QUESTION_OPEN.match(best.strip()):
                continue
            # the clause is about the user: a first-person word, or no other
            # named subject ("Sam runs the pipeline" is about Sam). A
            # capitalised first word is a name only if it is not an ordinary
            # word ("Fourth week as a paramedic" is about the user).
            if not re.search(r"\b(i|i'm|i've|i'd|i'll|me|my|mine|we|we're|our|us)\b", best, re.I):
                first = (re.findall(r"[A-Za-z']+", best) or [""])[0]
                if first.lower() in ("he", "she", "they") or (
                        _is_name(first) and first.lower() not in text.lower()):
                    continue
            # an ending: evidence the user did, and no longer does -- when
            # the ending word governs the claim's own value ("I left Acme",
            # "no Corolla anymore"), not another one in the clause ("I left
            # Acme and joined Birch" does not end the Birch claim)
            if _ends_value(best, vwords or cwords) and not _ENDED.search(text):
                found["no_longer_true"].append({"status": "ended", "said": m.get("text"),
                                                "date": m.get("date")})
                verdict = "no_longer_true"
                evidence = found["no_longer_true"] + evidence
                msg_ev = None
                break
            # a negation in raw message text is too often about something
            # else in the clause ("no air con", "can't find the kitchen") to
            # call the claim contradicted; the parser's negated facts do that
            if mneg != cneg_claim:
                continue
            msg_ev = (m, True)
            break
    if msg_ev is not None:
        m, agrees = msg_ev
        older = [e for e in found["contradicted"] if (e["date"] or "") >= (m.get("date") or "")]
        if not agrees:
            if verdict is None:
                verdict = "contradicted"
                evidence = [{"status": "says otherwise", "said": m.get("text"),
                             "date": m.get("date")}]
        elif verdict is None or (verdict == "contradicted" and not older):
            # said, and later than anything that differs from it
            e = {"status": "supports", "said": m.get("text"), "date": m.get("date")}
            later = _later_changes(claim, [m.get("text") or ""], m.get("date"),
                                   cfams=claim_fams)
            verdict = "may_have_changed" if later else "supported"
            if later:
                e["status"] = "may have changed"
            evidence = [e] + [{"status": "later message", "said": x.get("text"),
                               "date": x.get("date"), "similarity": x.get("cos")}
                              for x in later[:2]] + [
                dict(c, status="said earlier") for c in found["contradicted"]][:2]
    if verdict is None:
        # nothing stored settles it: do the user's messages touch it at all?
        words = currency._content(" ".join(f["value"] for f in cfacts) or text)
        words -= currency._content(owner)
        hits = _messages_for(claim, k=6) if words else []
        near = [m for m in hits if words & currency._content(m.get("text"))][:3]
        verdict = "unclear" if near else "not_found"
        # the claim's words are in an earlier message and a later message on
        # the topic follows: "four coffees a day" then "Two months without
        # any coffee now"
        conv_scope = getattr(mem, "conv_scopes", {}) or {}
        if scope:
            near = [m for m in near if conv_scope.get(m.get("conv")) in (None, scope)]
            verdict = "unclear" if near else "not_found"
        evidence = [{"status": "mentions", "said": m.get("text"),
                     "date": m.get("date"), "score": round(m.get("score", 0), 2)}
                    for m in near]
    # 2026-10-05 (check_eval on the readable sets): "supported" as a
    # statement about NOW was right for only 81% of the claims it was given
    # to -- changes such as "Fourth week as a paramedic" after "I'm a
    # pharmacy assistant" carry no change word and no shared fact. So the
    # verdict says what the evidence can carry: whether the user SAID it,
    # and separately what is known about it since.
    said = verdict in ("supported", "may_have_changed", "no_longer_true")
    since = {"supported": "no later change found",
             "may_have_changed": "may have changed",
             "no_longer_true": "no longer true"}.get(verdict)
    return {"claim": claim, "read_as": [f["text"] for f in cfacts],
            "verdict": "said" if said else verdict,
            "since": since, "evidence": evidence[:6]}


def fact_id_of_node(mem, node_id):
    """The public fact id of a store node id (superseded_by holds node ids)."""
    from memory_api import fact_id
    if not node_id:
        return None
    for st in (mem.g.nodes, mem.g.provisional):
        nd = st.get(node_id)
        if nd is not None:
            return fact_id(nd)
        for nd in st.values():
            if nd.get("id") == node_id:
                return fact_id(nd)
    return None


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


# ------------------------------------------------- a memory you can read and edit
#
# 2026-10-02. From research into what people want from AI memory: being able
# to SEE what is stored and remove it is the second most common request
# (a CHI 2026 interview study: most users were unpleasantly surprised by what
# ChatGPT had remembered), and developers want it as plain, portable files
# rather than hidden state. So every change rewrites MEMORY.md beside the
# data, and any fact can be forgotten or confirmed by its short id.

def _owner_subject(text, owner):
    t = (text or "").strip()
    return bool(owner) and (t.startswith(owner) or t.startswith(owner + "'s"))


def _all_facts(mem):
    out = []
    for tier, store in (("asserted", mem.g.nodes), ("provisional", mem.g.provisional),
                        ("hearsay", getattr(mem.g, "hearsay", {}) or {})):
        for nd in store.values():
            f = mem._fact(nd, provisional=(tier == "provisional"))
            f["_tier"] = tier
            out.append(f)
    return out


def memory_file():
    """Where MEMORY.md is written."""
    return os.path.join(_data_dir(), "MEMORY.md")


def profile_news(mark=True):
    """Facts stored since the last call, newest first, for the "saved"
    notice at session start (research into what users want, 2026-10-02:
    visible notices, not silent background harvesting). The ids already
    reported are kept in <data dir>/seen.json; mark=False only looks."""
    mem = _ensure_loaded()
    with _lock:
        facts = [f for f in _all_facts(mem)
                 if f["_tier"] != "hearsay" and f.get("current") is not False]
        path = os.path.join(_data_dir(), "seen.json")
        try:
            with open(path, encoding="utf-8") as fh:
                seen = set(json.load(fh).get("ids", []))
        except (OSError, ValueError):
            seen = set()
        new = [f for f in facts if f["id"] not in seen]
        if mark and new:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"ids": sorted(seen | {f["id"] for f in facts})}, fh)
            os.replace(tmp, path)

    def when(f):
        return (f.get("receipts") or [{}])[0].get("date") or ""
    return sorted(new, key=when, reverse=True)


def _md_line(f):
    quote = (f.get("said") or "").strip()
    date = (f.get("receipts") or [{}])[0].get("date", "")
    bits = [f'"{quote}"'] if quote else []
    if date:
        bits.append(date)
    if (f.get("mentions") or 0) > 1:
        bits.append(f"said {f['mentions']}x")
    text = f.get("text") or f"{f['attribute']}: {f['value']}"
    return f"- {text} ({', '.join(bits)}) `{f['id']}`" if bits else f"- {text} `{f['id']}`"


def memory_groups():
    """-> (owner, [(section title, facts newest first)]) -- the grouping
    MEMORY.md and the browser share."""
    mem = _ensure_loaded()
    owner = getattr(mem, "owner", None) or os.environ.get("SOURCEDRECALL_OWNER")
    facts = _all_facts(mem)
    def by_date(f):
        return (f.get("receipts") or [{}])[0].get("date", "")
    # 2026-10-02: facts bound to a project (its world, and work statements
    # made in it) are listed under that project
    nodes = {}
    for store in (mem.g.nodes, mem.g.provisional):
        for nd in store.values():
            nodes[mem._fact(nd)["id"]] = nd
    def _project(f):
        nd = nodes.get(f["id"])
        return mem.project_of(nd) if nd is not None else None
    live = [f for f in facts if f["_tier"] != "hearsay" and f.get("current") is not False]
    passing = [f for f in live if f.get("passing")]
    live = [f for f in live if not f.get("passing")]
    by_project = {}
    for f in live:
        pr = _project(f)
        if pr:
            by_project.setdefault(pr, []).append(f)
    unbound = [f for f in live if not _project(f)]
    # 2026-10-05: standing instructions to the assistant get their own
    # section, first, where they are easy to see and to remove
    instr = [f for f in live if f.get("attribute") == "instruction"]
    unbound = [f for f in unbound if f.get("attribute") != "instruction"]
    about = [f for f in unbound if _owner_subject(f.get("text"), owner)]
    world = [f for f in unbound if not _owner_subject(f.get("text"), owner)]
    gone = [f for f in facts if f["_tier"] != "hearsay" and f.get("current") is False]
    heard = [f for f in facts if f["_tier"] == "hearsay"]
    groups = [("What you have asked the assistant to always do", instr),
              ("About you", about), ("No longer true", gone),
              ("Other things you mentioned", world)]
    for proj in sorted(by_project):
        groups.append((f"Project: {os.path.basename(proj) or proj} ({proj})",
                       by_project[proj]))
    groups.append(("Said in passing (left out of the summary after a few days)",
                   passing))
    groups.append(("Said by the assistant, never confirmed by you", heard))
    return owner, [(t, sorted(g, key=by_date, reverse=True)) for t, g in groups if g]


def export_markdown(path=None):
    """Write the whole memory as Markdown and return the path. Grouped into
    what the user said about themselves, what is no longer true, other
    things they mentioned, and what the assistant said that they never
    confirmed."""
    owner, groups = memory_groups()
    lines = [f"# Memory{': ' + owner if owner else ''}", "",
             "Generated by sourcedrecall from your conversations. Each line is a "
             "summary, then your exact words and the date. To remove one, run "
             "`sourcedrecall-memory forget <id>` or ask your assistant to forget "
             "it. Editing this file does not change the memory; it is rewritten "
             "after every change.", ""]
    for title, group in groups:
        lines += [f"## {title}", ""]
        lines += [_md_line(f) for f in group]
        lines.append("")
    notes = _load_notes()
    if notes:
        # 2026-10-05: notes written by the user's own model (opt-in), each
        # with an id so it can be forgotten like any fact
        lines += ["## Notes written by your model (from your conversations)", ""]
        for r in sorted(notes, key=lambda r: str(r.get("date") or ""), reverse=True):
            lines.append(f"- {r['text']}  [{r.get('date') or ''} · id `{_note_id(r)}`]")
        lines.append("")
    if not groups and not notes:
        lines += ["Nothing stored yet.", ""]
    path = path or memory_file()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    os.replace(tmp, path)
    return path


def _export_quietly():
    try:
        export_markdown()
    except Exception:
        pass        # the file is a view; failing to write it must not fail a write


def _find(fact_id):
    mem = _ensure_loaded()
    for f in _all_facts(mem):
        if f["id"] == fact_id:
            return f
    return None


def _note_id(r):
    import hashlib
    return "n" + hashlib.sha1(f"{r.get('conv')}\x00{r['text']}".encode()).hexdigest()[:5]


def profile_forget(fact_id):
    """Remove one fact by its id (as shown in recall results and MEMORY.md).
    A quoted sentence ("their words", ids starting with "u") can be
    forgotten the same way, and so can a note written by the user's model
    (ids starting with "n")."""
    if str(fact_id).startswith("n"):
        with _lock:
            rows = _load_notes()
            kept = [r for r in rows if _note_id(r) != fact_id]
            if len(kept) != len(rows):
                gone = [r for r in rows if _note_id(r) == fact_id][0]
                _write_notes_file(kept)
                _drop_embeddings()      # its vector must not stay on disk
        if len(kept) != len(rows):
            _export_quietly()
            return {"forgotten": True, "fact": {"id": fact_id, "text": gone["text"],
                                                "said": None}, "applied": "live"}
    f = _find(fact_id)
    if f is None:
        mem = _ensure_loaded()
        u = next((x for x in getattr(mem, "unparsed", []) or []
                  if x.get("id") == fact_id), None)
        if u is None:
            return {"forgotten": False, "error": f"no fact with id {fact_id}"}
        profile_correct("deny", "said", u["value"], exact=True, said=u["value"])
        _export_quietly()
        return {"forgotten": True, "fact": {"id": fact_id, "text": None,
                                            "said": u["value"]},
                "applied": "live"}
    out = profile_correct("deny", f["attribute"], f["value"], exact=True,
                          said=f.get("said"))
    # 2026-10-03: forgetting removes what the fact left behind. A rebuild
    # (from the cache; nothing is re-parsed) recomputes "no longer true"
    # without it -- forgetting "moved to Brunswick" makes "lives in Fitzroy"
    # current again -- and covers the hearsay tier; the names the sentence
    # introduced ("my dog Biscuit") leave the parser's saved world.
    _forget_names(f.get("said"))
    with _lock:
        _reload_locked()
    _export_quietly()
    return {"forgotten": True, "fact": {k: f[k] for k in ("id", "text", "said")},
            "applied": out.get("applied")}


def _notes_path():
    return os.path.join(_data_dir(), "notes.jsonl")


def _load_notes():
    try:
        with open(_notes_path(), encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]
    except (OSError, ValueError):
        return []


def _write_notes_file(rows):
    tmp = _notes_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, _notes_path())
    _state["notes_index"] = None


def _save_notes(conv_id, date, texts, by="model"):
    """A conversation's notes replace its earlier ones (a resumed session is
    re-sent whole)."""
    with _lock:
        rows = [r for r in _load_notes() if r.get("conv") != conv_id]
        rows += [{"conv": conv_id, "date": date, "text": t, "by": by} for t in texts]
        _write_notes_file(rows)


def _notes_for(query, k=6):
    """The model-written notes that match the question best (retrieve_v3)."""
    import retrieve_v3 as _RV3
    with _lock:
        cached = _state.get("notes_index")
        if cached is None:
            rows = _load_notes()
            docs = [{"attr": "", "value": r["text"], "text": r["text"],
                     "date": r.get("date"), "conv": r.get("conv"),
                     "by": r.get("by", "model")} for r in rows]
            cached = _RV3.IndexV3(None, facts=docs) if docs else False
            _state["notes_index"] = cached
    if not cached:
        return []
    hits = _RV3.retrieve_facts_v3(cached, query, k=60, dense_k=30, top_n=k,
                                  with_scores=True)
    return [dict(h, score=sc) for h, sc in hits]


def _drop_notes(said):
    """Forgetting a sentence drops the notes of every conversation it was in:
    a note may restate it."""
    if not said:
        return
    key = re.sub(r"\W+", " ", said).strip().lower()
    if not key:
        return
    try:
        convs = json.load(open(_conversations_path(), encoding="utf-8"))
    except (OSError, ValueError):
        return
    hit = {c.get("uuid") for c in convs
           if any(key in re.sub(r"\W+", " ", str(m.get("text", ""))).lower()
                  for m in c.get("chat_messages") or [])}
    rows = _load_notes()
    kept = [r for r in rows if r.get("conv") not in hit]
    if len(kept) != len(rows):
        _write_notes_file(kept)


def _drop_embeddings():
    """Forgetting removes the saved vectors too (retrieve_v3's on-disk cache):
    an embedding of a forgotten sentence must not stay on disk. They are
    rebuilt from what remains on the next question; the message index is
    rebuilt without the forgotten words."""
    import retrieve_v3 as _RV3
    p = _RV3.emb_cache_path()
    if p:
        _RV3._EMB_CACHE.pop(p, None)
        try:
            os.remove(p)
        except OSError:
            pass
    _state["msg_index"] = None


def _forget_names(sentence):
    if not sentence:
        return
    path = os.path.join(_data_dir(), "world.json")
    try:
        with open(path, encoding="utf-8") as fh:
            world = json.load(fh)
    except (OSError, ValueError):
        return
    import re as _re
    words = {w.lower() for w in _re.findall(r"[A-Za-z]+", sentence)}
    kept = {k: v for k, v in world.items()
            if not (k in words and str(v)[:1].isupper())
            # a link ("=home country": "Sweden") goes with the sentence
            # that named it
            and not (k.startswith("=") and set(str(v).lower().split()) <= words)}
    if len(kept) != len(world):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(kept, fh)
        os.replace(tmp, path)
        ex = _ingest_state.get("extractor")
        if ex is not None:
            for k in set(world) - set(kept):
                ex._world.pop(k, None)


def profile_confirm(fact_id):
    """Mark one fact as confirmed by the user, by its id."""
    f = _find(fact_id)
    if f is None:
        return {"confirmed": False, "error": f"no fact with id {fact_id}"}
    out = profile_correct("confirm", f["attribute"], f["value"], exact=True)
    return {"confirmed": True, "fact": {k: f[k] for k in ("id", "text", "said")},
            "applied": out.get("applied")}
