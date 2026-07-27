"""p2 GATE LAB (entry: compose-vs-abstain tightening, dev users 10-12, 14B
v5.1 caches): deterministic evaluation of the plain-surface COMPOSE-VS-ABSTAIN
gate in halumem_run._answer_plain.

THE PROBLEM (measured on the official HaluMem judge, not this in-house proxy):
~29% of plain-surface answers on dev/test get NO verdict ("None") from the
real LLM judge -- not "hallucination", not "omission", literally unparseable.
These are long word-salad blobs: many weakly-matched narrative facts
(motivation/belief/value/preference/plan -- the mega-buckets the v5.1
extractor dumps hundreds of facts into) joined with "; " because the existing
gate ("any real content word covered") is satisfied by a single incidental
value-token overlap. This happens almost entirely on
inference/application/multi-hop/conflict questions, where the store has NO
fact that DIRECTLY answers -- composing is a category error there; the
correct behaviour is the SAME abstain the system already does correctly on
pure Memory Boundary questions.

METRICS (all local, deterministic, no model/judge call):
  DELIVERED            -- % of real-gold questions whose composed answer
                           contains >=50% of gold content tokens (unchanged
                           proxy metric from surface_lab.py)
  COMPOSED-ON-UNKNOWN   -- % of Unknown-gold questions that got a composed
                           (non-"Unknown.") answer (want LOW)
  ABSTAIN-RATE          -- % of ALL questions answered "Unknown."
  LEN-RISK              -- % of composed answers > 350 chars, and the max
                           composed length (a proxy for the real judge's
                           unparseable-blob failure: the official run found
                           26.8% None-verdicts on unbounded joins, hence the
                           RG_COMPOSE_BUDGET length cap already shipped;
                           LEN-RISK measures whether the NEW gate keeps
                           answers away from that budget ceiling, not just
                           under it)
  COMPOSED-COUNT        -- distribution of how many facts got joined into a
                           composed answer (blobs = many)

IMPORTANT FRAMING (do not over-read the raw DELIVERED number): the shipped
policy's ~40.5% DELIVERED is partly an artifact of this proxy -- a long blob
cheaply CONTAINS gold tokens by sheer volume even though the real judge
cannot parse it and scores it 0 in practice. A tighter gate that delivers
fewer but SHORTER, more confident answers is the actual goal; this harness
also reports LEN-RISK and COMPOSED-ON-UNKNOWN specifically so a "winner" can't
just be the variant that blob-shotguns hardest.

Candidate gate mechanisms under test (toggle via GCfg, all default OFF so the
all-off baseline reproduces halumem_run._answer_plain's shipped behaviour
exactly -- verified by ship_parity_check() below):

  MULTIHOP  (mechanism c): a static phrase list flags speculative/inferential
      question framing ("might", "could", "would", "should", "how did",
      "how does", "why do you think", "what does this suggest", "what role
      did") -- verified empirically against this dev set's own
      question_type labels (see module docstring notes in the commit): on
      users 10-12, might/could/would/should hit 92%/11%/3%/2% of
      "Generalization & Application" questions and ZERO questions of any
      OTHER type; "how did" hits 46% of "Multi-hop Inference" and only one
      "Dynamic Update" question. A pure join can never actually answer these
      -- they ask for a synthesized recommendation/explanation, not a stored
      value -- so this is a heuristic PHRASE match, documented as such, not a
      semantic judgement.
  CONFIDENT (mechanism a): compose only if at least one candidate fact's
      ATTRIBUTE tokens (or a _QUERY_SYNONYMS-mapped question token's target
      attribute) directly intersect the question's ask-tokens -- i.e. some
      fact was found because its ATTRIBUTE lines up with what was asked, not
      merely because FIX F's value-token fallback found a stray shared word
      in a mega-bucket value. Else abstain.
  MAXCOMPOSE(N) + GENERIC (mechanism b): hard-cap the number of facts that
      may be joined into one answer to N (default off = no cap beyond the
      existing per-tier caps), and separately: if EVERY candidate fact is a
      generic narrative attribute (motivation/belief/value/reflection/
      feeling/preference/plan -- the mega-buckets) AND none of them has an
      attribute-level match to the ask (same check as CONFIDENT), abstain --
      this is the "all we have is topically-related narrative noise, no
      actual answer" case that produces the worst blobs.

Usage: gate_lab.py [--users 10-12] [--min-mentions 2]
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import halumem_run as HR
from wire import (_tokens, extract_dates, _STOP, _QWORDS, _MONTHS,
                   _QUERY_SYNONYMS, _DATE_PREP, _is_dateish)
from surface_lab import (HALUMEM_PATH, CACHE_TEMPLATE, load_dev_users,
                          _is_unknown_gold, _delivered)

# ---------------------------------------------------------------------------
# MULTIHOP phrase list (mechanism c) -- see module docstring for the measured
# per-question-type hit rates that justify each phrase. Verified against
# users 10-12's own question_type labels (not guessed):
#   modal speculative wording ("might"/"could"/"would"/"should", ANYWHERE in
#   the question) hits 97% of "Generalization & Application" (a speculative
#   recommendation ask -- "what beverage might Michelle explore" -- that no
#   join of stored facts can ever answer) and 0% of Basic Fact Recall /
#   Memory Boundary / Dynamic Update on this dev set.
#   "how did"/"how does"/"why do you think"/"what does this suggest"/
#   "what role did" additionally catch 57% of "Multi-hop Inference".
#   a LEADING "did/is/was/does" (a yes/no confirm-or-deny question -- "Did
#   Michelle decide to..."/"Is her work related to...") catches 92% of
#   "Memory Conflict": these ask for a CONFIRM/DENY judgement against a
#   claim, which a bare fact-value join can never express (it has no way to
#   say "no, actually..."), so joining is a category error here regardless
#   of whether the store holds the right fact.
# Combined hit rate: Generalization&Application 97%, Memory Conflict 92%,
# Multi-hop Inference 57%; false-positive rate on the classes that SHOULD
# still compose: Basic Fact Recall 1%, Dynamic Update 5%, Memory Boundary 3%
# (harmless there -- Boundary is already 100% Unknown-gold).
# ---------------------------------------------------------------------------
_MULTIHOP_RX = re.compile(
    r"\b(might|could|would|should|how did|how does|why do you think|"
    r"what does this suggest|what role did)\b", re.I)
_CONFLICT_LEAD_RX = re.compile(r"^\s*(did|is|was|does)\b", re.I)


def _is_multihop(q):
    return bool(_MULTIHOP_RX.search(q) or _CONFLICT_LEAD_RX.match(q))

# GENERIC narrative attributes (mechanism b) -- the mega-buckets the v5.1
# extractor dumps hundreds of facts into (see halumem_run.py FIX F comment);
# an attribute bridge cannot discriminate one fact among these, so a set of
# candidates that is ENTIRELY generic, with no attribute-level match to the
# ask, is exactly the "topically related, doesn't actually answer" case.
_GENERIC_ATTRS = {"motivation", "belief", "value", "reflection", "feeling",
                   "preference", "plan"}


def _base_attr(f):
    return f["attribute"].split(":")[-1]


def _confident_hit(facts, ask_all):
    """True if some candidate fact's ATTRIBUTE (not just its value) lines up
    with what was asked -- directly, or via the synonym bridge. `ask_all`:
    the question's content tokens (persona/stop/qwords/date-noise removed)."""
    attr_toks = set()
    for f in facts:
        attr_toks |= _tokens(f["attribute"])
    if attr_toks & ask_all:
        return True
    return any(_QUERY_SYNONYMS.get(t) in attr_toks for t in ask_all
               if t in _QUERY_SYNONYMS)


