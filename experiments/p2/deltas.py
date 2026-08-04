"""Write-time delta synthesis (entry 153): store the CHANGE, not just the values.

Entry 152's correction: the gold RG cannot answer is dominated by facts that
are synthesised across turns -- "no longer X", "changed from X to Y" -- rather
than stated in any one turn. Per-turn atomic extraction cannot produce those
by construction, however good the extractor is.

This writes them at store-build time, deterministically (no model): where a
slot holds two dated values that the store's own clustering says are the same
slot, emit ONE additional fact naming the transition, receipted from both
sides.

Why this differs from timeline.py, which was screened twice and came up
sub-threshold (entries 115, 142): timeline emitted a separate CHANGE HISTORY
*section* appended to the context, competing with the evidence lines for the
composer's attention -- the same shape that made the gist tier fail. A delta
here is a NORMAL STORED FACT: BM25 can rank it, it appears inline as one more
receipted line, and it is retrievable by either of its endpoint values or by
words like "change", "switch", "no longer".
"""
from datetime import datetime

_FMTS = ("%b %d, %Y", "%Y-%m-%d", "%B %d, %Y")

# Slots where a later value replaces an earlier one. Narrative attributes are
# excluded for the reason established in entries 100/109/113: they are
# distinct reflections, not successive values of one slot.
_EPISODIC = {"event", "motivation", "belief", "value", "plan", "feeling",
             "goal", "reflection", "activity", "project"}


def _date(s):
    t = str(s).strip()
    for f in _FMTS:
        try:
            return datetime.strptime(t[:20].strip(), f)
        except ValueError:
            continue
    return None


def _latest(node):
    ds = [d for d in (_date(x) for x in (node.get("convs") or {}).values()) if d]
    return max(ds) if ds else None


def _toks(v, stop):
    import re
    return {t for t in re.findall(r"[a-z0-9]+", str(v).lower())
            if len(t) > 2 and t not in stop}


def synthesise(facts, min_overlap=0.34, stop=None):
    """Return new delta-fact dicts to add to the store.

    Two values belong to the same slot if they share the attribute and enough
    content tokens to be about the same thing, but are not the same value.
    The earlier-dated one is treated as superseded."""
    stop = stop or {"the", "and", "for", "with", "that", "this", "her", "his",
                    "she", "him", "they", "から", "a"}
    by_attr = {}
    for f in facts:
        if f["attr"] in _EPISODIC:
            continue
        if _latest(f) is None:
            continue
        by_attr.setdefault(f["attr"], []).append(f)
    out = []
    for attr, group in by_attr.items():
        group = sorted(group, key=_latest)
        for i, a in enumerate(group):
            ta = _toks(a["value"], stop)
            if not ta:
                continue
            for b in group[i + 1:]:
                tb = _toks(b["value"], stop)
                if not tb or a["value"] == b["value"]:
                    continue
                ov = len(ta & tb) / min(len(ta), len(tb))
                # related enough to be the same slot, distinct enough to be a change
                if not (min_overlap <= ov < 0.8):
                    continue
                da, db = _latest(a), _latest(b)
                if da is None or db is None or da >= db:
                    continue
                convs = dict(a.get("convs") or {})
                convs.update(b.get("convs") or {})
                out.append({
                    "id": f"delta:{attr}={a['value'][:24]}->{b['value'][:24]}",
                    "attr": attr,
                    "value": (f"changed from {a['value']} to {b['value']} "
                              f"by {db.strftime('%b %d, %Y')}"),
                    "tier": "delta",
                    "n_mentions": int(a.get("n_mentions", 1)) + int(b.get("n_mentions", 1)),
                    "convs": convs,
                    "toks": (a.get("toks") or ta) | (b.get("toks") or tb),
                    "sources": [a.get("id"), b.get("id")],
                })
                break        # one delta per earlier value: its next successor
    return out
