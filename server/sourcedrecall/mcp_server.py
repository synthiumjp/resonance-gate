"""sourcedrecall MCP server (stdio). Exposes four substrate tools over the Resonance
Gate rg-1.1 VSA substrate, plus nine profile_* tools (dogfood-v1) that bridge
the p2 world/profile memory (experiments/p2) in as a read+correct+rehydrate+
ingest slice — see sourcedrecall/profile_memory.py. NO language model
anywhere in this server, ingestion included — no mouth, no extractor that
samples, no judge. profile_ingest's extractor is rgx, a deterministic parser
(grammar rules over a dependency parse), not an LLM: it never generates text,
it only lifts facts already present in the turn's own words. The registry's
MiniLM encoder (string->vector) is the only *model* anywhere in this file,
loaded lazily for novel writes on the four substrate tools; it is
non-generative (embeds strings, invents nothing).

Env:
  SOURCEDRECALL_STATE          state dir (default ~/.sourcedrecall)
  SOURCEDRECALL_BROWSER_PORT   read-only browser port (default 7071; 0 disables)
  RG_ROOT                      Resonance Gate repo root (default: repo containing this file)
  RG_MEMORY_DIR                conversation-memory data dir for the profile_* tools
                               (default when run as a server: $SOURCEDRECALL_STATE/conversations)
  RG_PREWARM                   0 = do not load models in the background at startup
  SOURCEDRECALL_OWNER          fallback owner_name for profile_ingest (see profile_memory.py)
"""

import os

from sourcedrecall import substrate_path  # noqa: F401 — sys.path + offline env
from mcp.server.fastmcp import FastMCP

from sourcedrecall.service import MemoryService
from sourcedrecall.browser import start_browser
from sourcedrecall import profile_memory as pmem

STATE_DIR = os.environ.get("SOURCEDRECALL_STATE",
                           os.path.expanduser("~/.sourcedrecall"))
BROWSER_PORT = int(os.environ.get("SOURCEDRECALL_BROWSER_PORT", "7071"))

service = MemoryService(STATE_DIR)
mcp = FastMCP("sourcedrecall")


@mcp.tool()
def remember(subject: str, relation: str, object: str,
             source: str = "caller-stated") -> dict:
    """Store one explicit structured fact as a (subject, relation, object)
    triple. You pass the structured triple — this server does NOT extract
    facts from text. `source` is provenance: caller-stated (default),
    user-stated, agent-inferred, or tool-derived. The write is echo-checked
    (read back through the gate); a bad write is rejected, not silently kept.
    Returns {stored, record_id, echo_ok}."""
    return service.remember(subject, relation, object, source)


@mcp.tool()
def recall(query: str, top_k: int = 10) -> dict:
    """Recall stored facts about `query` (resolved as a subject/entity).
    Returns {resolved, facts:[{subject,relation,object,source,record_id,
    confidence:{b,d,u}}], conflict}. If nothing is stored that resolves,
    returns resolved=false with an empty list — an honest "I don't have
    that", never a fabricated guess. If contradictory facts are stored under
    synonymous keys, conflict=true and BOTH facts are returned with an
    advisory resolution_hint {by_recency, by_resolution}; the server does NOT
    choose between them."""
    return service.recall(query, top_k)


@mcp.tool()
def update(subject: str, relation: str, object: str,
           source: str = "caller-stated") -> dict:
    """Explicitly correct a fact: write (subject, relation, object) and
    supersede prior records for that subject under the same or a synonymous
    relation (tombstoned via the supersedes-chain, audit trail retained).
    This is the ONLY path that resolves a conflict by choosing — because you
    asked it to. A passive collision (surfaced by recall) is never resolved
    this way. Returns {updated, new_record_id, superseded:[record_ids]}."""
    return service.update(subject, relation, object, source)


@mcp.tool()
def forget(subject: str, relation: str = None, object: str = None) -> dict:
    """Delete stored facts. With subject only: forget everything about the
    subject. With subject+relation: forget facts under that relation (and its
    synonyms). With subject+relation+object: forget that exact record.
    Records are subtracted and tombstoned (stays deleted). Returns
    {forgotten:[record_ids]}."""
    return service.forget(subject, relation, object)