class GCfg:
    def __init__(self, name, *, multihop=False, confident=False,
                 max_compose=None, generic_drop=False, compose_budget=360):
        self.name = name
        # multihop: False (off) / True (unconditional abstain on phrase hit)
        # / "cond" (abstain on phrase hit ONLY if the final candidates also
        # fail the CONFIDENT attribute-match test -- lets a genuinely
        # answering fact still speak even on modal/conflict-phrased
        # questions, only killing the "phrase hit + nothing specific"
        # combination that produces the worst blobs).
        self.multihop = multihop
        self.confident = confident
        self.max_compose = max_compose
        self.generic_drop = generic_drop
        self.compose_budget = compose_budget


def answer_plain_gated(mem, q, cfg):
    """Same pipeline as halumem_run._answer_plain (FIX B/D/F/H/I/J), with the
    EXPERIMENTAL gate mechanisms this lab measured (MULTIHOP-modal/CONFIDENT/
    MAXCOMPOSE/GENERIC -- NOT adopted, see halumem_run.py's FIX J comment for
    why) inserted as toggleable hooks, all off by default. The
    CONFLICT-LEAD check (yes/no confirm-or-deny abstain) and the tightened
    360-char compose_budget default ARE adopted/shipped, so they run
    unconditionally here too -- an all-flags-off GCfg reproduces the shipped
    function's output exactly, see ship_parity_check(). Returns
    (answer_text, n_composed)."""
    if _CONFLICT_LEAD_RX.match(q):        # FIX J, shipped unconditionally
        return "Unknown.", 0
    q_is_multihop = _is_multihop(q)
    if cfg.multihop is True and q_is_multihop:
        return "Unknown.", 0

    r = mem.recall(q)
    r = r if r["found"] else {"found": True, "asserted": [], "wired": [],
                               "unconfirmed": []}

    persona = mem.g._persona_tokens()
    q_toks_raw = _tokens(q)
    qc = q_toks_raw - persona - _QWORDS - _DATE_PREP
    qc = {t for t in qc if not _is_dateish(t)}

    extra = HR._value_fallback_facts(mem, qc, min_shared=1)
    have = {f["attribute"] + "=" + f["value"] for f in r["unconfirmed"]}
    r = dict(r)
    r["unconfirmed"] = r["unconfirmed"] + [
        f for f in extra if f["attribute"] + "=" + f["value"] not in have]

    r["asserted"] = [f for f in r["asserted"] if HR._subject_ok(f, q_toks_raw)]
    r["wired"] = [w for w in r["wired"] if HR._subject_ok(w["fact"], q_toks_raw)]
    r["unconfirmed"] = [f for f in r["unconfirmed"] if HR._subject_ok(f, q_toks_raw)]

    all_facts = (r["asserted"] + [w["fact"] for w in r["wired"]] + r["unconfirmed"])
    ask = HR._ask_tokens(q, all_facts) - persona

    def _rank(fs):
        return sorted(fs, key=lambda f: -len(
            (_tokens(f["attribute"]) | _tokens(f["value"])) & ask))

    q_date = HR._parse_query_date(q)
    if q_date is not None:
        groups = defaultdict(list)
        for f in r["asserted"]:
            groups[("a", f["attribute"].split(":")[-1])].append(f)
        for w in r["wired"]:
            groups[("w", w["fact"]["attribute"].split(":")[-1])].append(w["fact"])
        for f in r["unconfirmed"]:
            groups[("u", f["attribute"].split(":")[-1])].append(f)
        keep_a, keep_w, keep_u = [], [], []
        for (tier, _attr), fs in groups.items():
            picked = HR._asof_select(fs, q_date)
            (keep_a if tier == "a" else keep_w if tier == "w" else keep_u
             ).extend(picked)
        if keep_a or keep_w or keep_u:
            r["asserted"], r["unconfirmed"] = keep_a, keep_u
            r["wired"] = [w for w in r["wired"] if w["fact"] in keep_w]

    asserted = _rank(r["asserted"])[:20]
    wired = _rank([w["fact"] for w in r["wired"]])[:20]
    unconfirmed = _rank(r["unconfirmed"])[:40]

    facts = asserted + wired + unconfirmed
    if not facts:
        return "Unknown.", 0

    if not HR._specificity_ok(q_toks_raw, facts):
        return "Unknown.", 0

    ask_all = {t for t in (q_toks_raw - _STOP - _QWORDS - persona)
               if not t.isdigit() and t not in _MONTHS and t not in _DATE_PREP}

    # MECHANISM (a): CONFIDENT MATCH -- require an attribute-level hit
    # (direct or synonym-bridged) among the candidates before composing.
    if cfg.confident and ask_all and not _confident_hit(facts, ask_all):
        return "Unknown.", 0

    # MECHANISM (c), conditional form: a modal/conflict-phrased question
    # (mechanism c's phrase list) abstains ONLY when it ALSO has no
    # confident attribute-level match -- a genuinely on-topic stored fact
    # still gets to answer even when the question is phrased speculatively.
    if cfg.multihop == "cond" and q_is_multihop and not _confident_hit(facts, ask_all):
        return "Unknown.", 0

    # MECHANISM (b): hard cap + generic-narrative drop. The cap runs first
    # (it changes what "all candidates" means for the generic check), then
    # the generic-drop test runs on the CAPPED set -- the actual set that
    # would be composed.
    if cfg.max_compose:
        facts = facts[:cfg.max_compose]
    if cfg.generic_drop and facts and all(_base_attr(f) in _GENERIC_ATTRS
                                          for f in facts):
        if not _confident_hit(facts, ask_all):
            return "Unknown.", 0

    attr_val_toks, attr_toks = set(), set()
    for f in facts:
        attr_val_toks |= _tokens(f["attribute"]) | _tokens(f["value"])
        attr_toks |= _tokens(f["attribute"])
    uncovered = q_toks_raw - attr_val_toks - _STOP - _QWORDS - persona
    uncovered = {t for t in uncovered if _QUERY_SYNONYMS.get(t) not in attr_toks}
    unc = uncovered & ask_all
    if ask_all and unc >= ask_all:
        return "Unknown.", 0

    budget = int(os.environ.get("RG_COMPOSE_BUDGET", cfg.compose_budget))
    out, total = [], 0
    for f in facts:
        v = f["value"]
        if out and total + len(v) + 2 > budget:
            break
        out.append(v)
        total += len(v) + 2
    return "; ".join(out), len(out)


