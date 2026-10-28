"""sourcedrecall MCP server (stdio). Exposes the profile_* tools over the
conversation memory (experiments/p2, bridged in by sourcedrecall/profile_memory.py).
NO language model anywhere in this server, ingestion included: no extractor
that samples, no judge. profile_ingest's extractor is rgx, a deterministic
parser (grammar rules over a dependency parse), not an LLM: it never
generates text, it only lifts facts already present in the turn's own words.
2026-10-14: the four rg-1.1 triple tools (remember/recall/update/forget,
off by default since 2026-10-04) are removed with the substrate they used.

Env:
  SOURCEDRECALL_STATE          state dir (default ~/.sourcedrecall)
  SOURCEDRECALL_BROWSER_PORT   read-only browser port (default 7071; 0 disables)
  RG_ROOT                      repository checkout to load the memory code from (default: the one containing this file)
  RG_MEMORY_DIR                conversation-memory data dir for the profile_* tools
                               (default when run as a server: $SOURCEDRECALL_STATE/conversations)
  RG_PREWARM                   0 = do not load models in the background at startup
  SOURCEDRECALL_OWNER          fallback owner_name for profile_ingest (see profile_memory.py)
"""

import os
import sys

import sourcedrecall.paths  # noqa: F401 — offline mode first
from mcp.server.fastmcp import FastMCP

from sourcedrecall.browser import start_browser
from sourcedrecall import profile_memory as pmem

BROWSER_PORT = int(os.environ.get("SOURCEDRECALL_BROWSER_PORT", "7071"))
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
    return pmem.profile_correct(action, attribute, value, new_attribute, exact, via="mcp")


@_tool(read_only=True, extra=True)
def profile_status(reload: bool = False) -> dict:
    """Diagnostics: whether the memory is loaded, how many facts it holds, and where it is stored. reload=True rebuilds it from disk."""
    return pmem.profile_status(reload)


@_tool(read_only=True)
def history_search(query: str, all_projects: bool = False, max_results: int = 10,
                   scope: str = None) -> dict:
    """Search past coding sessions in this project: passages of what was said and done (what failed and what fixed it, commands, files edited, why something was decided), each dated. Use it when the user says "last time", "before", "again", "how did we", "why did we", or an error looks familiar. all_projects=True searches every project; profile_rehydrate reads a whole session."""
    return pmem.profile_history(query, scope, max(1, min(int(max_results), 25)),
                                all_projects)


@_tool(read_only=True)
def profile_rehydrate(conversation_id: str, max_turns: int = 40,
                       include_assistant: bool = True, scope: str = None) -> dict:
    """The full text of one stored conversation, by the conversation_id that profile_recall gives with each fact. At most max_turns turns (200 at most); include_assistant=False gives only the user's turns."""
    return pmem.rehydrate(conversation_id, max_turns, include_assistant, scope)


# 2026-10-28 (review H5): marked destructive so the host asks the user
# first (it stores words as the user's); always a new conversation, never
# turns added to one the hooks stored
@_tool(read_only=False, destructive=True)
def profile_ingest(turns: list[dict], title: str = None, owner_name: str = None,
                    date: str = None, scope: str = None) -> dict:
    """Store a conversation the hooks did not capture. turns is [{"role": "user"|"assistant", "content": str}, ...], oldest first; date is when it happened (ISO; not in the future). Nothing is generated: a grammar parser reads the user's own words. Standing instructions are not stored from this tool."""
    from sourcedrecall.paths import current_scope
    pmem._not_future(date)
    return pmem.profile_ingest(turns, None, title, owner_name,
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
    return pmem.profile_forget(fact_id, via="mcp")


@_tool(read_only=False, destructive=True, idempotent=True)
def profile_confirm(fact_id: str) -> dict:
    """Mark one stored fact as confirmed by the user, by its id."""
    return pmem.profile_confirm(fact_id, via="mcp")


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
            start_browser(None, BROWSER_PORT)
        except OSError:
            pass  # port busy: run headless rather than fail the MCP server
    mcp.run()


if __name__ == "__main__":
    main()
