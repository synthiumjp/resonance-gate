"""sourcedrecall MCP server (stdio). Exposes four tools over the Resonance
Gate rg-1.1 VSA substrate, plus five profile_* tools (dogfood-v1) that bridge
the p2 world/profile memory (experiments/p2) in as a read+correct+rehydrate
slice — see sourcedrecall/profile_memory.py. NO language model in the
request path — no mouth, no extractor, no judge. The registry's MiniLM
encoder (string->vector) is the only model, loaded lazily for novel writes;
it is non-generative.

Env:
  SOURCEDRECALL_STATE          state dir (default ~/.sourcedrecall)
  SOURCEDRECALL_BROWSER_PORT   read-only browser port (default 7071; 0 disables)
  RG_ROOT                      Resonance Gate repo root (default: repo containing this file)
  RG_MEMORY_DIR                p2 data dir for the profile_* tools (see profile_memory.py)
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


def main():
    if BROWSER_PORT:
        try:
            start_browser(service, BROWSER_PORT)
        except OSError:
            pass  # port busy: run headless rather than fail the MCP server
    mcp.run()


if __name__ == "__main__":
    main()
