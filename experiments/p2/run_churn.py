"""p2: measure store churn on real haystack users.

Reuses the already-extracted haystack_facts.jsonl (no GPU needed). For each
user, replays their facts in session order, recomputes strength at each session
a fact is observed or tested, and feeds the trajectory to ChurnMeter. Then
reports the reliable-change decomposition of the store between an early and a
late session cut.

The point is the "beyond the mean" decomposition: not "the store grew" but how
much of the net is the residual of opposing per-fact movements.
"""

import json
import os
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from strength import strength
from churn import ChurnMeter
from ingest import fact_key


def replay_user(facts):
    """Reconstruct a per-fact strength trajectory across sessions from the
    dumped haystack records. Each record already carries the static evidence
    and the activation/contradiction counts AS OF END of transcript; to get a
    trajectory we recompute strength at each session using the activations that
    had accrued by then. The dump does not store per-session activation, so we
    approximate: a fact observed first at session f, with A total activations
    spread over the sessions after f, accrues them linearly. This is an
    APPROXIMATION and is labelled as such -- a faithful trajectory needs the
    per-session activation log, which run_haystack does not yet dump."""
    meter = ChurnMeter()
    for r in facts:
        k = tuple(r["fact_key"])
        f0 = r["first_session"]
        nsess = r["n_sessions"]
        A = r["activations"]
        C = r["contradictions"]
        ev = r["ev"]
        # sessions at which this fact is 'seen': first, then evenly spaced
        # activation sessions across the remaining span
        span = max(1, nsess - 1 - f0)
        act_sessions = [f0]
        for a in range(A):
            act_sessions.append(min(nsess - 1, f0 + int((a + 1) * span / (A + 1))))
        act_sessions = sorted(set(act_sessions))
        # sample strength at EVERY session from first appearance to end, so a
        # fact carries decay (dormancy since last activation) between the
        # sparse sessions where it is actually revisited. This is what gives
        # the store a downward force and makes churn two-sided.
        for sess in range(f0, nsess):
            acts = sum(1 for s in act_sessions if s <= sess) - 1
            last_act = max([s for s in act_sessions if s <= sess], default=f0)
            dorm = sess - last_act
            cons = C if sess >= act_sessions[-1] else 0     # contradiction lands late
            st = strength(ev, activations=acts, contradictions=cons, dormancy=dorm)
            meter.observe(k, sess, st)
    return meter


def main():
    path = os.path.join(_HERE, "haystack_facts.jsonl")
    facts = [json.loads(l) for l in open(path)]
    by_user = defaultdict(list)
    for f in facts:
        by_user[f["instance"]].append(f)

    print(f"users: {len(by_user)}, facts: {len(facts)}\n")
    agg = defaultdict(int)
    net_res = []
    for u, ff in sorted(by_user.items()):
        nsess = ff[0]["n_sessions"]
        t0, t1 = int(nsess * 0.25), nsess - 1
        meter = replay_user(ff)
        c = meter.churn(t0, t1)
        if c.get("insufficient"):
            continue
        agg["strengthened"] += c["reliable_strengthened"]
        agg["weakened"] += c["reliable_weakened"]
        agg["stable"] += c["stable"]
        net_res.append((c["net_strength_change"], c["gross_upward"], c["gross_downward"]))
        print(f"  user {u:>4}: {c['n']:>2} facts present [t{t0}->t{t1}]  "
              f"str+{c['reliable_strengthened']} str-{c['reliable_weakened']} "
              f"stable {c['stable']}  churn {c['churn_rate']:.2f}  "
              f"net {c['net_strength_change']:+.1f} = up {c['gross_upward']:+.1f} "
              f"/ down {c['gross_downward']:+.1f}  r_xx {c['mean_reliability']:.2f}")

    tot = agg["strengthened"] + agg["weakened"] + agg["stable"]
    print(f"\n=== STORE CHURN (aggregate over {len(net_res)} users, {tot} fact-observations) ===")
    print(f"  reliably strengthened : {agg['strengthened']} ({agg['strengthened']/tot:.1%})")
    print(f"  reliably weakened     : {agg['weakened']} ({agg['weakened']/tot:.1%})")
    print(f"  stable                : {agg['stable']} ({agg['stable']/tot:.1%})")
    print(f"  overall churn rate    : {(agg['strengthened']+agg['weakened'])/tot:.1%}")
    up = sum(u for _, u, _ in net_res); dn = sum(d for _, _, d in net_res); net = sum(n for n, _, _ in net_res)
    print(f"\n  BEYOND THE MEAN: net strength change {net:+.1f} is the residual of")
    print(f"    gross upward {up:+.1f} and gross downward {dn:+.1f}")
    print(f"    -> {abs(dn)/(up+abs(dn)+1e-9):.0%} of gross movement is downward and invisible to the net")


if __name__ == "__main__":
    main()
