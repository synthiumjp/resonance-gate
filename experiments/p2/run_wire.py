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
import write_rules as WR
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
from wire import WireGraph, ResonanceIndex, correct_facts, role_hash_guard

# queries with no corroborated evidence in ANY profile of this kind -- the
# abstention probe must return ABSTAIN on every one, never a guess.
_ABSTAIN_PROBES = [
    "i live in reykjavik", "works at nasa", "allergic to peanuts",
    "favourite opera", "owns a yacht", "born in 1902", "plays the bassoon",
]


_QUARANTINE = []


def quarantine():
    """Writes the learned policy blocked this build (auditable, reversible)."""
    return list(_QUARANTINE)


def _load_assistant_stream(path):
    """Mirror of PF.load_stream_and_titles, but for the ASSISTANT's own
    turns -- deliberately kept separate from the human `stream`/`prose` (never
    folded into n_convs, never eligible for real corroboration). Exists
    solely to feed the hearsay tier (entry 246): an assistant clause tagged
    evidential=="report" is a receipted claim ABOUT the user, not the user's
    own words -- see the filter in build_facts's assistant loop below."""
    conv = json.load(open(path))
    conv.sort(key=lambda c: c.get("created_at", ""))
    stream = []
    for i, c in enumerate(conv):
        for m in (c.get("chat_messages") or []):
            if (m.get("sender") or "").lower() != "assistant":
                continue
            txt = m.get("text") or m.get("content") or ""
            if isinstance(txt, list):
                txt = " ".join(str(x.get("text", "")) if isinstance(x, dict) else str(x)
                               for x in txt)
            if txt.strip():
                stream.append((i, c.get("uuid", ""), c.get("created_at", "")[:10],
                               txt.strip()[:1800]))
    return stream


def _keep_text(slot, new_text, new_source=None):
    """Choose the proposition text for a (key, value) slot.

    e266: rgx emits both a short "atom" and a fuller record off the same
    clause, and they often normalise to the SAME slot -- so `setdefault` kept
    whichever arrived FIRST, which is usually the atom, and the richer text was
    silently dropped. "I left my last job at Perrin because the commute was
    brutal" stored only "<owner> left <owner>'s last job at Perrin"; the REASON,
    which is the whole point of the sentence, went in the bin.

    e255 found this and fixed it in halumem_run.py -- the BENCHMARK harness.
    The product path (this file) kept the defect. That is the FOURTH time a
    validated fix reached one path and not the others (e248 renderer, e251
    stale run copy, e258 retrieval, this). Ledger 5m.

    RG_TEXT_LONGEST=0 forces the old first-wins behaviour; unset or 1 keeps the
    longest. The default is flipped RELATIVE TO the benchmark harness on
    purpose: e255 left it opt-in there because turning it on changes every
    banked artifact, and the product path has no banked artifacts to protect.
    """
    import os as _os
    # 2026-10-02: the verbatim source sentence is kept WITH the text it
    # belongs to, so a slot's quote is always the sentence its proposition
    # was read from.
    if _os.environ.get("RG_TEXT_LONGEST") == "0":
        if "text" not in slot:
            slot["text"] = new_text
            slot["source"] = new_source
        return
    cur = slot.get("text")
    if new_text and (not cur or len(new_text) > len(cur)):
        slot["text"] = new_text
        slot["source"] = new_source


