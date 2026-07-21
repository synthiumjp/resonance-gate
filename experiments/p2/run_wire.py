"""p2 WIRE runner: build the receipted co-occurrence graph over the corroborated
profile and run the non-hallucination acceptance audit on real data.

Reads conversations.json + the existing extraction cache (profile_cache.jsonl,
the 45-min run) -- CACHE-ONLY, no LLM calls; uncached turns are skipped and
counted. Rebuilds the corroborated facts exactly as run_profile_full (same
canon/hygiene/clustering), then:
  1. builds the WireGraph (edges = receipted co-occurrence, gated + weighted)
  2. runs graph.audit()            -- the non-hallucination acceptance test
  3. runs the VSA crosstalk audit  -- resonance proposals without a receipted
                                      edge must ALL be blocked
  4. probes ABSTENTION on queries with no corroborated evidence
  5. writes the UNREDACTED wired report (edges + receipts, hub neighbourhoods)
     next to conversations.json; stdout stays REDACTED.

PRIVACY: same contract as run_profile_full -- quarantined input, redacted stdout,
unredacted report stays local. The run is the registrant's (execution gated).

Usage: run_wire.py <conversations.json> [min_mentions=2] [--query "..."]
"""

import hashlib
import json
import os
import re
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for p in (_HERE, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import run_crosssession as RC
from run_crosssession import redact
from run_belief import _is_prose
from llm_profile import canon_attr
import run_profile_full as PF
from wire import WireGraph, ResonanceIndex

# queries with no corroborated evidence in ANY profile of this kind -- the
# abstention probe must return ABSTAIN on every one, never a guess.
_ABSTAIN_PROBES = [
    "i live in reykjavik", "works at nasa", "allergic to peanuts",
    "favourite opera", "owns a yacht", "born in 1902", "plays the bassoon",
]


def build_facts(path, min_mentions=2):
    """Corroborated facts with receipts, rebuilt from the cache exactly as
    run_profile_full readout (canon + hygiene + clustering). Returns
    (facts, n_convs, titles, n_uncached)."""
    cache_path = os.path.join(os.path.dirname(path), "profile_cache.jsonl")
    cache = {}
    if os.path.exists(cache_path):
        for line in open(cache_path):
            try:
                d = json.loads(line)
                cache[d["h"]] = d["f"]
            except Exception:
                pass
    stream, titles = PF.load_stream_and_titles(path)
    prose = [s for s in stream if _is_prose(s[3])]
    slots = defaultdict(lambda: defaultdict(lambda: {"n": 0, "recs": []}))
    uncached = 0
    for step, uuid, date, text in prose:
        h = hashlib.sha1(text.encode("utf-8")).hexdigest()
        if h not in cache:
            uncached += 1
            continue
        for fct in cache[h]:
            a = canon_attr(fct["attribute"])
            v = re.sub(r"\s+", " ", str(fct["value"]).strip().lower())
            if not v or a in PF._EXCLUDE_ATTR or PF._reject_value(a, v):
                continue
            slots[a][v]["n"] += 1
            slots[a][v]["recs"].append((date, uuid))
    facts = []
    for attr, entries in slots.items():
        for cl in PF._cluster(entries):
            if cl["n"] >= min_mentions:
                facts.append((cl["n"], attr, cl["label"], cl["recs"]))
    facts.sort(reverse=True)
    n_convs = len({u for _, u, _, _ in prose})
    return facts, n_convs, titles, uncached


def _edge_lines(f, g, e, titles, max_recs=4):
    f.write(f"  [{e['weight']:.2f} w, x{e['cooc']} convs] "
            f"{e['a']}  <-->  {e['b']}\n")
    dates = {c: d for nid in (e["a"], e["b"])
             for c, d in g.nodes[nid]["convs"].items()}
    for cid in e["convs"][:max_recs]:
        f.write(f"      {dates.get(cid, '?')}  {titles.get(cid, '')[:66]}\n")
    if len(e["convs"]) > max_recs:
        f.write(f"      (+{len(e['convs']) - max_recs} more shared conversations)\n")


def main():
    path = sys.argv[1]
    args = sys.argv[2:]
    query = None
    if "--query" in args:
        qi = args.index("--query")
        query = args[qi + 1]
        args = args[:qi] + args[qi + 2:]
    min_mentions = int(args[0]) if args else 2

    try:
        u = json.load(open(os.path.join(os.path.dirname(path), "users.json")))[0]
        for tok in re.findall(r"[A-Za-z]{3,}", u.get("full_name", "")):
            RC._EXTRA_REDACT.append(tok)
    except Exception:
        pass

    facts, n_convs, titles, uncached = build_facts(path, min_mentions)
    print(f"corroborated facts (>= {min_mentions} mentions): {len(facts)}  "
          f"over {n_convs} conversations  ({uncached} uncached turns skipped)")

    g = WireGraph.from_facts(facts, n_convs=n_convs)
    degs = sorted((len(g.adj[n]) for n in g.nodes), reverse=True)
    wired = sum(1 for d in degs if d)
    print(f"\n=== WIRE GRAPH ===")
    print(f"nodes {len(g.nodes)}, receipted edges {len(g.edges)}; "
          f"{wired} nodes wired, max degree {degs[0] if degs else 0}, "
          f"median {degs[len(degs)//2] if degs else 0}")

    # 1. the acceptance test: no unsupported link, exhaustive over all pairs
    a = g.audit()
    print(f"\n=== NON-HALLUCINATION AUDIT (all {a['n_pairs_checked']} pairs) ===")
    print(f"{'PASS' if a['pass'] else 'FAIL'}: every edge = real co-occurrence "
          f"(>= {g.min_cooc} shared convs, receipted); violations: "
          f"{len(a['violations'])}")
    for x in a["violations"][:5]:
        print("  VIOLATION:", redact(str(x))[:100])

    # 2. VSA resonance crosstalk audit: proposer gated by the edge table
    ri = ResonanceIndex(g)
    ct = ri.crosstalk_audit()
    print(f"\n=== VSA RESONANCE CROSSTALK AUDIT ===")
    print(f"{'PASS' if ct['pass'] else 'FAIL'}: {ct['proposed']} resonance "
          f"proposals, {ct['blocked']} crosstalk BLOCKED by the receipt gate, "
          f"{ct['leaked']} leaked (must be 0)")

    # 3. abstention probe: no corroborated evidence -> say nothing
    abstained = sum(1 for q in _ABSTAIN_PROBES if g.spread(q).get("abstain"))
    print(f"\n=== ABSTENTION PROBE ===")
    print(f"{abstained}/{len(_ABSTAIN_PROBES)} no-evidence queries ABSTAINED "
          f"({'PASS' if abstained == len(_ABSTAIN_PROBES) else 'FAIL'})")

    # top edges, redacted, for the shared session
    top_edges = sorted(g.edges.values(), key=lambda e: -e["weight"])[:10]
    print(f"\ntop wired associations (redacted):")
    for e in top_edges:
        print(f"  [{e['weight']:.2f} w, x{e['cooc']}] "
              f"{redact(e['a'])[:38]:38s} <--> {redact(e['b'])[:38]}")

    # UNREDACTED wired report -> local file only
    report = os.path.join(os.path.dirname(path), "wire_report.txt")
    with open(report, "w") as f:
        f.write(f"WIRED MEMORY REPORT  ({len(g.nodes)} nodes, {len(g.edges)} "
                f"receipted edges over {n_convs} conversations)\n")
        f.write("An edge means: these two corroborated facts were asserted in the "
                "same conversation >= 2 times.\nEvery edge lists the shared "
                "conversations (its receipts). Verify by opening them.\n\n")
        f.write("== EDGES (by association weight) ==\n")
        for e in sorted(g.edges.values(), key=lambda e: -e["weight"]):
            _edge_lines(f, g, e, titles)
        f.write("\n== HUB NEIGHBOURHOODS (spreading activation, 2 hops) ==\n")
        hubs = sorted(g.nodes, key=lambda n: -len(g.adj[n]))[:5]
        for h in hubs:
            r = g.spread(g.nodes[h]["value"])
            if r.get("abstain"):
                continue
            f.write(f"\n>> {h}  (degree {len(g.adj[h])})\n")
            for d in r["neighbourhood"][:12]:
                f.write(f"   a={d['activation']:.2f} hop{d['hops']} "
                        f"{d['node']['id']}   via "
                        + " ; ".join(f"x{e['cooc']}" for e in d["path"]) + "\n")
        if query is not None:
            f.write(f"\n== QUERY: {query} ==\n")
            r = g.spread(query)
            if r.get("abstain"):
                f.write("   ABSTAIN -- no corroborated fact matches.\n")
            else:
                for s in r["seeds"]:
                    f.write(f"   seed: {s['id']}  (x{s['n_mentions']})\n")
                for d in r["neighbourhood"]:
                    f.write(f"   a={d['activation']:.2f} hop{d['hops']} "
                            f"{d['node']['id']}\n")
                    for e in d["path"]:
                        f.write(f"      edge {e['a']} <-> {e['b']} "
                                f"(x{e['cooc']}: {', '.join(e['convs'][:3])}"
                                f"{'...' if len(e['convs']) > 3 else ''})\n")
    print(f"\n>>> UNREDACTED wired report (edges + receipts) written to:\n    {report}")
    if query is not None:
        r = g.spread(query)
        print(f"\nquery (redacted): "
              + ("ABSTAIN" if r.get("abstain") else
                 f"{len(r['seeds'])} seed(s), {len(r['neighbourhood'])} wired "
                 f"neighbours -- details in the local report"))


if __name__ == "__main__":
    main()