def ship_parity_check(mems):
    """All-gates-off GCfg must reproduce halumem_run.answer_question(
    surface='plain') EXACTLY, question for question -- this harness is only
    trustworthy as a gate-iteration tool if its baseline is a faithful copy
    of the shipped pipeline, not a reimplementation that drifted."""
    base = GCfg("parity")
    mismatches = 0
    n = 0
    for uidx, (mem, qs) in mems.items():
        for q in qs:
            n += 1
            shipped = HR.answer_question(mem, q["question"], surface="plain")
            gated, _ = answer_plain_gated(mem, q["question"], base)
            if shipped != gated:
                mismatches += 1
                if mismatches <= 3:
                    print(f"  PARITY MISMATCH u{uidx} q={q['question'][:60]!r}\n"
                          f"    shipped: {shipped[:120]!r}\n"
                          f"    gated:   {gated[:120]!r}")
    print(f"parity check: {n - mismatches}/{n} match "
          f"({'PASS' if mismatches == 0 else 'FAIL'})")
    return mismatches == 0


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

def score_gcfg(mems, cfg):
    n_real = n_delivered = 0
    n_unk = n_unk_composed = 0
    n_total = n_abstain = 0
    lens = []
    compose_counts = []
    abstain_by_type = defaultdict(int)
    total_by_type = defaultdict(int)
    for uidx, (mem, qs) in mems.items():
        for q in qs:
            gold = str(q.get("answer", "")).strip()
            qtype = q.get("question_type", "?")
            ans, n_composed = answer_plain_gated(mem, q["question"], cfg)
            n_total += 1
            total_by_type[qtype] += 1
            composed = ans != "Unknown."
            if not composed:
                n_abstain += 1
                abstain_by_type[qtype] += 1
            else:
                lens.append(len(ans))
                compose_counts.append(n_composed)
            if _is_unknown_gold(gold):
                n_unk += 1
                if composed:
                    n_unk_composed += 1
            elif gold:
                n_real += 1
                if composed and _delivered(gold, ans):
                    n_delivered += 1
    n_over350 = sum(1 for l in lens if l > 350)
    cc_hist = defaultdict(int)
    for c in compose_counts:
        cc_hist[c if c <= 4 else "5+"] += 1
    return {
        "name": cfg.name,
        "n_total": n_total,
        "delivered": 100 * n_delivered / max(n_real, 1),
        "n_delivered": n_delivered, "n_real": n_real,
        "composed_on_unknown": 100 * n_unk_composed / max(n_unk, 1),
        "n_unk_composed": n_unk_composed, "n_unk": n_unk,
        "abstain_rate": 100 * n_abstain / max(n_total, 1),
        "max_len": max(lens) if lens else 0,
        "pct_over350": 100 * n_over350 / max(len(lens), 1),
        "n_composed": len(lens),
        "cc_hist": dict(cc_hist),
        "abstain_by_type": dict(abstain_by_type),
        "total_by_type": dict(total_by_type),
    }


