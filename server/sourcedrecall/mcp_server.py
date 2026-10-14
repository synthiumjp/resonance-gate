"""sourcedrecall MCP server (stdio). Exposes the profile_* tools (with
SOURCEDRECALL_LEGACY_TOOLS=1 also four substrate tools over the Resonance
Gate rg-1.1 VSA substrate). The profile_* tools (dogfood-v1) that bridge
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
  SOURCEDRECALL_LEGACY_TOOLS   1 = also the rg-1.1 triple tools (remember/recall/update/forget)
"""

import os
import sys

from sourcedrecall import substrate_path  # noqa: F401 — sys.path + offline env
from mcp.server.fastmcp import FastMCP

from sourcedrecall.browser import start_browser
from sourcedrecall import profile_memory as pmem

STATE_DIR = os.environ.get("SOURCEDRECALL_STATE",
                           os.path.expanduser("~/.sourcedrecall"))
BROWSER_PORT = int(os.environ.get("SOURCEDRECALL_BROWSER_PORT", "7071"))
# 2026-10-04: the four triple tools of the rg-1.1 substrate (remember,
# recall, update, forget) are off unless asked for. Next to profile_recall
# and profile_forget they gave a new user two "recall" and two "forget"
# tools, and they load the older substrate at every start.
LEGACY_TOOLS = os.environ.get("SOURCEDRECALL_LEGACY_TOOLS") == "1"

service = None
if LEGACY_TOOLS:
    from sourcedrecall.service import MemoryService
    service = MemoryService(STATE_DIR)
mcp = FastMCP("sourcedrecall")
# 2026-10-13 (clean-install test): initialize reported the mcp library's
# version (1.30.0) as the server's
try:
    from sourcedrecall import __version__ as _VERSION
    mcp._mcp_server.version = _VERSION
except (ImportError, AttributeError):
    pass


# 2026-10-12 (review 3.2): hints the host can act on, so it can ask the user
# before a call that changes or deletes the memory. Older mcp releases have
# no annotations; the tool is registered without them there.
# 2026-10-12 (review 3.11): each tool's description is in every session's
# context. Diagnostics are hidden unless SOURCEDRECALL_ALL_TOOLS=1.
ALL_TOOLS = os.environ.get("SOURCEDRECALL_ALL_TOOLS") == "1"


def _tool(read_only, destructive=False, idempotent=False, extra=False):
    if extra and not ALL_TOOLS:
        return lambda fn: fn
    try:
        from mcp.types import ToolAnnotations
        return mcp.tool(annotations=ToolAnnotations(
            readOnlyHint=read_only, destructiveHint=destructive,
            idempotentHint=idempotent, openWorldHint=False))
    except (ImportError, TypeError):
        return mcp.tool()


def _legacy_tool(fn):
    return mcp.tool()(fn) if LEGACY_TOOLS else fn


@_legacy_tool
def remember(subject: str, relation: str, object: str,
             source: str = "caller-stated") -> dict:
    """Store one explicit structured fact as a (subject, relation, object)
    triple. You pass the structured triple — this server does NOT extract
    facts from text. `source` is provenance: caller-stated (default),
    user-stated, agent-inferred, or tool-derived. The write is echo-checked
    (read back through the gate); a bad write is rejected, not silently kept.
    Returns {stored, record_id, echo_ok}."""
    return service.remember(subject, relation, object, source)


@_legacy_tool
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


@_legacy_tool
def update(subject: str, relation: str, object: str,
           source: str = "caller-stated") -> dict:
    """Explicitly correct a fact: write (subject, relation, object) and
    supersede prior records for that subject under the same or a synonymous
    relation (tombstoned via the supersedes-chain, audit trail retained).
    This is the ONLY path that resolves a conflict by choosing — because you
    asked it to. A passive collision (surfaced by recall) is never resolved
    this way. Returns {updated, new_record_id, superseded:[record_ids]}."""
    return service.update(subject, relation, object, source)


@_legacy_tool
def forget(subject: str, relation: str = None, object: str = None) -> dict:
    """Delete stored facts. With subject only: forget everything about the
    subject. With subject+relation: forget facts under that relation (and its
    synonyms). With subject+relation+object: forget that exact record.
    Records are subtracted and tombstoned (stays deleted). Returns
    {forgotten:[record_ids]}."""
    return service.forget(subject, relation, object)


@_tool(read_only=True, extra=True)
def profile_dynamics() -> dict:
    """How much the memory holds and how recent it is: facts still being mentioned, facts that have faded, and the span of time covered."""
    return pmem.profile_dynamics()


@_tool(read_only=True, extra=True)
def profile_quarantine() -> dict:
    """Statements the memory refused to store because of an earlier correction by the user, each with the correction responsible."""
    return pmem.profile_quarantine()


@_tool(read_only=True)
def profile_conflicts() -> dict:
    """Facts about the user that changed or disagree with no correction settling them, each with a question to ask. If one matters to the conversation, ask the user rather than picking a value; then record the answer with profile_correct."""
    return pmem.profile_conflicts()


