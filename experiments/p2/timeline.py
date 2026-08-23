"""Store-derived CHANGE HISTORY for the evidence layer (entry 113 follow-up).

Line re-clustering starved Dynamic Update questions (gold reachable 16/20,
chained 2/20) because formatted context lines carry one date and one wording.
The store keeps more: each node's `toks` is the token UNION of every merged
variant, and `convs` receipts date every conversation the value appeared in.
Chains are built from same-attr node groups linked on that richer signal, and
only where the store actually shows evolution (>=2 distinct dated values) --
so the section is structure-triggered: it appears when the evidence warrants
it, never because question phrasing matched a keyword list.

Emits, for slots present among the retrieved facts:
  CHANGE HISTORY (...):
  attr: value1 (dates...) -> value2 (dates...)
"""
from datetime import datetime

from wire import _tokens

# Attrs that never form supersession chains: events are episodic (a later
# event does not replace an earlier one), and narrative attrs (motivation,
# belief, ...) are reflections -- distinct statements loosely sharing tokens,
# not values of one evolving slot (entry 100/109/113: generic narrative
# attributes defeat every slot-identity heuristic tried so far).
_EPISODIC_ATTRS = {"event", "motivation", "belief", "value", "plan",
                   "feeling", "goal", "reflection"}
_LINK_MIN = 0.5                      # token-union overlap vs the smaller set


def _parse_date(s):
    for fmt in ("%b %d, %Y", "%Y-%m-%d", "%B %d, %Y"):
        try:
            return datetime.strptime(str(s).strip(), fmt)
        except ValueError:
            continue
    return datetime.min


def node_dates(nd):
    """Sorted real dates from the node's conversation receipts."""
    return sorted(_parse_date(d) for d in nd["convs"].values())


def _linked(a, b):
    ta, tb = a.get("toks") or _tokens(a["value"]), b.get("toks") or _tokens(b["value"])
    if not ta or not tb:
        return False
    return len(ta & tb) / min(len(ta), len(tb)) >= _LINK_MIN


def slot_chains(facts):
    """Group same-attr facts into linked evolution chains; return only chains
    with >=2 distinct values, ordered oldest->newest by earliest receipt."""
    by_attr = {}
    for nd in facts:
        if nd["attr"] in _EPISODIC_ATTRS:
            continue
        by_attr.setdefault(nd["attr"], []).append(nd)
    chains = []
    for attr, nds in by_attr.items():
        groups = []
        for nd in nds:
            for g in groups:
                if any(_linked(nd, m) for m in g):
                    g.append(nd)
                    break
            else:
                groups.append([nd])
        for g in groups:
            if len({m["value"] for m in g}) < 2:
                continue
            g.sort(key=lambda m: (node_dates(m) or [datetime.min])[0])
            chains.append((attr, g))
    return chains


def _fmt_dates(nd):
    ds = [d for d in node_dates(nd) if d != datetime.min]
    if not ds:
        return "undated"
    if len(ds) == 1:
        return ds[0].strftime("%b %d, %Y")
    return f"{ds[0].strftime('%b %d, %Y')} .. {ds[-1].strftime('%b %d, %Y')}"


def change_history(mem, retrieved_facts):
    """CHANGE HISTORY section for the slots present in `retrieved_facts`
    (list of node dicts, e.g. what retrieve.retrieve ranked), built from the
    FULL store so a superseded value missing from top-k still appears in its
    chain. Empty string when no retrieved slot shows evolution."""
    store = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
    retrieved_ids = {nd["id"] for nd in retrieved_facts}
    chains = [c for c in slot_chains(store)
              if any(m["id"] in retrieved_ids for m in c[1])]
    if not chains:
        return ""
    # entry 244 follow-up: slot_chains() groups on the raw attr key, which
    # for rgx facts can be a predicate-key fragment ("openness_to_..."),
    # not just canonical slots ("employer"). Prefer each member's own
    # proposition text over the bare "attr: value" atom -- when the chain
    # carries text, drop the attr-as-header entirely (it would leak the
    # predicate key) and let each dated point stand as its own sentence.
    lines = []
    for attr, g in chains:
        if any(m.get("text") for m in g):
            lines.append(" -> ".join(
                f"{m.get('text') or attr + ': ' + m['value']} ({_fmt_dates(m)})"
                for m in g))
        else:
            lines.append(f"{attr}: " + " -> ".join(
                f"{m['value']} ({_fmt_dates(m)})" for m in g))
    return ("\nCHANGE HISTORY (attributes whose stored value evolved, "
            "oldest to newest; the last value is current):\n" + "\n".join(lines))


TIMELINE_RULE = ("\n4. A CHANGE HISTORY section, when present, lists attributes whose value "
 "changed over time, oldest to newest; the LAST value in a chain is the current one. For "
 "questions about the current state, answer with the last value. For questions about what "
 "changed, or about an earlier time, use the dated chain: state the relevant value(s) and "
 "date(s) directly from it.")