VARIANTS = [
    GCfg("G0 baseline (shipped, all gates off)"),
    GCfg("G1 +MULTIHOP", multihop=True),
    GCfg("G2 +CONFIDENT", confident=True),
    GCfg("G3 +MAXCOMPOSE(3)", max_compose=3),
    GCfg("G4 +MAXCOMPOSE(2)", max_compose=2),
    GCfg("G5 +MAXCOMPOSE(1)", max_compose=1),
    GCfg("G6 +GENERIC-drop", generic_drop=True),
    GCfg("G7 +MAXCOMPOSE(3)+GENERIC", max_compose=3, generic_drop=True),
    GCfg("G8 MULTIHOP+CONFIDENT", multihop=True, confident=True),
    GCfg("G9 MULTIHOP+MAXCOMPOSE(3)+GENERIC",
         multihop=True, max_compose=3, generic_drop=True),
    GCfg("G10 MULTIHOP+CONFIDENT+MAXCOMPOSE(3)+GENERIC",
         multihop=True, confident=True, max_compose=3, generic_drop=True),
    GCfg("G11 MULTIHOP+CONFIDENT+MAXCOMPOSE(2)+GENERIC",
         multihop=True, confident=True, max_compose=2, generic_drop=True),
    GCfg("G12 MULTIHOP+CONFIDENT+MAXCOMPOSE(1)+GENERIC",
         multihop=True, confident=True, max_compose=1, generic_drop=True),
    GCfg("G13 MULTIHOP+MAXCOMPOSE(2)+GENERIC",
         multihop=True, max_compose=2, generic_drop=True),
    GCfg("G14 MULTIHOP+MAXCOMPOSE(1)+GENERIC",
         multihop=True, max_compose=1, generic_drop=True),
    GCfg("G15 CONFIDENT+MAXCOMPOSE(3)+GENERIC",
         confident=True, max_compose=3, generic_drop=True),
]

