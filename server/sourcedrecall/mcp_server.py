"""sourcedrecall MCP server (stdio). Exposes exactly four tools over the
Resonance Gate rg-1.1 VSA substrate. NO language model in the request path —
no mouth, no extractor, no judge. The registry's MiniLM encoder
(string->vector) is the only model, loaded lazily for novel writes; it is
non-generative.

Env:
  SOURCEDRECALL_STATE          state dir (default ~/.sourcedrecall)
  SOURCEDRECALL_BROWSER_PORT   read-only browser port (default 7071; 0 disables)
  RG_ROOT                      Resonance Gate repo root (default: repo containing this file)
"""

import os

from sourcedrecall import substrate_path  # noqa: F401 — sys.path + offline env
from mcp.server.fastmcp import FastMCP

from sourcedrecall.service import MemoryService
from sourcedrecall.browser import start_browser

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


def main():
    if BROWSER_PORT:
        try:
            start_browser(service, BROWSER_PORT)
        except OSError:
            pass  # port busy: run headless rather than fail the MCP server
    mcp.run()


if __name__ == "__main__":
    main()
