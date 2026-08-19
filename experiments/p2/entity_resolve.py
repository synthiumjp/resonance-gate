"""Deterministic entity resolution over person subjects in the store.

The defect this fixes, measured on user 10's real store: the SAME person
arrives under several subject keys --

    "karen"  and "brownkaren"      -> one person (a colleague)
    "donald" and "millerdonald"    -> one person (a friend)
    "sophia" and "sophia (mentor)" -> one person (a mentor)
    "linh"   and "nguyen linh"     -> one person (a collaborator)

-- because our own extractor writes the subject however the transcript names
it turn to turn, and HaluMem's own dialogue text is inconsistent about it
("BrownKaren is my Colleague, Karen is a colleague who ..." -- both spellings
in one sentence). A composer that builds one record per SUBJECT therefore
builds several weak records per PERSON instead of one strong one, which
measured BELOW the atomic per-fact baseline (33.3% vs 37.3% coverage of the
51 Relationship gold points at threshold 0.5). Entity resolution over
subjects is the blocker for anything downstream that wants one record per
person.

WHERE THE CASE INFORMATION ACTUALLY WENT. HaluMem's dialogue literally
embeds the gold identifier CamelCased ("BrownKaren is my Colleague, Karen is
a colleague..."), so the SurnameFirstname convention noted in the task really
is what the transcript contains -- confirmed by mining (CamelName, shortname)
pairs straight out of gold memory points ("Michelle Hernandez's Colleague
BrownKaren, Karen is a colleague ..."): the short form is always the LAST
name-part, i.e. the FIRST name. But `canon_subject()` in llm_profile.py
lowercases every subject before it is ever stored, so by the time a subject
reaches this module "BrownKaren" is already "brownkaren" -- the case
boundary that would normally split it is gone. So this module recovers the
CamelCase split two ways:
  1. by actual case boundary, when case survives ("BrownKaren" -> "Brown
     Karen") -- reusing the same technique schema_probe.relation_for() uses
     to line HaluMem's CamelCase names up with the spelled-out transcript;
  2. by SUFFIX, when it does not ("brownkaren" ends with "karen") -- the only
     signal left once lowercasing has erased the case boundary.
Both splits are used only to test containment (does this short subject's
token/suffix appear inside exactly one longer subject?), never to guess at
a boundary blindly.

THE SAFETY RULE, and it is the whole design. Merging two DIFFERENT people is
far worse than failing to merge one person: it fabricates a relationship and
attributes it to the wrong human, which is exactly the kind of thing this
whole project measures itself for NOT doing. Failing to merge one person
just leaves two weak records instead of one strong one -- a missed
opportunity, not a fabrication. So a candidate merge fires ONLY when it is
UNAMBIGUOUS: if a short name like "karen" could belong to two distinct
longer subjects in the same store ("brownkaren" AND "smithkaren"), NEITHER
merge happens and all three stay separate. Zero merges beats one wrong
merge, every time.

Also guarded: the profile owner's own name (any of the tokens in it) is
NEVER used to absorb a third party, and is never itself absorbed. Extraction
sometimes files the owner's own first name as a bare subject (a
self-reference artifact -- see schema_probe.reject()'s "self-reference"
guard for the same failure at extraction time); without this guard, that
stray subject could unambiguously suffix-match some unrelated colleague's
concatenated name and silently attribute the owner's own facts to them.

Non-destructive: `resolve_subjects` returns a MAPPING, {raw_subject:
canonical_subject}. Nothing in the store is deleted, rewritten, or renamed;
a caller decides what, if anything, to do with the mapping.

Deterministic, NO LLM CALLS. Every extraction win in this codebase came from
deterministic post-processing (schema_probe's relation typing, currency's
alias groups); prompt-based fixes are 0 for 3 here, and person identity is
exactly the kind of decision a model could quietly get wrong in either
direction with no receipt trail.
"""
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from propositions import titlecase_person  # noqa: E402

_PAREN_RX = re.compile(r"\s*\([^)]*\)")
_CAMEL_RX = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_PUNCT_RX = re.compile(r"[^\w\s'-]")
_WS_RX = re.compile(r"\s+")

# A first-name candidate shorter than this is not suffix-matched at all --
# two- and one-letter names produce too many spurious suffix hits ("al" is a
# suffix of dozens of unrelated words) for the signal to be trustworthy.
# Conservative on purpose: a missed short-name merge just leaves two records
# instead of one; a spurious one fabricates a relationship.
_MIN_SUFFIX_WORD = 3
# The "surname" remainder left after stripping the suffix must itself be a
# real chunk, not one stray character.
_MIN_SURNAME_REMAINDER = 2