# budget sweep (mechanism: tighten RG_COMPOSE_BUDGET itself, the direct knob
# on LEN-RISK) alone and combined with the cheapest-DELIVERED-cost gates.
for _budget in (350, 300, 250, 200):
    VARIANTS.append(GCfg(f"B{_budget} budget only", compose_budget=_budget))
for _budget in (350, 300, 250):
    VARIANTS.append(GCfg(f"B{_budget}+GENERIC", compose_budget=_budget,
                          generic_drop=True))
    VARIANTS.append(GCfg(f"B{_budget}+MULTIHOP", compose_budget=_budget,
                          multihop=True))
    VARIANTS.append(GCfg(f"B{_budget}+MULTIHOP+GENERIC", compose_budget=_budget,
                          multihop=True, generic_drop=True))
    VARIANTS.append(GCfg(f"B{_budget}+CONFIDENT", compose_budget=_budget,
                          confident=True))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--users", default="10-12")
    ap.add_argument("--min-mentions", dest="min_mentions", type=int, default=2)
    ap.add_argument("--cache-template", dest="cache_template", default=CACHE_TEMPLATE)
    ap.add_argument("--by-type", action="store_true",
                     help="print per-question-type abstain breakdown for the winner")
    args = ap.parse_args()

    a, b = args.users.split("-") if "-" in args.users else (args.users, args.users)
    user_indices = list(range(int(a), int(b) + 1))

    print(f"loading users {user_indices} from v5.1 14B caches ...")
    mems = load_dev_users(user_indices, args.min_mentions, args.cache_template)
    total_q = sum(len(qs) for _, qs in mems.values())
    print(f"{len(mems)} users, {total_q} questions total\n")

    ship_parity_check(mems)
    print()

    hdr = (f"{'variant':46s} {'ABSTAIN%':>8s} {'DELIV%':>7s} {'(n)':>9s} "
           f"{'CMP-UNK%':>8s} {'(n)':>7s} {'MAXLEN':>7s} {'>350%':>6s} "
           f"{'n_cmp':>6s}")
    print(hdr)
    print("-" * len(hdr))
    rows = []
    for cfg in VARIANTS:
        row = score_gcfg(mems, cfg)
        rows.append(row)
        print(f"{cfg.name:46s} {row['abstain_rate']:8.1f} {row['delivered']:7.1f} "
              f"{row['n_delivered']:>3d}/{row['n_real']:<5d} "
              f"{row['composed_on_unknown']:8.1f} "
              f"{row['n_unk_composed']:>3d}/{row['n_unk']:<3d} "
              f"{row['max_len']:7d} {row['pct_over350']:6.1f} "
              f"{row['n_composed']:6d}")

    print(f"\nTARGETS: DELIVERED >= 28.0, COMPOSED-ON-UNKNOWN <= 20.0, "
          f"MAXLEN <= 450, >350chars% < 15.0")

    if args.by_type:
        print("\nCOMPOSED-COUNT histograms (facts joined per composed answer):")
        for row in rows:
            print(f"  {row['name']:46s} {row['cc_hist']}")
        print("\nabstain-rate by question_type (winner-agnostic, all variants):")
        for row in rows:
            print(f"  {row['name']}")
            for t, tot in sorted(row["total_by_type"].items()):
                ab = row["abstain_by_type"].get(t, 0)
                print(f"    {t:32s} abstain {ab:3d}/{tot:<3d} ({100*ab/tot:.0f}%)")


if __name__ == "__main__":
    main()
