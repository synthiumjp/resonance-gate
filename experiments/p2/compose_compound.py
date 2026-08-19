"""Compound proposition composer (S6, following merge_probe.py's offline probe).

merge_probe measured naive merging (by_overlap: chain records sharing >=2
value tokens, unbounded group size) at +5.6pt of single-record coverage over
its matched random-grouping null, at 57% fewer records. This module is the
"properly" version that probe called for: a grouping rule that is JUSTIFIED
rather than merely lexical, a size cap, and grammar that reuses
propositions.render() instead of re-deriving verb/value agreement.

WHY THIS GROUPING RULE. HaluMem gold sentences bundle propositions that are
about the same person and the same THEME -- "has initiated collaborative
projects ... focusing on innovative solutions and shared goals" is one
person's plan and their focus, not a plan and an unrelated fact about their
commute. Three signals decide whether two of our facts plausibly belong in
one gold-shaped sentence, in priority order:

  1. SAME SUBJECT. A sentence has one grammatical subject. Facts about the
     owner and facts about a third party (currency.py's subject-prefixed
     "sophia:occupation") are never candidates for the same sentence --
     merging them would silently attribute someone else's fact to the owner.
  2. SAME ATTRIBUTE FAMILY (_FAMILY below). Built from the real V5/V6
     extractor vocabulary (llm_profile.py's SYSTEM_V5 narrative attributes;
     currency.py's _ALIAS work/place groups), not guessed. An attribute
     outside every family (e.g. "name", "monthly_income" alone) never
     merges with anything -- the conservative default matters: a grouping
     rule permissive enough to catch everything degenerates to
     merge_probe's "all" strategy, which is the paper's own upper bound and
     explicitly NOT a proposal (it buys coverage by destroying the scored
     unit).
  3. LEXICAL OVERLAP. Facts in DIFFERENT families still plausibly belong
     together if their values share >=2 content tokens (same threshold as
     merge_probe's by_overlap, so this is a strict superset of that
     signal, not a different one). Owner-name tokens are stripped first
     (granularity.py's convention: every rendered fact carries the owner's
     name, so leaving it in would make "shares >=2 tokens" trivially true
     for any two facts about the same person).

CAP = 3. HaluMem's own gold sentences bundle "two or three propositions" (see
this file's module docstring epigraph in the task brief); the probe's degenerate
"all" strategy shows that once merging is not bounded to what gold itself
does, more merging keeps buying single-record coverage for a reason that has
nothing to do with matching gold's structure -- it is just a bigger bag of
words. Capping at the observed gold granularity keeps the compound honest:
it is sized to look like the thing it is trying to match, not to maximize
overlap.

GRAMMAR. Zero new verb/value logic. propositions.render() already resolved
the verb-shape bug class (gerund vs infinitive, "to X" vs noun phrase) for
every individual fact; this module renders each fact NORMALLY and then joins
the already-correct clauses, stripping only the repeated subject text (which
render() prepends verbatim and predictably, so the strip is a literal
string operation, not a re-derivation of grammar). Two rendered clauses
sharing the exact same verb ("enjoys reading" + "enjoys hiking") have their
values coalesced under one verb ("enjoys reading and hiking"); clauses with
different verbs or the possessive fallback form are chained with "and"/
", and <Subject>'s ..." rather than invented pronouns (gender is never
known, so no pronoun is ever generated).

Compounds are additive: this returns ONLY the compound sentences for facts
that were grouped (size >= 2). Facts that did not join any group are not
returned here at all -- the caller keeps emitting them as atoms, unchanged.

No LLM calls. Deterministic: same input list -> same output list, every time.
"""
import os
import sys
from collections import OrderedDict, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import granularity as G  # noqa: E402  (reuse: toks(), STOP tokenisation)
import propositions as PR  # noqa: E402  (reuse: render(), split_subject(), ...)

