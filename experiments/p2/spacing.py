"""Spaced corroboration (entry 137: the acquisition frame, BabyLM/
psycholinguistics -- spaced re-exposure consolidates; massed repetition does
not). Pure functions over a node's conversation receipts; no model, no I/O.

A fact's evidence profile:
  n_convs   distinct conversations mentioning it (re-exposures)
  span_days days between first and last mention
  spacing   "spaced"  (>=2 convs across >=7 days)
            "massed"  (>=2 convs within <7 days, or >1 mention in 1 conv)
            "single"  (one conversation)

consolidation(node) in [0,1]: 1 - exp(-(distinct_convs-1) * spread_factor),
where spread_factor saturates with span (a re-mention a month later counts
more than one the next morning). Deterministic, monotone in both signals.
"""
import math
from datetime import datetime

_FMTS = ("%b %d, %Y", "%Y-%m-%d", "%B %d, %Y", "%d %b %Y")


def _parse(d):
    s = str(d).strip()
    for f in _FMTS:
        try:
            return datetime.strptime(s[:20].strip(), f)
        except ValueError:
            continue
    return None


def evidence_profile(node):
    dates = sorted(x for x in (_parse(d) for d in node.get("convs", {}).values())
                   if x)
    n_convs = len(node.get("convs", {}))
    span = (dates[-1] - dates[0]).days if len(dates) >= 2 else 0
    if n_convs <= 1:
        spacing = "single"
    elif span >= 7:
        spacing = "spaced"
    else:
        spacing = "massed"
    return {"n_convs": n_convs, "span_days": span, "spacing": spacing,
            "n_mentions": int(node.get("n_mentions", n_convs))}


def consolidation(node):
    p = evidence_profile(node)
    if p["n_convs"] <= 1:
        return 0.0
    spread = 1.0 - math.exp(-p["span_days"] / 30.0)     # ~0 same-day, ~.6 @1mo
    return 1.0 - math.exp(-(p["n_convs"] - 1) * (0.4 + 0.6 * spread))


def tag(node):
    """Human-readable evidence tag for context lines / MCP payloads."""
    p = evidence_profile(node)
    if p["spacing"] == "single":
        return "unconfirmed(once)"
    if p["spacing"] == "massed":
        return f"repeated x{p['n_convs']} (single period)"
    return f"consolidated x{p['n_convs']} over {p['span_days']}d"
