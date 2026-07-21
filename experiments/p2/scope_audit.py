"""p2 SCOPED consistency audit: run the LLM-as-energy audit at conversation scale.

Entry 55 exposed the blocking gap: consistency.audit() concatenates every user
turn into ONE prompt, so a real conversation (206 turns = 9693 tokens) overflows
the 8192 context and the audit -- the ONE path that works on real categorical
change -- simply crashes. run_real's 220-char global cap was a stand-in.

This is the proper fix: NEIGHBOURHOOD SCOPING. Statements are packed into
context-budgeted WINDOWS with generous OVERLAP, the audit runs per window, and
proposals are aggregated + verified + deduped. Properties:
  - ALWAYS fits context (never overflows, regardless of conversation length),
  - catches any change whose two endpoints fall in a common window (overlap makes
    that span wide -- the entry-55 rename, turns 15 and 51, lands in one window),
  - a BOUNDED number of LLM calls (len / window-capacity), not one-per-anchor.

HONEST LIMITATION, logged not hidden: a change whose old and new mentions are
farther apart than a window span can be split across windows and missed. Overlap
widens the span but does not make it infinite. True long-range change (mentions
hundreds of turns apart) needs ENTITY-ANCHORED neighbourhoods (group by shared
subject/noun regardless of distance) -- named as the next step, not built here.
The window span is reported so the user sees the coverage bound, never a silent
truncation.
"""

from consistency import audit, verify, _norm


def _windows(sizes, budget, overlap_frac):
    """Index ranges [start,end) packing items (by `sizes`) under `budget`, each
    successive window stepping forward by (1-overlap_frac) of the previous span
    so adjacent windows share ~overlap_frac of their statements."""
    n = len(sizes)
    wins, start = [], 0
    while start < n:
        cur, end = 0, start
        while end < n and cur + sizes[end] <= budget:
            cur += sizes[end]
            end += 1
        if end == start:                 # a single oversized item: take it alone
            end = start + 1
        wins.append((start, end))
        if end >= n:
            break
        step = max(1, int((end - start) * (1.0 - overlap_frac)))
        start += step
    return wins


def audit_scoped(statements, cap=200, budget_chars=16000, overlap_frac=0.34,
                 log=None):
    """Scoped audit over a full conversation. Returns (proposals, info) where
    proposals is the deduped, grounding-verified change list and info reports the
    window count and per-window statement span (the coverage bound).

    cap: per-statement char cap (a pasted document is not a change signal).
    budget_chars: chars per window (~budget/4 tokens; kept well under 8192).
    """
    capped = [s[:cap] for s in statements]
    sizes = [len(s) + 8 for s in capped]          # +numbering/formatting overhead
    wins = _windows(sizes, budget_chars, overlap_frac)
    span = max((b - a for a, b in wins), default=0)
    if log:
        log(f"scoped audit: {len(statements)} statements -> {len(wins)} window(s), "
            f"max span {span} statements (overlap {int(overlap_frac*100)}%)")
    proposals = {}
    for a, b in wins:
        for c in audit(capped[a:b]):
            # verify against the FULL statement set (grounding is conversation-wide)
            if verify(c, statements):
                key = (_norm(c.get("attribute", "")), _norm(c.get("old", "")),
                       _norm(c.get("new", "")))
                proposals.setdefault(key, c)
    info = {"n_statements": len(statements), "n_windows": len(wins),
            "max_window_span": span, "overlap_frac": overlap_frac}
    return list(proposals.values()), info