# Built from the real extractor vocabulary, not guessed:
#  - narrative attrs are SYSTEM_V5's closed list (llm_profile.py) plus "plan"/
#    "goal", which canon_attr folds "plans"/"intention"/"upcoming_event" into.
#    These are exactly the attrs currency.py calls out as "genuinely
#    multi-valued... merging them buys nothing [for supersession]" -- multi-
#    valued for supersession is exactly what makes them plural, compoundable
#    material for one sentence about a person's inner life.
#  - work/place/health families mirror currency.py's _ALIAS groups, which are
#    the store's own evidence that these names denote one concept.
_FAMILY = {
    # narrative / inner life
    "motivation": "narrative", "belief": "narrative", "value": "narrative",
    "feeling": "narrative", "reflection": "narrative",
    "preference": "narrative", "relationship_dynamic": "narrative",
    "plan": "narrative", "goal": "narrative",
    # work
    "occupation": "work", "job_title": "work", "employer": "work",
    "workplace": "work", "income": "work", "monthly_income": "work",
    "salary": "work",
    # place
    "location": "place", "residence": "place", "city": "place",
    "country": "place",
    # lifestyle
    "hobby": "lifestyle", "activity": "lifestyle", "routine": "lifestyle",
    "habit": "lifestyle",
    # health
    "health_condition": "health", "mental_health": "health",
}

CAP = 3

# The exact verb strings render() can produce, longest first so "plans to"
# is matched before a hypothetical shorter prefix would shadow it.
_VERBS = sorted(set(PR._VERBAL.values()), key=len, reverse=True)


def _family(attr):
    return _FAMILY.get(attr)


def _linkable(attr1, toks1, attr2, toks2):
    f1, f2 = _family(attr1), _family(attr2)
    if f1 is not None and f1 == f2:
        return True
    return len(toks1 & toks2) >= 2


def _cluster(items, cap):
    """items: [(idx, attr, value, toks)] -> groups of >=2 items, each capped."""
    groups, ginfo = [], []
    for it in items:
        _, attr, _, tk = it
        placed = False
        for g, gi in zip(groups, ginfo):
            if len(g) >= cap:
                continue
            if any(_linkable(attr, tk, a2, t2) for a2, t2 in gi):
                g.append(it)
                gi.append((attr, tk))
                placed = True
                break
        if not placed:
            groups.append([it])
            ginfo.append([(attr, tk)])
    return [g for g in groups if len(g) >= 2]


def _decompose(rendered, subject_text):
    """Split render()'s output back into (kind, verb, rest) so clauses can be
    rejoined without a repeated subject. Purely string slicing against text
    render() itself produced -- see module docstring on why this is not a
    second renderer."""
    poss_prefix = subject_text + "'s "
    verb_prefix = subject_text + " "
    if rendered.startswith(poss_prefix):
        return "poss", None, rendered[len(poss_prefix):]
    if rendered.startswith(verb_prefix):
        body = rendered[len(verb_prefix):]
        for verb in _VERBS:
            if body.startswith(verb + " "):
                return "verb", verb, body[len(verb) + 1:]
    # Defensive fallback (render() contract says this should not happen):
    # keep the whole clause intact rather than mangling it.
    return "full", None, rendered


def _render_group(facts, owner):
    subj_prefix, _ = PR.split_subject(facts[0].get("attr", ""))
    subject_text = (PR.titlecase_person(subj_prefix) if subj_prefix
                     else (PR.titlecase_person(owner) if owner else "The user"))

    clauses = []
    for f in facts:
        rendered = PR.render(f, owner=owner)
        if not rendered:
            continue
        clauses.append(_decompose(rendered, subject_text))
    if len(clauses) < 2:
        return None

    # Coalesce clauses that share the exact same verb, regardless of position,
    # so "enjoys reading" + "prefers X" + "enjoys hiking" still merges the two
    # "enjoys" clauses rather than only adjacent ones.
    merged = []
    seen_verb_pos = {}
    for kind, verb, rest in clauses:
        if kind == "verb" and verb in seen_verb_pos:
            idx = seen_verb_pos[verb]
            merged[idx][2] += " and " + rest
        else:
            if kind == "verb":
                seen_verb_pos[verb] = len(merged)
            merged.append([kind, verb, rest])

    sentence = None
    for kind, verb, rest in merged:
        if sentence is None:
            if kind == "verb":
                sentence = f"{subject_text} {verb} {rest}"
            elif kind == "poss":
                sentence = f"{subject_text}'s {rest}"
            else:
                sentence = rest
        else:
            if kind == "verb":
                sentence += f" and {verb} {rest}"
            elif kind == "poss":
                sentence += f", and {subject_text}'s {rest}"
            else:
                sentence += f"; {rest}"
    return sentence