@_tool(read_only=True)
def profile_recall(query: str, scope: str = None) -> dict:
    """Find what the user said about something. Returns the matching facts with their dates and the conversations they came from; found=false means nothing stored answers it, so say you don't know. To read the whole conversation behind a fact, pass its conversation_id to profile_rehydrate."""
    return pmem.profile_recall(query, scope)


@_tool(read_only=True)
def profile_check(claim: str, scope: str = None) -> dict:
    """Did the user say this? Use before acting on a detail about the user ("The user lives in Fitzroy"). verdict is said (with since: no longer true, may have changed, or no later change found), contradicted, unconfirmed (only the assistant said it), unclear, or not_found; evidence holds the user's own dated words."""
    return pmem.profile_check(claim, scope)


@_tool(read_only=True)
def profile_context(query: str = None, max_facts: int = None,
                    scope: str = None) -> dict:
    """The memory for a question, ready to read: the user's own dated messages, oldest first, with labels for what is no longer true and for text pasted from someone else. Without a question, a summary of what is known about the user."""
    return pmem.profile_context(query, max_facts, scope)


@_tool(read_only=False, destructive=True)
def profile_correct(action: str, attribute: str, value: str,
                     new_attribute: str = None, exact: bool = False) -> dict:
    """Record the user's correction of a stored fact: deny (it is wrong, drop it), confirm (the user vouches for it) or retype (right value, wrong kind of fact; needs new_attribute). Use only when the user asks."""
    return pmem.profile_correct(action, attribute, value, new_attribute, exact)


@_tool(read_only=True, extra=True)
def profile_status(reload: bool = False) -> dict:
    """Diagnostics: whether the memory is loaded, how many facts it holds, and where it is stored. reload=True rebuilds it from disk."""
    return pmem.profile_status(reload)


@_tool(read_only=True)
def profile_rehydrate(conversation_id: str, max_turns: int = 40,
                       include_assistant: bool = True, scope: str = None) -> dict:
    """The full text of one stored conversation, by the conversation_id that profile_recall gives with each fact. At most max_turns turns (200 at most); include_assistant=False gives only the user's turns."""
    return pmem.rehydrate(conversation_id, max_turns, include_assistant, scope)


@_tool(read_only=False)
def profile_ingest(turns: list[dict], conversation_id: str = None,
                    title: str = None, owner_name: str = None,
                    date: str = None, scope: str = None) -> dict:
    """Store a conversation the hooks did not capture. turns is [{"role": "user"|"assistant", "content": str}, ...], oldest first; date is when it happened (ISO; not in the future). Nothing is generated: a grammar parser reads the user's own words. Standing instructions are not stored from this tool."""
    from sourcedrecall.paths import current_scope
    pmem._not_future(date)
    return pmem.profile_ingest(turns, conversation_id, title, owner_name,
                               date=date, scope=current_scope(scope),
                               instructions=False)


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
        # Not a daemon: a daemon thread cut off mid-load at shutdown aborts
        # the process ("terminate called without an active exception");
        # waiting a few seconds for the load to finish is the clean exit.
        threading.Thread(target=run, name="sourcedrecall-prewarm",
                         daemon=False).start()


@_tool(read_only=False, destructive=True, idempotent=True)
def profile_forget(fact_id: str) -> dict:
    """Forget one stored fact by its id (shown in profile_recall results and MEMORY.md): the sentence it came from is erased. Use when the user asks for something to be forgotten."""
    return pmem.profile_forget(fact_id)


@_tool(read_only=False, idempotent=True)
def profile_confirm(fact_id: str) -> dict:
    """Mark one stored fact as confirmed by the user, by its id."""
    return pmem.profile_confirm(fact_id)


@_tool(read_only=False, idempotent=True, extra=True)
def profile_export() -> dict:
    """Write everything stored to MEMORY.md and return it, so the user can read it."""
    path = pmem.export_markdown()
    return {"path": path, "markdown": open(path, encoding="utf-8").read()}


def _quiet_logs():
    """Model loading logs every step at INFO to stderr, which an MCP client
    shows as server output. Warnings and errors still come through."""
    import logging
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    for name in ("sentence_transformers", "transformers", "stanza",
                 "huggingface_hub"):
        logging.getLogger(name).setLevel(logging.WARNING)


def main():
    _quiet_logs()
    # 2026-10-14: conversations with an assistant (rgx RGX_ASSISTANT_CHAT)
    os.environ.setdefault("RGX_ASSISTANT_CHAT", "1")
    # 2026-10-13: SOURCEDRECALL_STACK_DUMP=<seconds> writes every thread's
    # stack to stderr at that interval, to see where a server is stuck
    dump = os.environ.get("SOURCEDRECALL_STACK_DUMP")
    if dump:
        import faulthandler
        faulthandler.dump_traceback_later(float(dump), repeat=True, file=sys.stderr)
    # 2026-10-13 (clean-install test on Windows): the first profile_context
    # imported numpy lazily inside the running server and hung there for
    # good (the CLI, importing at top level, was fine). Import the compiled
    # libraries in the main thread before serving.
    for mod in ("numpy", "onnxruntime"):
        try:
            __import__(mod)
        except ImportError:
            pass
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
