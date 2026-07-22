"""HaluMem adapter + pilot (entry 82): the out-of-sample generalization test
AND the SOTA target run, on the operation-level memory-hallucination benchmark
(arXiv:2511.03506; 20 synthetic users, gold memory points, QA with built-in
Memory Boundary questions whose gold answer is "Unknown").

Pipeline per user: user-role turns -> per-turn v3 extraction (local qwen,
cached) -> canon/hygiene -> corroboration (session = conversation granularity)
-> WireGraph/Memory -> non-generative QA:
    recall(question) -> matched facts verbatim, or ABSTAIN ("Unknown").

Scoring (PILOT, in-house -- the official harness uses LLM judging; ours is a
local-judge proxy, flagged, two-judge validation owed before quoting):
  - QA: local judge classifies each answer as correct / hallucination /
    omission given the gold answer and our returned facts.
  - Extraction proxy: token-overlap match of asserted facts against gold
    memory points (integrity ~ recall of golds; precision of asserted).
No personal data anywhere: benchmark is synthetic personas.

Usage: halumem_run.py <HaluMem-Medium.jsonl> [user_idx=0] [min_mentions=2]
"""

import hashlib
import json
import os
import re
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import run_profile_full as PF
from llm_profile import SYSTEM_V3, SYSTEM_V4, canon_attr, extract_profile_facts

# v4 (events/plans) is the coverage lever measured in entry 83; opt in via
# RG_EXTRACT_V4 so v3 pilot caches stay valid for comparison.
_SYSTEM = SYSTEM_V4 if os.environ.get("RG_EXTRACT_V4") else SYSTEM_V3
_CSFX = "_v4" if os.environ.get("RG_EXTRACT_V4") else ""
from consistency import get_llm
from wire import WireGraph, _tokens, extract_dates, _STOP
from memory_api import Memory

JUDGE = """You grade a memory system's answer to a question about a user.
GOLD is the reference answer. SYSTEM returned stored facts (or ABSTAIN).
The system only returns stored facts; it never composes an answer. Judge
whether the STORED FACTS state the asked-for value.
Reply with exactly one word:
  correct       -- the returned facts contain the gold answer; OR gold says
                   Unknown/not provided and NO returned fact states a value
                   for the specific thing asked (returning true RELATED facts
                   that do not answer the question is correct, not an error)
  hallucination -- a returned fact STATES a value for the asked question that
                   is wrong or contradicts gold, or states one when gold says
                   Unknown
  omission      -- gold has a real answer but the system abstained or its
                   facts do not contain it"""


def judge_answer(question, gold, answer_text):
    out = get_llm().create_chat_completion(
        messages=[{"role": "system", "content": "/no_think " + JUDGE},
                  {"role": "user", "content":
                   f"QUESTION: {question}\nGOLD: {gold}\nSYSTEM: {answer_text}"}],
        max_tokens=10, temperature=0.0)
    txt = out["choices"][0]["message"]["content"]
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.DOTALL).strip().lower()
    for v in ("correct", "hallucination", "omission"):
        if v in txt:
            return v
    return "omission"


def ingest_user(user, cache_path, min_mentions=2):
    """User-role turns -> extraction (cached) -> hygiene -> corroborated facts.
    Session index is the conversation id (co-occurrence granularity)."""
    cache = {}
    if os.path.exists(cache_path):
        for line in open(cache_path):
            try:
                d = json.loads(line)
                cache[d["h"]] = d["f"]
            except Exception:
                pass
    cf = open(cache_path, "a")
    slots = defaultdict(lambda: defaultdict(lambda: {"n": 0, "recs": []}))
    n_turns = 0
    for si, sess in enumerate(user["sessions"]):
        date = str(sess.get("start_time", ""))[:12]
        for t in sess.get("dialogue", []):
            if t.get("role") != "user":
                continue
            text = str(t.get("content", "")).strip()[:1800]
            if not text:
                continue
            n_turns += 1
            h = hashlib.sha1(text.encode()).hexdigest()
            if h in cache:
                facts = cache[h]
            else:
                facts = extract_profile_facts(text, system=_SYSTEM)
                cf.write(json.dumps({"h": h, "f": facts}) + "\n")
                cf.flush()
                cache[h] = facts
            for fct in facts:
                a = canon_attr(fct["attribute"])
                v = re.sub(r"\s+", " ", str(fct["value"]).strip().lower())
                if (not v or a in PF._EXCLUDE_ATTR
                        or PF._EXCLUDE_ATTR_RX.search(a)
                        or PF._reject_value(a, v)):
                    continue
                subj = fct.get("subject")
                key = f"{subj}:{a}" if subj else a
                slots[key][v]["n"] += 1
                slots[key][v]["recs"].append((date, f"s{si}"))
    facts, prov = [], []
    for attr, entries in slots.items():
        for cl in PF._cluster(entries):
            tgt = facts if cl["n"] >= min_mentions else prov
            tgt.append((cl["n"], attr, cl["label"], cl["recs"], cl["toks"]))
    g = WireGraph.from_facts(facts, n_convs=len(user["sessions"]),
                             provisional=prov)
    return Memory(g), n_turns


def _fact_dates(f):
    """All date tokens a returned fact carries: its value text, plus every
    receipt's date string. Used only to SCOPE which stored facts an answer
    draws on -- never to invent a date."""
    d = extract_dates(f["value"])
    for rec in f.get("receipts", []) or []:
        d |= extract_dates(rec.get("date", ""))
    return d