def group_facts(facts, owner=None, cap=CAP):
    """The grouping half of compose(), split out so the grouping DECISION
    (which facts co-occur) is inspectable separately from the rendering. Used
    by compose() itself and by the offline measurement below, which needs
    real group sizes to build a null that is matched on group size, not just
    on total compound count -- see the __main__ block's note on why a count-
    only null overstates the null's coverage.

    -> list of fact-groups (each a list of >=2 of the input fact dicts)."""
    owner_toks = G.toks(owner) if owner else set()

    buckets = defaultdict(list)
    for i, f in enumerate(facts or []):
        if str(f.get("tier", "")).lower() == "retracted":
            continue
        attr = f.get("attr", "")
        value = f.get("value", "")
        if not attr or not value:
            continue
        subj, bare = PR.split_subject(attr)
        n = f.get("n_mentions", 1) or 1
        key = subj or "\x00owner"
        buckets[key].append((i, bare, str(value), n, f))

    groups = []
    for _, items in buckets.items():
        # Most-corroborated facts first, so when a family exceeds the cap the
        # best-evidenced facts are the ones kept together.
        items = sorted(items, key=lambda it: -it[3])
        cluster_in = [(i, bare, value, G.toks(value) - owner_toks)
                       for i, bare, value, _, _ in items]
        by_idx = {i: f for i, _, _, _, f in items}
        for g in _cluster(cluster_in, cap):
            groups.append([by_idx[i] for i, *_ in g])
    return groups


def compose(facts, owner=None, cap=CAP):
    """One session's facts (+ owner name) -> a small list of compound
    proposition strings. See module docstring for the grouping rule, the cap,
    and the grammar contract. Facts with tier "retracted" are never composed
    into a sentence stated as true. Returns [] for <2 facts or when nothing
    is linkable -- callers keep emitting every input fact as an atom
    regardless of what this returns."""
    out = []
    for g in group_facts(facts, owner=owner, cap=cap):
        sent = _render_group(g, owner)
        if sent:
            out.append(sent)
    return out