@mcp.tool()
def profile_dynamics() -> dict:
    """Memory-aging report: how many stored facts are actively reinforced,
    how many have faded (retained, lower weight), total receipts, and the
    span they cover. Use when the user asks how much the memory holds, how
    current it is, or what it has stopped hearing about."""
    return pmem.profile_dynamics()


@mcp.tool()
def profile_quarantine() -> dict:
    """Writes blocked at ingest by rules learned from the owner's own
    corrections, each with the rule responsible. Use when the user asks why
    something is missing from memory, or to review whether a learned rule has
    aged badly (e.g. they denied a job title once but now hold it)."""
    return pmem.profile_quarantine()


@mcp.tool()
def profile_conflicts() -> dict:
    """Open memory conflicts: slots where the user's stored values evolved or
    disagree and no correction has resolved them. Each item carries a
    ready-to-ask clarifying question -- when one is relevant to the current
    conversation, ASK it rather than silently picking a value. Resolving a
    conflict: call profile_correct with the outdated value."""
    return pmem.profile_conflicts()


@mcp.tool()
def profile_recall(query: str) -> dict:
    """Recall from the p2 world/profile memory (a validated, non-hallucinating
    LIVING memory built by replaying a cached extraction over the user's own
    conversation history — cache-only, no LLM call in this request path).
    Returns Memory.recall()'s dict verbatim: {found, abstain, query,
    asserted:[...], wired:[...], unconfirmed:[...]} — each fact carries its
    mention count, receipts (dates + conversation titles + conversation_id),
    and status (corroborated / unconfirmed-single-mention / owner-confirmed);
    wired facts also carry the receipted co-occurrence path that connects
    them. If nothing corroborated matches, abstain=true — an honest "never
    seen", never a guess. Plus source="rg-p2-memory". Pass a receipt's
    conversation_id to profile_rehydrate() to pull the verbatim source
    conversation back into context."""
    return pmem.profile_recall(query)


@mcp.tool()
def profile_context(query: str = None, max_facts: int = 15) -> dict:
    """The verbatim, receipted text block for prompt injection — every line is
    a stored fact with its mention count, and the block carries the standing
    instruction that anything about the user NOT listed is unknown and must
    not be invented. With no query, the top of the corroborated profile;
    with a query, that recall's neighbourhood. Returns {"block": <str>}."""
    return pmem.profile_context(query, max_facts)


@mcp.tool()
def profile_correct(action: str, attribute: str, value: str,
                     new_attribute: str = None, exact: bool = False) -> dict:
    """Owner correction over the p2 memory: action is one of deny (the fact is
    wrong — drop it and its edges), confirm (owner-vouched — promote a
    single-mention fact to asserted), or retype (right fact, wrong attribute —
    requires new_attribute). Always appended as one line to the data dir's
    corrections.jsonl (ground truth, never inference). deny/confirm also apply
    immediately to the live graph (applied="live"); retype needs a fact-level
    rebuild and only takes effect on the next reload (applied="on-reload",
    needs_reload=true — see profile_status(reload=True))."""
    return pmem.profile_correct(action, attribute, value, new_attribute, exact)


@mcp.tool()
def profile_status(reload: bool = False) -> dict:
    """Health/shape of the loaded p2 memory: {loaded, asserted, provisional,
    edges, audit_pass, needs_reload, uncached_turns, data_dir}. audit_pass is
    the non-hallucination graph audit (every edge = real receipted
    co-occurrence, nothing more, nothing less); it's O(n^2) so it's computed
    once and cached, not recomputed per call. Pass reload=True to rebuild from
    the cache + corrections.jsonl on disk first (picks up a pending retype)."""
    return pmem.profile_status(reload)


