"""Memory operation log (entry 157): the lifecycle of the store as events.

RG already carries four of the five fields a lifecycle benchmark asks for --
trigger (which conversation, when), target (which node), scope (attribute and
subject) and supporting evidence (receipts, rehydratable to the verbatim
turn). The missing one is STATE TRANSITION: we hold the current state but
never recorded how it got there.

Entry 154 established that transitions cannot be RECONSTRUCTED from a
finished store -- four attempts, all failed, because a genuine substitution
replaces its own tokens and no lexical or embedding criterion recovers the
pairing. That result does not apply here. At ingest the transition is not
inferred, it is OBSERVED: this slot held A, this turn supplies B.

Operations recorded:
  CREATE      a value enters the store for the first time
  STRENGTHEN  an existing value gains a receipt (re-observation)
  PROMOTE     provisional -> asserted (corroboration threshold crossed)
  SUPERSEDE   a single-valued slot receives a different value
  INVALIDATE  an owner correction denies a value
  QUARANTINE  a learned write rule blocked a candidate

Every entry is append-only and carries its own evidence, so the log is
auditable on the same terms as the facts themselves: nothing here is
inferred after the fact.
"""
import json
import os
from collections import Counter

OPS = ("CREATE", "STRENGTHEN", "PROMOTE", "SUPERSEDE", "INVALIDATE", "QUARANTINE")


class OperationLog:
    """Append-only record of how the store changed."""

    def __init__(self, path=None):
        self.path = os.path.expanduser(path) if path else None
        self.entries = []

    def record(self, op, target, conv=None, date=None, before=None, after=None,
               attr=None, subject=None, evidence=None, rule=None):
        assert op in OPS, op
        e = {"op": op, "target": target, "attr": attr, "subject": subject,
             "trigger": {"conversation": conv, "date": date},
             "transition": {"before": before, "after": after},
             "evidence": evidence or ([conv] if conv else []),
             "seq": len(self.entries)}
        if rule:
            e["rule"] = rule
        self.entries.append(e)
        return e

    # --- queries the product and a lifecycle benchmark both need -----------
    def history(self, target):
        """Every operation that touched one memory item, in order."""
        return [e for e in self.entries if e["target"] == target]

    def slot_history(self, attr):
        """Every operation on an attribute -- the slot's trajectory."""
        return [e for e in self.entries if e["attr"] == attr]

    def transitions(self):
        """Only the entries that changed a value (what 'update' means)."""
        return [e for e in self.entries if e["op"] in ("SUPERSEDE", "INVALIDATE")]

    def as_of(self, date_key):
        """Operations up to a date (string-comparable ISO or parsed elsewhere)."""
        return [e for e in self.entries
                if not e["trigger"]["date"] or str(e["trigger"]["date"]) <= str(date_key)]

    def summary(self):
        c = Counter(e["op"] for e in self.entries)
        return {"operations": len(self.entries),
                **{op.lower(): c.get(op, 0) for op in OPS},
                "items_touched": len({e["target"] for e in self.entries})}

    def flush(self):
        if not self.path:
            return 0
        with open(self.path, "a") as f:
            for e in self.entries:
                f.write(json.dumps(e) + "\n")
        n = len(self.entries)
        self.entries = []
        return n


def build_from_store(nodes, quarantined=None, corrections=None):
    """Derive the log for an ALREADY-BUILT store.

    Honest limitation, stated because entry 154 is the reason this module
    exists: from a finished store only CREATE / STRENGTHEN / PROMOTE are
    recoverable -- they are implied by receipts and tier. SUPERSEDE cannot be
    recovered retroactively (that is precisely what four attempts failed to
    do); it must be captured at ingest. QUARANTINE and INVALIDATE come from
    the write-policy and correction records, which ARE retained.
    """
    log = OperationLog()
    for nd in nodes:
        convs = sorted((nd.get("convs") or {}).items(), key=lambda kv: str(kv[1]))
        for i, (conv, date) in enumerate(convs):
            if i == 0:
                log.record("CREATE", nd["id"], conv=conv, date=date,
                           attr=nd.get("attr"), after=nd.get("value"))
            else:
                log.record("STRENGTHEN", nd["id"], conv=conv, date=date,
                           attr=nd.get("attr"), after=nd.get("value"))
        if nd.get("tier") == "asserted" and len(convs) >= 2:
            log.record("PROMOTE", nd["id"], conv=convs[1][0], date=convs[1][1],
                       attr=nd.get("attr"), before="provisional", after="asserted")
        if nd.get("invalid"):
            log.record("INVALIDATE", nd["id"], attr=nd.get("attr"),
                       before=nd.get("value"), after=None,
                       rule=nd["invalid"].get("reason"))
    for q in (quarantined or []):
        log.record("QUARANTINE", f"{q.get('attribute')}={q.get('value')}",
                   conv=q.get("conv"), date=q.get("date"),
                   attr=q.get("attribute"), after=None, rule=q.get("rule"))
    return log