def build_facts(path, min_mentions=2, sources=None):
    """Corroborated facts with receipts, rebuilt from the cache exactly as
    run_profile_full readout (canon + hygiene + clustering). Returns
    (facts, provisional, hearsay, n_convs, titles, n_uncached) -- provisional
    is the single-mention tail (kept for direct-match-only readout, the
    hybrid); hearsay (entry 246) is slots whose ONLY mentions are assistant
    clauses tagged evidential=="report" (the assistant's claim ABOUT the
    user, e.g. "I remember you saying...", not the user's own words) --
    stored with receipts but never asserted or volunteered."""
    _sfx = ("_v5" if os.environ.get("RG_EXTRACT_V5")
            else "_v4" if os.environ.get("RG_EXTRACT_V4")
            else "_v3" if os.environ.get("RG_EXTRACT_V3")
            else "_v2" if os.environ.get("RG_EXTRACT_V2") else "")
    cache_path = os.path.join(os.path.dirname(path), f"profile_cache{_sfx}.jsonl")
    cache = {}
    if os.path.exists(cache_path):
        for line in open(cache_path):
            try:
                d = json.loads(line)
                cache[d["h"]] = d["f"]
            except Exception:
                pass
    global _WRITE_RULES
    _QUARANTINE.clear()
    _WRITE_RULES = None
    if not os.environ.get("RG_NO_WRITE_RULES"):
        _cpath = os.path.join(os.path.dirname(path), "corrections.jsonl")
        _r = WR.load(_cpath)
        _WRITE_RULES = _r if (_r["deny"] or _r["retype"]) else None
    stream, titles = PF.load_stream_and_titles(path)
    prose = [s for s in stream if _is_prose(s[3])]
    slots = defaultdict(lambda: defaultdict(lambda: {"n": 0, "recs": []}))
    uncached = 0
    _seen_hash_role = {}  # role_hash_guard state, scoped to this build_facts call
    for step, uuid, date, text in prose:
        # Deliberately role-blind (bare sha1(text)) so this hash stays a
        # stable key into profile_cache*.jsonl across runs -- see
        # wire.role_hash_guard's docstring for why, and the detector below
        # that catches it if a cross-role collision ever actually occurs.
        h = hashlib.sha1(text.encode("utf-8")).hexdigest()
        role_hash_guard(_seen_hash_role, h, "user", text)
        if h not in cache:
            uncached += 1
            continue
        for fct in cache[h]:
            a = canon_attr(fct["attribute"])
            v = re.sub(r"\s+", " ", str(fct["value"]).strip().lower())
            # LEARNED WRITE POLICY (entry 140): the owner's corrections shape
            # the rule, not just the fact. Denied writes are QUARANTINED (kept
            # with the rule that blocked them) -- never silently destroyed, so
            # a rule that ages badly is reviewable and reversible.
            if _WRITE_RULES is not None and v:
                _act, _det = WR.decide(_WRITE_RULES, a, v)
                if _act == "deny":
                    _QUARANTINE.append({"attribute": a, "value": v,
                                        "date": date, "conv": uuid,
                                        "rule": _det["rule"]})
                    continue
                if _act == "retype":
                    a = _det["new_attribute"]
            if (not v or a in PF._EXCLUDE_ATTR or PF._EXCLUDE_ATTR_RX.search(a)
                    or PF._reject_value(a, v)):
                continue
            subj = fct.get("subject")   # v3 world facts namespace the slot
            key = f"{subj}:{a}" if subj else a
            # HEARSAY TIER (entry 246): a clause the rgx parser tagged
            # evidential=="report" is an ASSISTANT clause relaying a claim
            # ABOUT the user ("I remember you saying...", "some people find
            # that you...") -- not the user's own words. It must never count
            # toward "n" (corroboration), or the store treats the assistant's
            # invention as if the user had said it themselves. Receipted
            # regardless, so it stays auditable.
            if fct.get("evidential") == "report":
                slots[key][v]["n_hearsay"] = slots[key][v].get("n_hearsay", 0) + 1
            else:
                slots[key][v]["n"] += 1
            slots[key][v]["recs"].append((date, uuid))
            # rgx cache facts carry the full proposition in "text"; LLM cache
            # facts don't (entry 244). e266: keep the LONGEST, not the first --
            # see _keep_text.
            _keep_text(slots[key][v], fct.get("text"), fct.get("source"))

    # ASSISTANT HEARSAY PASS (entry 246 completion): `prose` above is human-
    # turns-only by design (load_stream_and_titles), so an assistant clause
    # ("I remember you mentioning...") never reached the cache lookup above
    # and the hearsay branch two paragraphs up was dead code against the real
    # conversations.json pipeline. Walk the assistant's own turns separately;
    # keep ONLY evidential=="report" clauses (a receipted claim ABOUT the
    # user) -- anything else from the assistant is dropped outright, never
    # counted toward "n", never merged into the human `prose`/n_convs.
    for step, uuid, date, text in [s for s in _load_assistant_stream(path)
                                   if _is_prose(s[3])]:
        # Same bare-hash rationale as the user-prose pass above -- this MUST
        # be the identical hash function (cache compatibility), which is
        # exactly why it can't tell this assistant turn's text apart from a
        # byte-identical user turn's. role_hash_guard is the detector.
        h = hashlib.sha1(text.encode("utf-8")).hexdigest()
        role_hash_guard(_seen_hash_role, h, "assistant", text)
        if h not in cache:
            uncached += 1
            continue
        for fct in cache[h]:
            if fct.get("evidential") != "report":
                continue
            a = canon_attr(fct["attribute"])
            v = re.sub(r"\s+", " ", str(fct["value"]).strip().lower())
            if _WRITE_RULES is not None and v:
                _act, _det = WR.decide(_WRITE_RULES, a, v)
                if _act == "deny":
                    _QUARANTINE.append({"attribute": a, "value": v,
                                        "date": date, "conv": uuid,
                                        "rule": _det["rule"]})
                    continue
                if _act == "retype":
                    a = _det["new_attribute"]
            if (not v or a in PF._EXCLUDE_ATTR or PF._EXCLUDE_ATTR_RX.search(a)
                    or PF._reject_value(a, v)):
                continue
            subj = fct.get("subject")
            key = f"{subj}:{a}" if subj else a
            slots[key][v]["n_hearsay"] = slots[key][v].get("n_hearsay", 0) + 1
            slots[key][v]["recs"].append((date, uuid))
            _keep_text(slots[key][v], fct.get("text"), fct.get("source"))

    facts, prov, hearsay = [], [], []
    for attr, entries in slots.items():
        for cl in PF._cluster(entries):
            row = (cl["n"], attr, cl["label"], cl["recs"], cl["toks"],
                  cl.get("text"), cl.get("n_hearsay", 0))
            # 2026-10-02: the verbatim source sentence, by node id, returned
            # through an OPTIONAL out-parameter so the row tuple -- unpacked
            # by position in several places -- keeps its shape.
            if sources is not None and cl.get("source"):
                sources[f"{attr}={cl['label']}"] = cl["source"]
            # cl["toks"]: the cluster's merged-variant token union, so queries
            # match any receipted variant, not just the winning label
            if cl["n"] == 0 and cl.get("n_hearsay", 0) > 0:
                hearsay.append(row)       # hearsay-only: never asserted/prov
            elif cl["n"] >= min_mentions:
                facts.append(row)
            else:
                prov.append(row)
    facts.sort(key=lambda f: -f[0])
    prov.sort(key=lambda f: -f[0])
    hearsay.sort(key=lambda f: -f[6])
    # OWNER-STATED seed facts (ground truth, e.g. entities in the user's world):
    # asserted directly (n=2), receipted "owner-stated". Merged below.
    owner_path = os.path.join(os.path.dirname(path), "owner_facts.jsonl")
    if os.path.exists(owner_path):
        n_seed = 0
        for line in open(owner_path):
            if not line.strip():
                continue
            d = json.loads(line)
            subj = str(d.get("subject", "self")).lower().strip()
            a = canon_attr(d["attribute"])
            key = a if subj in ("", "self") else f"{subj}:{a}"
            v = re.sub(r"\s+", " ", str(d["value"]).strip().lower())
            facts.append((2, key, v, [(d.get("date", ""), "owner-stated")], None))
            n_seed += 1
        titles.setdefault("owner-stated", "(owner-stated fact)")
        print(f"owner-stated seed facts: {n_seed}")
    # owner corrections (ground truth), applied before wiring so the graph,
    # report and recall all rebuild consistently. Run unconditionally: the
    # merge pass also unions duplicate slots (e.g. a seed + an extraction).
    corr_path = os.path.join(os.path.dirname(path), "corrections.jsonl")
    corrections = ([json.loads(l) for l in open(corr_path) if l.strip()]
                   if os.path.exists(corr_path) else [])
    facts, prov, log = correct_facts(facts, prov, corrections)
    if log:
        from collections import Counter
        print("owner corrections applied:", dict(Counter(a for a, _ in log)))
    n_convs = len({u for _, u, _, _ in prose})
    return facts, prov, hearsay, n_convs, titles, uncached


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

    facts, prov, hearsay, n_convs, titles, uncached = build_facts(path, min_mentions)
    print(f"corroborated facts (>= {min_mentions} mentions): {len(facts)}  "
          f"+ {len(prov)} provisional (single-mention, direct-match only)  "
          f"+ {len(hearsay)} hearsay-only (assistant claims, never asserted)  "
          f"over {n_convs} conversations  ({uncached} uncached turns skipped)")

    g = WireGraph.from_facts(facts, n_convs=n_convs, provisional=prov,
                             hearsay=hearsay)
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

    # 3. abstention probe: the memory must never ASSERT on a no-evidence query.
    # Full abstain and provisional-only (a labeled single-mention quote) are both
    # legal; a fabricated asserted seed is the failure.
    full_abstain = prov_only = asserted_hits = 0
    for q in _ABSTAIN_PROBES:
        r = g.spread(q)
        if r.get("abstain"):
            full_abstain += 1
        elif not r["seeds"]:
            prov_only += 1
        else:
            asserted_hits += 1
    print(f"\n=== ABSTENTION PROBE ===")
    print(f"{full_abstain} abstained, {prov_only} provisional-only (labeled), "
          f"{asserted_hits} asserted on no-evidence queries "
          f"({'PASS' if asserted_hits == 0 else 'FAIL'} -- asserted must be 0)")

    # top edges for the shared session: ATTRIBUTES ONLY. Values can hold
    # third-party names the owner-token redaction cannot know about, so they
    # stay in the local report and never reach stdout.
    top_edges = sorted(g.edges.values(), key=lambda e: -e["weight"])[:10]
    print(f"\ntop wired associations (attributes only; values in local report):")
    for e in top_edges:
        a, b = e["a"].split("=", 1)[0], e["b"].split("=", 1)[0]
        print(f"  [{e['weight']:.2f} w, x{e['cooc']}] "
              f"{redact(a)[:30]:30s} <--> {redact(b)[:30]}")

    # UNREDACTED wired report -> local file only
    report = os.path.join(os.path.dirname(path), "wire_report.txt")
    with open(report, "w") as f:
        f.write(f"WIRED MEMORY REPORT  ({len(g.nodes)} nodes, {len(g.edges)} "
                f"receipted edges over {n_convs} conversations)\n")
        f.write("An edge means: these two corroborated facts were asserted in the "
                "same conversation >= 2 times.\nEvery edge lists the shared "
                "conversations (its receipts). Verify by opening them.\n\n")
        top = sorted(g.edges.values(), key=lambda e: -e["weight"])[:250]
        f.write(f"== EDGES (top {len(top)} of {len(g.edges)} by association "
                f"weight) ==\n")
        for e in top:
            _edge_lines(f, g, e, titles, max_recs=2)
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
        f.write(f"\n== PROVISIONAL STORE ({len(g.provisional)} single-mention "
                f"facts -- unconfirmed, direct-match only, one confirmation "
                f"from promotion; grouped by attribute) ==\n")
        by_attr = defaultdict(list)
        for nd in g.provisional.values():
            by_attr[nd["attr"]].append(nd["value"])
        for attr in sorted(by_attr, key=lambda a: -len(by_attr[a])):
            vals = sorted(by_attr[attr])
            line = " | ".join(vals[:12])
            more = f"  (+{len(vals) - 12} more)" if len(vals) > 12 else ""
            f.write(f"   {attr} ({len(vals)}): {line[:220]}{more}\n")
        if query is not None:
            f.write(f"\n== QUERY: {query} ==\n")
            r = g.spread(query)
            if r.get("abstain"):
                f.write("   ABSTAIN -- never seen.\n")
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
                for p in r.get("provisional", []):
                    f.write(f"   UNCONFIRMED (seen once): {p['node']['id']}\n")
    print(f"\n>>> UNREDACTED wired report (edges + receipts) written to:\n    {report}")
    if query is not None:
        r = g.spread(query)
        print(f"\nquery (redacted): "
              + ("ABSTAIN -- never seen" if r.get("abstain") else
                 f"{len(r['seeds'])} asserted seed(s), "
                 f"{len(r['neighbourhood'])} wired neighbours, "
                 f"{len(r.get('provisional', []))} unconfirmed single-mention "
                 f"-- details in the local report"))


if __name__ == "__main__":
    main()