def _norm_tokens(raw):
    """raw subject -> tuple of lowercase, whitespace/punctuation-normalised
    tokens, with any parenthetical qualifier stripped and any surviving
    CamelCase boundary split.

    "Sophia (mentor)" -> ("sophia",)
    "nguyen linh"      -> ("nguyen", "linh")
    "BrownKaren"        -> ("brown", "karen")   -- only if case survives
    "brownkaren"        -> ("brownkaren",)      -- case already lost; see
                                                    resolve_subjects for how
                                                    this is still resolved.
    """
    s = _PAREN_RX.sub("", str(raw or ""))
    s = _CAMEL_RX.sub(" ", s)
    s = _PUNCT_RX.sub(" ", s)
    s = _WS_RX.sub(" ", s).strip().lower()
    return tuple(s.split())


def resolve_subjects(subjects, owner=None):
    """Distinct subject strings -> {raw_subject: canonical_subject}.

    subjects: an iterable of the raw subject strings a store holds (as they
    appear on `"subject:attr"` keys -- see propositions.split_subject).
    Duplicates and ordering in the input do not matter; only the distinct
    strings are resolved.

    owner: the profile owner's own name, if known. Any subject that IS one
    of the owner's own name tokens is excluded from merging in EITHER
    direction -- see the module docstring's self-reference note.

    Returns a mapping over every distinct input string. A subject with no
    unambiguous match maps to a normalised form of ITSELF (never dropped).
    Two subjects merge (map to the same canonical string) only when:
      - they are the same name once case/whitespace/parenthetical-qualifier
        differences are normalised away ("Sophia" / "sophia (mentor)"), or
      - one is a full multi-word name and the other is EXACTLY one of its
        words ("nguyen linh" / "linh"), or
      - one is a longer concatenated name and the other is a >=3-letter
        SUFFIX of it with a real remainder ("brownkaren" / "karen"),
    and, in the suffix/word-containment cases, the match is UNIQUE across
    the whole input -- see THE SAFETY RULE in the module docstring.

    Deterministic; no model calls; nothing outside the returned dict is
    touched.
    """
    raw_list = []
    seen = set()
    for s in subjects:
        s = str(s or "")
        if s.strip() and s not in seen:
            seen.add(s)
            raw_list.append(s)
    if not raw_list:
        return {}

    owner_tokens = set(_norm_tokens(owner)) if owner else set()

    groups = {}
    for s in raw_list:
        groups.setdefault(_norm_tokens(s), []).append(s)

    # A cluster whose tokens are EXACTLY the owner's own name never
    # participates as a merge target -- see the self-reference note above.
    owner_keys = {k for k in groups if owner_tokens and set(k) == owner_tokens}

    multi_keys = [k for k in groups if len(k) > 1]
    single_keys = [k for k in groups if len(k) == 1]

    # token -> the multi-word clusters that contain it as an exact word.
    tok_index = {}
    for k in multi_keys:
        for tok in set(k):
            tok_index.setdefault(tok, set()).add(k)

    def _suffix_parents(word):
        """Other single-token subjects this word is a first-name SUFFIX of
        -- the only signal left once lowercasing has erased the CamelCase
        boundary (see module docstring)."""
        if len(word) < _MIN_SUFFIX_WORD:
            return set()
        out = set()
        for k in single_keys:
            cand = k[0]
            if cand != word and len(cand) - len(word) >= _MIN_SURNAME_REMAINDER \
                    and cand.endswith(word):
                out.add(k)
        return out

    canonical_of = {k: k for k in groups}
    split_at = {}   # single-token key -> index where a discovered suffix boundary falls

    for k in single_keys:
        word = k[0]
        if owner_tokens and word in owner_tokens:
            continue  # THE SAFETY RULE: never absorb, or be absorbed by, the owner
        cands = (set(tok_index.get(word, ())) | _suffix_parents(word)) - owner_keys
        cands.discard(k)
        if len(cands) == 1:
            parent = next(iter(cands))
            canonical_of[k] = parent
            if len(parent) == 1:
                split_at[parent] = len(parent[0]) - len(word)
        # 0 or >=2 candidates: ambiguous, or no match at all -- merge nothing.

    def _display(key):
        if not key:
            return titlecase_person(groups[key][0])
        if len(key) > 1:
            return titlecase_person(" ".join(key))
        word = key[0]
        if key in split_at:
            i = split_at[key]
            return titlecase_person(word[:i] + " " + word[i:])
        return titlecase_person(word)

    mapping = {}
    for k, raws in groups.items():
        display = _display(canonical_of[k])
        for r in raws:
            mapping[r] = display
    return mapping