def answer_question(mem, q):
    """Non-generative answer: matched stored facts verbatim, or ABSTAIN.

    Two static, receipt-only refinements over the raw match (both measured
    failure-mode fixes, neither generates content -- they only reorder/drop/
    label the SAME retrieved facts):

    DATE SCOPING (Fix 2): if the question names a date (extract_dates), facts
    whose value or receipt dates share a token with the asked date are kept
    (asserted/wired filtered down to just these); if the question names a
    date but NO returned fact matches it, the answer is prefixed to say so
    explicitly rather than presenting an off-date fact as if it answered the
    question.

    VALUE-TYPE DISCLAIMER (Fix 3): if the only thing the question shares with
    the returned facts is the subject/name tokens already consumed by the
    VALUE (not the actual attribute asked about -- e.g. a full-name fact
    returned for a "what's the middle name" question), the answer says the
    facts are related, not an answer, instead of the plain "Stored facts:"
    lead-in that a grader could misread as answering the question."""
    r = mem.recall(q)
    if not r["found"]:
        return "ABSTAIN -- no stored fact matches (Unknown)."

    asserted = r["asserted"][:6]
    wired = [w["fact"] for w in r["wired"][:4]]
    unconfirmed = r["unconfirmed"][:3]

    q_dates = extract_dates(q)
    date_scoped_empty = False
    if q_dates:
        a_hit = [f for f in asserted if _fact_dates(f) & q_dates]
        w_hit = [f for f in wired if _fact_dates(f) & q_dates]
        if a_hit or w_hit:
            asserted, wired = a_hit, w_hit
        else:
            date_scoped_empty = True   # keep all facts, flag the mismatch

    parts = [f"{f['attribute']}: {f['value']}" for f in asserted]
    parts += [f"(linked) {f['attribute']}: {f['value']}" for f in wired]
    parts += [f"UNCONFIRMED (seen once): {f['attribute']}: {f['value']}"
              for f in unconfirmed]
    if not parts:
        return "ABSTAIN -- no stored fact matches (Unknown)."
    answer = "; ".join(parts)

    if date_scoped_empty:
        return ("No stored fact from the asked date; related facts from "
                 "other dates: " + answer)

    facts = asserted + wired + unconfirmed
    value_toks = set()
    attr_val_toks = set()
    for f in facts:
        value_toks |= _tokens(f["value"])
        attr_val_toks |= _tokens(f["attribute"]) | _tokens(f["value"])
    ask_toks = _tokens(q) - value_toks - _STOP
    if ask_toks and not (ask_toks & attr_val_toks):
        return ("No stored fact answers the asked attribute; related "
                 "receipted facts: " + answer)

    return "Stored facts: " + answer


def extraction_proxy(mem, gold_mps):
    """Token-overlap proxy for the extraction task: a gold memory point is
    COVERED if some stored fact (either tier) shares >=50% of its content
    tokens. Reported for signal, not as an official number."""
    stored = [(_tokens(d["attr"] + " " + d["value"]))
              for d in list(mem.g.nodes.values()) + list(mem.g.provisional.values())]
    covered = 0
    for mp in gold_mps:
        gt = _tokens(mp.get("memory_content", ""))
        if not gt:
            continue
        if any(len(gt & st) / len(gt) >= 0.5 for st in stored):
            covered += 1
    return covered, len(gold_mps)


def main():
    path = sys.argv[1]
    uidx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    min_mentions = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    users = [json.loads(l) for l in open(path)]
    user = users[uidx]
    cache_path = os.path.join(os.path.dirname(path),
                              f"cache_u{uidx}{_CSFX}.jsonl")

    mem, n_turns = ingest_user(user, cache_path, min_mentions)
    print(f"user {uidx}: {len(user['sessions'])} sessions, {n_turns} user turns "
          f"-> {len(mem.g.nodes)} asserted + {len(mem.g.provisional)} provisional, "
          f"{len(mem.g.edges)} edges")
    a = mem.g.audit()
    print(f"wire audit: {'PASS' if a['pass'] else 'FAIL'} "
          f"({a['n_pairs_checked']} pairs, {len(a['violations'])} violations)")

    gold_mps = [mp for s in user["sessions"] for mp in s.get("memory_points", [])
                if mp.get("memory_source") != "interference"]
    cov, tot = extraction_proxy(mem, gold_mps)
    print(f"extraction proxy: {cov}/{tot} gold memory points covered "
          f"({100 * cov / max(tot, 1):.1f}%) [token-overlap proxy]")

    tally = defaultdict(int)
    by_type = defaultdict(lambda: defaultdict(int))
    qs = [(q, s) for s in user["sessions"] for q in s.get("questions", [])]
    for i, (q, s) in enumerate(qs):
        ans = answer_question(mem, q["question"])
        verdict = judge_answer(q["question"], q["answer"], ans)
        tally[verdict] += 1
        by_type[q.get("question_type", "?")][verdict] += 1
        if (i + 1) % 50 == 0:
            print(f"  ...{i + 1}/{len(qs)} questions judged")
    n = sum(tally.values())
    print(f"\nQA (n={n}, local-judge PILOT numbers, two-judge validation owed):")
    for v in ("correct", "hallucination", "omission"):
        print(f"  {v:13s}: {tally[v]:4d}  ({100 * tally[v] / max(n, 1):.1f}%)")
    print("\nby question type:")
    for t, d in sorted(by_type.items()):
        tn = sum(d.values())
        print(f"  {t[:34]:34s} n={tn:3d}  correct {d['correct']:3d}  "
              f"halluc {d['hallucination']:3d}  omit {d['omission']:3d}")


if __name__ == "__main__":
    main()
