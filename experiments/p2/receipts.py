"""Receipt operations (entry 147 / roadmap U2): receipts as first-class
objects rather than metadata.

A receipt is (conversation_id, date) -- the evidence that a fact was
actually said, which is what every RG guarantee rests on. Until now receipts
were a dict the store carried around. This module gives them the operations a
memory needs, all of them non-destructive:

  strengthen   re-observation adds a receipt (never overwrites a value)
  salience     decay-weighted evidence: recent receipts count for more than
               old ones, so an unreinforced fact fades in RANKING without
               being deleted. Nothing is ever removed by decay.
  merge        two nodes become one, receipts unioned, absorbed wording kept
  split        one node becomes two, receipts partitioned by predicate --
               the repair path for a cluster that merged wrongly
  invalidate   owner correction marks a node, retaining it for audit

Design rule carried from the rest of the project: no operation destroys
evidence. decay changes weight, invalidate changes status, split preserves
both halves. A store that forgets must still be able to show what it forgot.
"""
import math
from datetime import datetime

_FMTS = ("%b %d, %Y", "%Y-%m-%d", "%B %d, %Y", "%d %b %Y")
HALF_LIFE_DAYS = 365.0     # a receipt is worth half as much a year later


def parse_date(s):
    t = str(s).strip()
    for f in _FMTS:
        try:
            return datetime.strptime(t[:20].strip(), f)
        except ValueError:
            continue
    return None


def receipts(node):
    """[(conv_id, datetime|None)] for a node, oldest first."""
    out = [(c, parse_date(d)) for c, d in (node.get("convs") or {}).items()]
    return sorted(out, key=lambda t: (t[1] or datetime.min))


def anchor(nodes):
    """The 'now' a store is read at: its most recent receipt. Benchmark
    streams run on synthetic future dates, so wall-clock now is meaningless
    -- recency has to be relative to the stream itself."""
    latest = None
    for n in nodes:
        for _, d in receipts(n):
            if d and (latest is None or d > latest):
                latest = d
    return latest


def strengthen(node, conv_id, date):
    """Re-observation: one more receipt, one more mention. Value untouched."""
    node.setdefault("convs", {})
    if conv_id not in node["convs"]:
        node["convs"][conv_id] = date
        node["n_mentions"] = int(node.get("n_mentions", 0)) + 1
    return node


def salience(node, now=None, half_life=HALF_LIFE_DAYS):
    """Decay-weighted evidence mass: sum over receipts of 0.5**(age/half_life).
    Many recent receipts > many old ones > one old one. Undated receipts count
    as 1.0 (we cannot age what we cannot date, and refuse to guess)."""
    total = 0.0
    for _, d in receipts(node):
        if d is None or now is None:
            total += 1.0
        else:
            age = max(0.0, (now - d).days)
            total += 0.5 ** (age / half_life)
    return total


def merge(a, b):
    """One node absorbs another: receipts unioned, mentions summed, the
    absorbed wording retained as an auditable variant."""
    keep, gone = (a, b) if a.get("n_mentions", 1) >= b.get("n_mentions", 1) else (b, a)
    out = dict(keep)
    out["convs"] = dict(keep.get("convs") or {})
    out["convs"].update(gone.get("convs") or {})
    out["n_mentions"] = int(keep.get("n_mentions", 1)) + int(gone.get("n_mentions", 1))
    out["variants"] = list(keep.get("variants") or []) + [gone["value"]] \
        + list(gone.get("variants") or [])
    return out


def split(node, predicate):
    """Undo a wrong merge: partition receipts by predicate(conv_id, date).
    Returns (matching, remainder), both retaining full provenance. Either may
    be None if the partition is empty -- a split that loses evidence is a bug,
    so mention counts are recomputed from the receipts themselves."""
    hit, miss = {}, {}
    for c, d in (node.get("convs") or {}).items():
        (hit if predicate(c, parse_date(d)) else miss)[c] = d
    def _mk(convs):
        if not convs:
            return None
        n = dict(node)
        n["convs"] = convs
        n["n_mentions"] = len(convs)
        n["split_from"] = node.get("id")
        return n
    return _mk(hit), _mk(miss)


def invalidate(node, reason, by="owner"):
    """Mark a node invalid, retaining it and its receipts for audit."""
    n = dict(node)
    n["invalid"] = {"reason": reason, "by": by}
    return n


def dynamics(nodes, now=None):
    """Store-level report for profile_status: how this memory is aging."""
    now = now or anchor(nodes)
    sal = [salience(n, now) for n in nodes]
    dated = [d for n in nodes for _, d in receipts(n) if d]
    fresh = sum(1 for s in sal if s >= 0.5)
    faded = sum(1 for s in sal if s < 0.1)
    return {
        "facts": len(nodes),
        "read_as_of": now.strftime("%b %d, %Y") if now else None,
        "receipts": sum(len(receipts(n)) for n in nodes),
        "span_days": (max(dated) - min(dated)).days if len(dated) > 1 else 0,
        "fresh": fresh,                 # salience >= 0.5: actively reinforced
        "faded": faded,                 # salience < 0.1: retained, low weight
        "invalidated": sum(1 for n in nodes if n.get("invalid")),
        "mean_salience": sum(sal) / max(len(sal), 1),
    }
