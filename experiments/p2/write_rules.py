"""Learning-rule memory (entry 140): the write policy learns from the owner's
corrections, instead of only the facts changing.

Entry 137 measured that denied facts skew SPACED -- systematic extraction
errors recur whenever their topic recurs, so correcting the fact once does
not stop the error. What must change is the RULE. Corrections are the only
ground-truth signal we have about extractor mistakes, so we induce write
policy from them:

  DENY rules    (attr, value-key) seen denied -> block that write forever.
                Amplification: one correction blocks every future recurrence.
  RETYPE rules  (attr, value-key) -> new_attr, learned slot repair.
  RISK scores   P(correction | attr): slots the extractor gets wrong often
                need more corroboration before promotion to the asserted tier.

Discipline (same as gists): every rule cites the corrections that produced
it, so the policy is auditable and reversible; a rule is never inferred from
zero evidence, and RISK is smoothed so one bad day cannot condemn a slot.
"""
import json
import os
import re
from collections import Counter, defaultdict

_WORD = re.compile(r"[a-z0-9.]+")


def value_key(value):
    """Content-token key: matches the same error re-worded, not merely the
    identical string ('caltech undergrad' and 'caltech' share a key)."""
    toks = [t for t in _WORD.findall(str(value).lower()) if len(t) > 2]
    return tuple(sorted(set(toks)))


def induce(corrections):
    """corrections: [{action, attribute, value, new_attribute?}] -> rules."""
    deny, retype = {}, {}
    risk_num, risk_den = Counter(), Counter()
    for c in corrections:
        attr = c.get("attribute")
        if not attr:
            continue
        key = value_key(c.get("value", ""))
        risk_num[attr] += 1
        if c.get("action") == "deny" and key:
            deny.setdefault((attr, key), []).append(c)
        elif c.get("action") == "retype" and key and c.get("new_attribute"):
            retype.setdefault((attr, key), (c["new_attribute"], []))[1].append(c)
    return {"deny": deny, "retype": retype, "risk": dict(risk_num),
            "n_corrections": len(corrections)}


def risk_score(rules, attr, prior=3.0):
    """Smoothed P(this slot produces an error). prior=3 pseudo-clean writes,
    so a single correction never condemns a slot outright."""
    n = rules["risk"].get(attr, 0)
    return n / (n + prior)


def decide(rules, attr, value, subject=None):
    """Write-time decision for one candidate fact.
    Returns (action, detail) where action is 'allow' | 'deny' | 'retype'."""
    key = value_key(value)
    if not key:
        return "allow", None
    for (a, k), cs in rules["deny"].items():
        if a == attr and (set(k) <= set(key) or set(key) <= set(k)):
            return "deny", {"rule": f"deny {a}:{'/'.join(k)}",
                            "sources": len(cs)}
    for (a, k), (new_attr, cs) in rules["retype"].items():
        if a == attr and (set(k) <= set(key) or set(key) <= set(k)):
            return "retype", {"new_attribute": new_attr,
                              "rule": f"retype {a}->{new_attr}",
                              "sources": len(cs)}
    return "allow", None


def apply_to_extractions(rules, records):
    """Replay an extraction cache through the learned policy.
    records: iterable of {"f": [ {attribute, value, subject?}, ... ]}.
    Returns stats incl. AMPLIFICATION -- writes stopped per correction."""
    blocked = retyped = seen = 0
    by_rule = Counter()
    for rec in records:
        for f in rec.get("f", []) or []:
            seen += 1
            act, det = decide(rules, f.get("attribute"), f.get("value"))
            if act == "deny":
                blocked += 1
                by_rule[det["rule"]] += 1
            elif act == "retype":
                retyped += 1
                by_rule[det["rule"]] += 1
    n_rules = len(rules["deny"]) + len(rules["retype"])
    return {"extractions_seen": seen, "blocked": blocked, "retyped": retyped,
            "rules": n_rules,
            "amplification": (blocked + retyped) / max(n_rules, 1),
            "per_rule": by_rule.most_common(12)}


def load(path=None):
    path = path or os.path.expanduser("~/rg_private/corrections.jsonl")
    if not os.path.exists(path):
        return induce([])
    return induce([json.loads(l) for l in open(path) if l.strip()])