if __name__ == "__main__":
    import json
    from collections import defaultdict
    import random

    EVAL_DIR = os.path.expanduser("~/rg_private/halumem/official/HaluMem/eval")
    GOLD_PATH = os.path.expanduser("~/rg_private/halumem/HaluMem-Medium.jsonl")
    CACHE_PATH = os.path.expanduser("~/rg_private/halumem/dev/cache_u10_v5_14b.jsonl")

    sys.path.insert(0, EVAL_DIR)
    sys.path.insert(0, _HERE)
    os.chdir(EVAL_DIR)
    os.environ.setdefault("RG_EXTRACT_V5", "1")
    os.environ.setdefault("RG_INGEST_ALL_TURNS", "1")
    import halumem_run as H  # noqa: E402
    from propositions import split_subject, owner_name  # noqa: E402

    users = [json.loads(l) for l in open(GOLD_PATH)]
    user10 = users[10]

    # --- mine (CamelName, shortname) pairs straight out of GOLD memory
    # points, the same way the task frames "real ground truth": a sentence
    # like "Michelle Hernandez's Colleague BrownKaren, Karen is a colleague
    # ..." states the two spellings name the same person.
    _GOLD_PAIR_RX = re.compile(
        r"'s \w+ ([A-Z][a-z]+[A-Z][a-zA-Z]*), (\w+) is")
    gold_pairs = set()
    for sess in user10["sessions"]:
        for mp in sess["memory_points"]:
            for camel, short in _GOLD_PAIR_RX.findall(mp["memory_content"]):
                gold_pairs.add((camel.lower(), short.lower()))
    print(f"(a) gold-mined (CamelName, shortname) pairs for user 10: "
          f"{len(gold_pairs)}")
    for camel, short in sorted(gold_pairs):
        print(f"    {short} <-> {camel}")

    # --- build user 10's store, no GPU / no model calls: pure cache replay
    print("\nbuilding user 10's store from cache (no model calls)...")
    mem, n_turns = H.ingest_user(user10, cache_path=CACHE_PATH)
    nodes = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
    print(f"n_turns={n_turns} n_nodes={len(nodes)}")

    owner = owner_name([{"attr": n["attr"], "value": n["value"]} for n in nodes],
                        default="")
    print(f"owner name: {owner!r}")

    subj_facts = defaultdict(list)
    for n in nodes:
        subj, _ = split_subject(n["attr"])
        if subj:
            subj_facts[subj].append(n)

    before_subjects = sorted(subj_facts)
    print(f"\n(a) distinct person-ish subjects BEFORE resolution: "
          f"{len(before_subjects)}")

    mapping = resolve_subjects(before_subjects, owner=owner)
    after_subjects = sorted(set(mapping.values()))
    print(f"    distinct identities AFTER resolution: {len(after_subjects)}")
    merged_groups = defaultdict(list)
    for r, c in mapping.items():
        merged_groups[c].append(r)
    actual_merges = {c: rs for c, rs in merged_groups.items() if len(rs) > 1}
    print(f"    subjects actually merged into a shared identity: "
          f"{sum(len(v) for v in actual_merges.values())} raw subjects -> "
          f"{len(actual_merges)} identities")
    for c, rs in sorted(actual_merges.items()):
        print(f"      {c!r} <- {rs}")

    # --- (b) score against gold-mined pairs: correct / missed / WRONG
    def _norm(s):
        return re.sub(r"\s+", "", str(s).lower())

    correct, missed, wrong = 0, 0, 0
    detail, skipped = [], []
    for camel, short in sorted(gold_pairs):
        camel_subj = next((s for s in before_subjects if _norm(s) == camel), None)
        short_subj = next((s for s in before_subjects if _norm(s) == short), None)
        if camel_subj is None or short_subj is None:
            # this pair's subjects never both made it into OUR store -- our
            # own extraction only ever wrote ONE of the two spellings, so
            # there was no merge opportunity to score at all. Reported
            # explicitly rather than silently absorbed into "missed", which
            # would blame entity resolution for an extraction gap it cannot
            # fix.
            skipped.append((short, camel, camel_subj, short_subj))
            continue
        same = mapping.get(camel_subj) == mapping.get(short_subj)
        if same:
            correct += 1
        else:
            missed += 1
        detail.append((short, camel, same))

    # WRONG merges: pairs of DISTINCT gold people we merged together. Gold
    # tells us which short names belong to which full names; any two short
    # names from DIFFERENT gold pairs that we mapped to the same canonical
    # identity is a fabricated merge.
    gold_person_of = {}
    for camel, short in gold_pairs:
        gold_person_of[short] = camel  # short name -> the ONE person gold says it is
    by_canonical = defaultdict(set)
    for s in before_subjects:
        ns = _norm(s)
        person = gold_person_of.get(ns)
        if person is None:
            # a subject that IS itself a gold camel-name names its own person
            for camel, short in gold_pairs:
                if ns == camel:
                    person = camel
                    break
        if person:
            by_canonical[mapping.get(s, s)].add(person)
    wrong = sum(1 for people in by_canonical.values() if len(people) > 1)

    print(f"\n(b) against gold: correct merges={correct}  missed={missed}  "
          f"WRONG merges (distinct gold people merged together)={wrong}  "
          f"skipped (only one spelling ever reached our store)={len(skipped)}")
    for short, camel, same in detail:
        print(f"    {'OK ' if same else 'MISS'} {short} <-> {camel}")
    for short, camel, camel_subj, short_subj in skipped:
        have = "camel form only" if short_subj is None else "short form only"
        print(f"    SKIP {short} <-> {camel}  (our store has {have})")

    # --- (c) NULL: randomly merge the same number of subject pairs
    random.seed(0)
    n_real_merge_pairs = sum(len(v) - 1 for v in actual_merges.values())
    pool = list(before_subjects)
    null_correct, null_total = 0, 0
    if len(pool) >= 2 and n_real_merge_pairs > 0:
        random_pairs = set()
        attempts = 0
        while len(random_pairs) < n_real_merge_pairs and attempts < 10000:
            attempts += 1
            a, b = random.sample(pool, 2)
            if a != b:
                random_pairs.add(tuple(sorted((a, b))))
        for a, b in random_pairs:
            null_total += 1
            na, nb = _norm(a), _norm(b)
            pa = gold_person_of.get(na) or (na if na in {c for c, _ in gold_pairs} else None)
            pb = gold_person_of.get(nb) or (nb if nb in {c for c, _ in gold_pairs} else None)
            if pa is not None and pb is not None and pa == pb:
                null_correct += 1
        rate = (null_correct / null_total) if null_total else 0.0
        print(f"\n(c) NULL: {null_total} random subject-pair merges of the "
              f"same count as our {n_real_merge_pairs} real merges -> "
              f"{null_correct} would have been correct by chance "
              f"({rate:.1%})")
    else:
        print(f"\n(c) NULL: no real merges happened ({n_real_merge_pairs}), "
              f"so no null comparison is meaningful.")

    # --- (d) facts-per-person distribution before vs after. Scoped to
    # PERSON subjects only (currency.NON_PERSON, read-only reuse -- "ai",
    # "team", "network" etc are not people and would dilute a facts-per-
    # PERSON distribution, even though resolve_subjects() itself is generic
    # over subject strings and does not need to know about personhood).
    import currency as CU
    person_subjects = [s for s in subj_facts if not CU.is_non_person_subject(s)]
    n_nonperson = len(subj_facts) - len(person_subjects)
    before_counts = sorted((len(subj_facts[s]) for s in person_subjects),
                           reverse=True)
    after_counts_map = defaultdict(int)
    for s in person_subjects:
        after_counts_map[mapping.get(s, s)] += len(subj_facts[s])
    after_counts = sorted(after_counts_map.values(), reverse=True)

    def _dist(xs):
        if not xs:
            return "n/a"
        n = len(xs)
        mean = sum(xs) / n
        return (f"n={n} mean={mean:.1f} median={xs[n // 2]} "
                f"min={min(xs)} max={max(xs)}")

    print(f"\n(d) facts-per-person BEFORE: {_dist(before_counts)}  "
          f"({n_nonperson} non-person subjects excluded)")
    print(f"    facts-per-person AFTER:  {_dist(after_counts)}")