@mcp.tool()
def profile_rehydrate(conversation_id: str, max_turns: int = 40,
                       include_assistant: bool = True) -> dict:
    """Rehydrate a receipt into the verbatim conversation slice it points at
    -- the page-fault half of the virtual context window (the p2 fact graph
    is the page table; conversations.json, the raw export, is the backing
    store). Intended loop: profile_recall -> take a fact's
    receipts[].conversation_id -> profile_rehydrate(conversation_id) to pull
    the exact source turns back into context, verbatim, instead of trusting
    the compressed fact alone.

    Returns {found, conversation_id, title, date, n_turns_total,
    turns:[{role, text}], truncated}. turns is capped at max_turns (oldest-
    first order as stored; truncated=true if the conversation has more);
    include_assistant=False restricts to the human's own turns; each turn's
    text is capped at 2000 chars. An unknown conversation_id is NEVER
    guessed or fuzzy-matched -- returns {found: false, error: "no such
    conversation in the backing store"}, the same non-hallucination contract
    as profile_recall's abstain, one layer down."""
    return pmem.rehydrate(conversation_id, max_turns, include_assistant)


@mcp.tool()
def profile_ingest(turns: list[dict], conversation_id: str = None,
                    title: str = None, owner_name: str = None,
                    date: str = None) -> dict:
    """Turn ONE conversation into new profile-memory facts -- DETERMINISTIC,
    NO LANGUAGE MODEL: facts are lifted by rgx, a grammar-rule parser over a
    dependency parse, not sampled or generated by an LLM. A fact is either
    grounded in the turn's own words or it is not emitted; nothing here can
    invent content. `turns` is one dialogue: [{"role": "user"|"assistant",
    "content": str}, ...], oldest first. `conversation_id` groups repeated
    calls into the same conversation (a fresh uuid4 if omitted); `title`
    names it; `owner_name` is whose profile this is (falls back to env
    SOURCEDRECALL_OWNER, then an existing profile's own discovered name, then
    None).

    Appends the turns to conversations.json, extracts every turn not already
    in the extraction cache (a turn already seen is skipped, never
    re-extracted -- ingesting the same conversation twice is a safe no-op the
    second time), appends the new cache lines, and reloads the live memory
    so the very next profile_recall/profile_context/profile_status sees the
    result. Every fact this produces still carries the same receipts
    (session/turn/role, and once wired, conversation_id + date) as any other
    fact in this store -- ingestion doesn't relax the provenance contract, it
    only adds to what's receipted.

    An assistant turn's clause reporting a claim ABOUT the user (e.g. "I
    remember you mentioning...") is tagged hearsay: receipted, never
    asserted or volunteered as the user's own fact (see profile_recall's
    'hearsay' key).

    Returns {conversation_id, turns: <non-empty turns seen>,
    facts: <new non-hearsay facts>, hearsay: <new hearsay facts>,
    skipped_cached: <turns already cached, not re-extracted>,
    model_calls: 0} -- model_calls is always 0, the receipt that no model
    call happened anywhere in this path.

    `date` (ISO, e.g. "2026-09-25" or "2026-09-25T14:00:00Z") is when the
    conversation HAPPENED; default now. Pass it when importing older chats:
    which of two statements is newer decides what is "no longer true"."""
    return pmem.profile_ingest(turns, conversation_id, title, owner_name,
                               date=date)


def _default_memory_dir():
    from sourcedrecall.paths import default_memory_dir
    return default_memory_dir()


def _prewarm():
    """Load the retrieval and conflict models (and the parser, when the owner
    is known) in the background at startup. The new-user test measured a 4 s
    stall on the first question after a restart, with no message; the user's
    first question is the worst moment for it. RG_PREWARM=0 skips this."""
    def run():
        try:
            pmem.profile_status()            # loads the store from disk
        except Exception:
            pass
        try:
            import retrieve_v3
            retrieve_v3._models()            # bge-small + cross-encoder
        except Exception:
            pass
        if os.environ.get("RG_NLI") != "0":
            try:
                import consolidate
                consolidate._nli()
            except Exception:
                pass
        owner = os.environ.get("SOURCEDRECALL_OWNER")
        if owner:
            try:
                pmem._get_extractor(owner)._parser()   # stanza
            except Exception:
                pass
    if os.environ.get("RG_PREWARM") != "0":
        import threading
        threading.Thread(target=run, name="sourcedrecall-prewarm",
                         daemon=True).start()


def main():
    _default_memory_dir()
    _prewarm()
    if BROWSER_PORT:
        try:
            start_browser(service, BROWSER_PORT)
        except OSError:
            pass  # port busy: run headless rather than fail the MCP server
    mcp.run()


if __name__ == "__main__":
    main()