if __name__ == "__main__":
    import collections
    import json
    import re

    EVAL_DIR = os.path.expanduser("~/rg_private/halumem/official/HaluMem/eval")
    if EVAL_DIR not in sys.path:
        sys.path.insert(0, EVAL_DIR)
    os.chdir(EVAL_DIR)
    os.environ.setdefault("RG_EXTRACT_V5", "1")
    os.environ.setdefault("RG_INGEST_ALL_TURNS", "1")

    import halumem_run as H  # noqa: E402

    users_path = os.path.expanduser("~/rg_private/halumem/HaluMem-Medium.jsonl")
    cache_path = os.path.expanduser(
        "~/rg_private/halumem/dev/cache_u10_v5_14b.jsonl")
    u = [json.loads(l) for l in open(users_path)][10]
    mem, _ = H.ingest_user(u, cache_path=cache_path)

    # -- collect this user's atoms, grouped by session, in the same "attr,
    # value" shape compose() expects. WireGraph nodes carry convs: {conv_id:
    # date}; conv_id is "s{si}" per ingest_user, so the session index is
    # recoverable without touching gold.
    by_session = collections.defaultdict(list)
    all_atoms = []
    for nd in list(mem.g.nodes.values()) + list(mem.g.provisional.values()):
        fact = {"attr": nd["attr"], "value": nd["value"],
                "n_mentions": nd.get("n_mentions", 1)}
        all_atoms.append(fact)
        sis = set()
        for cid in nd.get("convs", {}):
            m = re.match(r"^s(\d+)$", str(cid))
            if m:
                sis.add(int(m.group(1)))
        for si in sis:
            by_session[si].append(fact)

    owner = PR.owner_name(all_atoms) or PR.owner_name(
        [f for fs in by_session.values() for f in fs])

    real_compounds = []
    real_group_sizes = []
    for si, facts in by_session.items():
        groups = group_facts(facts, owner=owner)
        real_group_sizes.extend(len(g) for g in groups)
        for g in groups:
            sent = _render_group(g, owner)
            if sent:
                real_compounds.append(sent)

    print(f"owner: {owner!r}")
    print(f"atoms: {len(all_atoms)}, sessions with facts: {len(by_session)}")
    print(f"real compounds: {len(real_compounds)}  "
          f"(mean group size {sum(real_group_sizes) / max(1, len(real_group_sizes)):.2f})")

    # -- THE NULL. A first cut of this null matched only the TOTAL compound
    # COUNT per session (merge_probe's random:k design) and the null WON at
    # every threshold -- because count-matching alone is not size-matching
    # here: this composer DROPS singleton groups (facts that link to no one
    # stay pure atoms, never counted), while a count-only null had to spread
    # an entire session's fact pool across the same, smaller number of
    # buckets, producing much BIGGER random records than the real ones by
    # construction. That is exactly the "coverage bought by record size, not
    # grouping quality" failure entries 151-153 exist to catch, just one
    # level indirect -- so this null is matched on GROUP SIZE too: for every
    # session, take the real algorithm's own group-size list (e.g. a 3 and
    # two 2s) and fill THOSE exact-sized buckets from a random shuffle of
    # that session's fact pool. Only "which facts land in the same bucket"
    # is randomized; how many facts and how many buckets is identical to the
    # real strategy, session by session.
    import random
    rng = random.Random(0)

    def null_compounds_for(by_session, owner, rng):
        out = []
        for si, facts in by_session.items():
            groups = group_facts(facts, owner=owner)
            sizes = [len(g) for g in groups]
            if not sizes:
                continue
            pool = list(facts)
            rng.shuffle(pool)
            pos = 0
            subj = PR.titlecase_person(owner) if owner else "The user"
            for k in sizes:
                chunk = pool[pos:pos + k]
                pos += k
                vals = " and ".join(PR._clean(f["value"]) for f in chunk)
                out.append(f"{subj}: {vals}")
        return out

    null_compounds = null_compounds_for(by_session, owner, rng)
    print(f"null compounds:  {len(null_compounds)}  "
          f"(same per-session group-size list as real, facts shuffled)")

    # -- gold, name-stripped (granularity.py's convention)
    gold = [mp for s in u["sessions"] for mp in s.get("memory_points", [])]
    owner_toks = G.toks(owner) if owner else set()

    def coverage(records, th):
        rtoks = [G.toks(r) for r in records]
        hit = 0
        for mp in gold:
            g = G.toks(mp.get("memory_content", "")) - owner_toks
            if not g:
                continue
            best = max((len(g & rt) / len(g) for rt in rtoks), default=0.0)
            hit += best >= th
        return hit, len([mp for mp in gold
                          if G.toks(mp.get("memory_content", "")) - owner_toks])

    print()
    print(f"{'strategy':<24}{'records':>9}", end="")
    for th in (0.4, 0.5, 0.6):
        print(f"{'cov@' + str(th):>10}", end="")
    print()

    strategies = {
        "atoms only": [PR.render(f, owner=owner) for f in all_atoms],
        "atoms + compounds": ([PR.render(f, owner=owner) for f in all_atoms]
                               + real_compounds),
        "atoms + NULL compounds": ([PR.render(f, owner=owner) for f in all_atoms]
                                    + null_compounds),
    }
    for name, records in strategies.items():
        records = [r for r in records if r]
        row = f"{name:<24}{len(records):>9}"
        for th in (0.4, 0.5, 0.6):
            hit, n = coverage(records, th)
            row += f"{hit / max(n, 1):>9.1%} "
        print(row)

    print("\n'records' is the denominator of target_accuracy; coverage bought")
    print("by shrinking it is not free. NULL uses the SAME per-session GROUP-SIZE")
    print("list as the real strategy (same record count AND same facts-per-record),")
    print("only which facts land together is randomized -- a real strategy has to")
    print("win on WHO it groups, not merely on having fewer, bigger records.")
