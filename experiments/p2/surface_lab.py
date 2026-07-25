"""p2 SURFACE LAB (entry: firewalled dev-set retrieval fix, users 10-12,
14B v5.1 caches): a deterministic evaluation harness for the
retrieval/selection/composition layer that sits between the store
(ingest_user, measured at 55.6% oracle gold-in-store on this set) and the
answer surface (answer_question(surface="plain"), measured at 14% composed /
3% of compositions containing gold / 67% of compositions on Unknown-gold
questions before this fix).

Two numbers, no model call anywhere:
  DELIVERED           -- % of real-gold questions (gold is a genuine value,
                          not a Memory Boundary "Unknown"/"not provided"/
                          "not mentioned"/"not specified" answer) whose FINAL
                          plain-surface answer string contains >=50% of the
                          gold answer's content tokens.
  COMPOSED-ON-UNKNOWN  -- % of Unknown-gold questions that get a composed
                          (non-"Unknown.") answer -- the false-positive rate
                          of the abstention boundary.
  composed-rate        -- % of ALL questions that get a composed answer
                          (context, not a target).

TARGETS: DELIVERED >= 35% (ceiling 55.6% per oracle.py), COMPOSED-ON-UNKNOWN
<= 25%, and the boundary preserved (Unknown-gold questions overwhelmingly
still get "Unknown.").

Root cause verified by direct instrumentation (see entry): every HaluMem
question names the persona's full name ("What is Michelle Hernandez's job
title as of Sep 5, 2025?"). Two consequences, both in WireGraph.match():
  (a) the name tokens win a PERFECT-overlap direct match against the store's
      own name=<full name> fact (a single-mention, answer-free node), so
      the highest-scoring "seed" is almost always a fact that cannot answer
      anything;
  (b) worse, the synonym-bridge match's "unexplained" guard treats the
      persona's own name tokens (never present on an occupation/income/etc.
      node) as UNEXPLAINED CONTENT, so it blocks the synonym match outright
      for the actual answering attribute on ~every question. Date words
      ("as", "on", "September", "2025") do the same thing a second time.
The store has the answer; match() was refusing to even retrieve it.

Policy under test (see FIXED_MATCH / Cfg below):
  FIX A (match, wire.py): subtract the persona's own name tokens (derived,
      non-generatively, from the store's own highest-mention attr=="name"
      fact -- never from the question) from the query before scoring, and
      extend the synonym-guard's "unexplained" check to forgive date-ish
      tokens (years/months/days) and date-framing prepositions ("as",
      "on", "by") the same way it already forgives question-framing words.
  FIX B (selection, halumem_run.py): the existing date-scoping (Fix 2) only
      narrowed the asserted/wired tiers to the asked date; the unconfirmed
      (provisional, single-mention) tier -- where most of an 800-fact
      long-tail answer actually lives -- passed through unfiltered. Extend
      the SAME date intersection to unconfirmed.
  FIX C (ask-token hygiene, halumem_run.py): _ask_tokens and the compose
      gate's "uncovered" calculation also subtract the persona name tokens
      and date-framing prepositions, so the coverage gate is not blocked or
      misled by tokens that were never answerable in the first place.
  cap sweep / gate sweep: measured, not assumed -- see variants below.

Usage: surface_lab.py [--users 10-12] [--min-mentions 2]
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
import wire as W
from wire import (WireGraph, _tokens, extract_dates, _STOP, _QWORDS, _MONTHS,
                   _QUERY_SYNONYMS as _BASE_SYNONYMS, MATCH_MIN)

# FIX G: narrow-bucket synonym additions, each verified against the ACTUAL
# attribute vocabulary the v5.1 extractor produces on this dev set (low
# fact-count buckets where an attribute bridge is unambiguous and cheap --
# unlike the mega-buckets "preference"/"motivation"/"plan"/"belief"/"value"
# with 250-600+ facts each, where attribute alone cannot discriminate the
# one relevant fact and a value-token fallback (FIX F, below) is used
# instead). Merged with, never replacing, the shipped table.
_EXTRA_SYNONYMS = {
    "disease": "health_condition", "diagnosed": "health_condition",
    "condition": "health_condition", "illness": "health_condition",
    "medical": "health_condition", "chronic": "health_condition",
    "birth": "birth_date", "birthday": "birth_date", "born": "birth_date",
    "mental": "mental_health",
    "gender": "gender",
    "goal": "goal", "aim": "goal", "objective": "goal",
    "field": "discipline", "discipline": "discipline",
}
_QUERY_SYNONYMS = {**_BASE_SYNONYMS, **_EXTRA_SYNONYMS}

HALUMEM_PATH = os.path.expanduser("~/rg_private/halumem/HaluMem-Medium.jsonl")
CACHE_TEMPLATE = os.path.expanduser(
    "~/rg_private/halumem/dev/cache_u{i}_v5_14b.jsonl")

_NO_INFO_RX = re.compile(
    r"\b(unknown|not provided|not mentioned|not specified)\b", re.I)

_DATE_PREP = {"as", "on", "by"}
_DATEISH_WORDS = set(_MONTHS) | set(_MONTHS.values())
_YEAR_DAY_RX = re.compile(r"^(?:(?:19|20)\d{2}|\d{1,2})$")


def _is_dateish(t):
    return t in _DATEISH_WORDS or bool(_YEAR_DAY_RX.match(t))


# ---------------------------------------------------------------------------
# FIX H: "as of <date>" LATEST-VALID-FACT resolution (root cause (d)). The
# existing date-scoping (Fix 2 in halumem_run.py) only keeps facts whose
# receipt shares a literal date TOKEN with the question -- exact-day
# questions ("as of Sep 5, 2025") work, but "current/as of <a date nothing
# was said on>" questions (very common -- attributes like occupation change
# repeatedly across the persona's timeline) always come up empty and fall
# through to date_scoped_empty. This is real DATE ARITHMETIC (the one place
# in this lab that is NOT pure token-set overlap) but still fully
# receipted/deterministic/non-generative: it compares parsed (year, month,
# day) tuples from the SAME receipt date strings already stored, and picks
# the fact(s) whose most recent receipt is <= the asked date -- i.e. "the
# value that was true as of that date", never inventing a date or a value.
# ---------------------------------------------------------------------------

_MONTH_NUM = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"])}
_RECEIPT_RX = re.compile(
    r"\b(" + "|".join(_MONTH_NUM) + r")[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})\b", re.I)
_TEXT_DATE_RX = re.compile(
    r"\b(" + "|".join(_MONTH_NUM) + r")[a-z]*\.?\s*(\d{1,2})?,?\s*(\d{4})?\b", re.I)
_TEXT_YEAR_RX = re.compile(r"\b(19\d{2}|20\d{2})\b")


def _parse_receipt_date(s):
    """A receipt date string is always 'Mon DD, YYYY' (ingest_user's
    truncation of the session start_time) -- exact parse, no ambiguity."""
    m = _RECEIPT_RX.search(str(s))
    if not m:
        return None
    return (int(m.group(3)), _MONTH_NUM[m.group(1).lower()[:3]], int(m.group(2)))


def _parse_query_date(q):
    """Best-effort (year, month, day) from question text -- missing
    components are None (a bare year, or a month+year with no day)."""
    m = _TEXT_DATE_RX.search(q)
    if m and (m.group(1) or m.group(3)):
        month = _MONTH_NUM[m.group(1).lower()[:3]] if m.group(1) else None
        day = int(m.group(2)) if m.group(2) else None
        year = int(m.group(3)) if m.group(3) else None
        if month or year:
            return (year, month, day)
    m = _TEXT_YEAR_RX.search(q)
    if m:
        return (int(m.group(1)), None, None)
    return None


def _pad_upper(t):
    y, m, d = t
    return (y if y is not None else 9999,
            m if m is not None else 12,
            d if d is not None else 31)


# FIX I: SPECIFICITY GATE -- a cheap, purely lexical check for questions
# that ask for an atomic value of a recognizable TYPE (a number: salary,
# ranking, count; a proper name: "who", "friend's name") that the selected
# facts do not contain ANY token of that type. This is the plain-surface
# analogue of halumem_run.answer_question's existing labeled-surface
# "VALUE-TYPE DISCLAIMER" -- same principle (don't let topic-relatedness
# read as answering a specific-typed ask), applied as an abstain instead of
# a disclaimer since the plain surface has no room for hedging language.
_NUMERIC_TRIGGERS = {"salary", "amount", "number", "ranking", "score", "rank",
                      "many", "much", "cost", "price", "toppings", "count"}
_NAME_TRIGGERS = {"name"}


def _specificity_ok(q_toks, facts):
    if q_toks & _NUMERIC_TRIGGERS:
        if not any(re.search(r"\d", f["value"]) for f in facts):
            return False
    if q_toks & _NAME_TRIGGERS:
        if not any("name" in f["attribute"] for f in facts):
            return False
    return True


def _fact_latest_receipt(f):
    dates = [_parse_receipt_date(rc["date"]) for rc in f.get("receipts", []) or []]
    dates = [d for d in dates if d]
    return max(dates) if dates else None


def _asof_select(facts, q_date):
    """Among `facts`, the subset whose most recent receipt is <= the asked
    date, restricted to those with the LATEST such receipt (ties kept --
    several attributes may have last changed on the same date). Returns []
    if no fact has any receipt at or before the asked date (never guesses
    forward in time)."""
    qd = _pad_upper(q_date)
    dated = [(d, f) for f in facts if (d := _fact_latest_receipt(f)) and d <= qd]
    if not dated:
        return []
    best = max(d for d, _ in dated)
    return [f for d, f in dated if d == best]


def persona_tokens(g):
    """The persona's own name tokens, derived from the STORE (never from the
    question): the highest-mention subject-less attr=='name' fact's value,
    across both tiers. Purely a lookup into already-extracted, receipted
    facts -- non-generative, and empty (no-op) whenever no name fact was
    extracted."""
    cands = [nd for nd in list(g.nodes.values()) + list(g.provisional.values())
              if nd["attr"] == "name"]
    if not cands:
        return frozenset()
    best = max(cands, key=lambda nd: nd["n_mentions"])
    return frozenset(_tokens(best["value"]))


# ---------------------------------------------------------------------------
# FIX A: WireGraph.match() with persona-token subtraction + date-word/prep
# forgiveness in the synonym-bridge "unexplained" guard. Same shape/contract
# as the shipped match(): non-generative token grounding, [] on no match.
# ---------------------------------------------------------------------------

def match_fixed(self, query, store=None):
    q = _tokens(query)
    if not q:
        return []
    persona = getattr(self, "_persona_toks", None)
    if persona is None:
        persona = persona_tokens(self)
        self._persona_toks = persona
    qeff = (q - persona) or q     # never let subtraction empty the query out
    syn_attrs = {_QUERY_SYNONYMS[t] for t in qeff if t in _QUERY_SYNONYMS}
    hits = []
    for nid, nd in (self.nodes if store is None else store).items():
        nt = _tokens(nd["attr"]) | nd["toks"]
        if not nt:
            continue
        ov = len(qeff & nt) / min(len(qeff), len(nt))
        if ov < MATCH_MIN and syn_attrs & _tokens(nd["attr"]):
            unexplained = qeff - nt - set(_QUERY_SYNONYMS) - _QWORDS - _DATE_PREP
            unexplained = {t for t in unexplained if not _is_dateish(t)}
            if not unexplained:
                ov = MATCH_MIN
        if ov >= MATCH_MIN:
            hits.append((ov, nd["n_mentions"], nid))
    hits.sort(reverse=True)
    return [(sc, nid) for sc, _, nid in hits]


class MatchPatch:
    """Installs match_fixed on WireGraph for the block; restores the
    original after. A variant with match_on=False runs the SHIPPED match()
    unmodified, for an honest before/after comparison."""

    def __init__(self, on):
        self.on = on
        self._orig = WireGraph.match

    def __enter__(self):
        if self.on:
            WireGraph.match = match_fixed
        return self

    def __exit__(self, *a):
        WireGraph.match = self._orig


# ---------------------------------------------------------------------------
# Selection / composition variants (FIX B, FIX C, gate/cap sweep). Mirrors
# halumem_run.answer_question's plain-surface path structurally; every knob
# is a documented, named policy choice, never a per-question special case.
# ---------------------------------------------------------------------------

def _subject_of(attr):
    """attr strings are 'subj:attr' for facts about someone other than the
    persona (see halumem_run.ingest_user's slot key), plain 'attr' for the
    persona's own facts. Returns the subject token set, or None (self)."""
    if ":" not in attr:
        return None
    return _tokens(attr.split(":", 1)[0])


def _subject_ok(f, q_toks):
    """FIX D: a subject-scoped fact ('sophia:occupation', 'team:occupation')
    answers a question about someone ELSE, not the persona -- it must only
    be offered as a candidate when the query actually names that subject.
    Otherwise a 'what is Michelle's job' query is free to be answered by
    Michelle's MENTOR's occupation, which shares the same attribute after
    the synonym bridge but is not what was asked. Self facts always pass."""
    subj = _subject_of(f["attribute"])
    return subj is None or (subj & q_toks)


_DAY_RX = re.compile(r"-\d+$")


def _date_level(dates):
    if any(_DAY_RX.search(d) for d in dates):
        return "day"
    if any(d in _MONTHS.values() for d in dates):
        return "month"
    return "year"


def _fact_dates_at(fdates, level):
    """Fact date tokens filtered to the given granularity only -- so a bare
    shared YEAR (present on almost every long-running fact) cannot satisfy
    a query that named an exact day."""
    if level == "day":
        return {d for d in fdates if _DAY_RX.search(d)}
    if level == "month":
        return {d for d in fdates if d in _MONTHS.values()}
    return fdates


class Cfg:
    def __init__(self, name, *, persona_in_ask=False, date_scope_unconfirmed=False,
                 cap_asserted=6, cap_wired=4, cap_unconfirmed=3, top=12,
                 gate="majority", subject_filter=False, date_granularity=False,
                 value_fallback=False, value_fallback_min=2,
                 value_fallback_always=False, date_latest=False,
                 value_fallback_rare_df=None, specificity_gate=False):
        self.name = name
        self.persona_in_ask = persona_in_ask
        self.date_scope_unconfirmed = date_scope_unconfirmed
        self.cap_asserted = cap_asserted
        self.cap_wired = cap_wired
        self.cap_unconfirmed = cap_unconfirmed
        self.top = top
        self.gate = gate
        self.subject_filter = subject_filter
        self.date_granularity = date_granularity
        self.value_fallback = value_fallback
        self.value_fallback_min = value_fallback_min
        self.value_fallback_always = value_fallback_always
        self.date_latest = date_latest
        self.value_fallback_rare_df = value_fallback_rare_df
        self.specificity_gate = specificity_gate

    def should_abstain(self, unc, ask_all):
        if not ask_all:
            return False
        if self.gate == "majority":
            return 2 * len(unc) >= len(ask_all)
        if self.gate == "any":              # abstain only if NOTHING covered
            return len(unc) >= len(ask_all)
        if self.gate == "strict":           # abstain if ANYTHING uncovered
            return len(unc) > 0
        if isinstance(self.gate, float):    # abstain if covered fraction < gate
            covered = len(ask_all) - len(unc)
            return covered / len(ask_all) < self.gate
        raise ValueError(self.gate)


RARE_DF = 3   # a token appearing in at most this many distinct fact VALUES
              # in the store counts as "specific enough" for a single-token
              # fallback match; a token seen everywhere ("work", "time",
              # "health") needs a second co-occurring token to count.


def _value_doc_freq(mem):
    """Document frequency of each content token over every stored fact's
    VALUE (both tiers) -- a purely distributional, non-generative measure of
    how generic vs. specific a word is IN THIS STORE. Cached on the graph."""
    df = getattr(mem.g, "_value_df", None)
    if df is not None:
        return df
    df = defaultdict(int)
    for nd in list(mem.g.nodes.values()) + list(mem.g.provisional.values()):
        for t in _tokens(nd["value"]):
            df[t] += 1
    mem.g._value_df = df
    return df


def _value_fallback_facts(mem, q_toks, min_shared, rare_df=None):
    """FIX F: LAST-RESORT literal grounding for the mega-buckets (preference/
    motivation/plan/belief/value/...) where attribute-bridging cannot
    discriminate one fact among hundreds. If the query's own content words
    (already stripped of persona/QWORDS/STOP/date-noise by the caller)
    share >= min_shared literal tokens with a stored fact's VALUE, the fact
    is offered as a candidate -- still non-generative (a stored, receipted
    value; the SAME literal-overlap principle as the primary match, just
    without requiring the attribute to also line up).

    rare_df (optional): a SINGLE shared token also counts if that token's
    document frequency across the store is <= rare_df -- a distinctive word
    ("sushi", "diabetes") is strong enough evidence on its own, while a
    generic one ("work", "health") is not and still needs a second
    co-occurring token. Purely a term-frequency count over the store, not a
    semantic judgement. Returned facts are dict-shaped like Memory._fact so
    they flow through the same rank/cap/date-scope/compose pipeline as any
    other candidate."""
    df = _value_doc_freq(mem) if rare_df is not None else None
    out = []
    for nd in list(mem.g.nodes.values()) + list(mem.g.provisional.values()):
        vt = _tokens(nd["value"])
        shared = q_toks & vt
        ok = len(shared) >= min_shared
        if not ok and rare_df is not None and shared:
            ok = any(df[t] <= rare_df for t in shared)
        if ok:
            out.append(mem._fact(nd, provisional=(nd["tier"] == "provisional")))
    return out


def _ask_tokens2(q, facts, persona):
    val_toks = set()
    for f in facts:
        val_toks |= _tokens(f["value"])
    return _tokens(q) - val_toks - _STOP - _QWORDS - persona


def answer_plain(mem, q, cfg):
    """Reimplementation of halumem_run.answer_question(surface='plain'),
    parameterized by cfg for A/B measurement. Falls back to "Unknown." on
    every abstain path, exactly like the shipped function; composes ONLY
    stored fact values, never new words -- same non-generative contract."""
    persona = getattr(mem.g, "_persona_toks", None)
    if persona is None:
        persona = persona_tokens(mem.g)
        mem.g._persona_toks = persona
    persona_use = persona if cfg.persona_in_ask else frozenset()

    r = mem.recall(q, top=cfg.top)
    q_toks_raw = _tokens(q)
    if not r["found"]:
        if not cfg.value_fallback:
            return "Unknown."
        qc = (q_toks_raw - persona_use - _QWORDS - _DATE_PREP)
        qc = {t for t in qc if not _is_dateish(t)}
        fallback = _value_fallback_facts(mem, qc, cfg.value_fallback_min,
                                         cfg.value_fallback_rare_df)
        if not fallback:
            return "Unknown."
        r = {"found": True, "asserted": [], "wired": [], "unconfirmed": fallback}
    elif cfg.value_fallback and cfg.value_fallback_always:
        qc = (q_toks_raw - persona_use - _QWORDS - _DATE_PREP)
        qc = {t for t in qc if not _is_dateish(t)}
        extra = _value_fallback_facts(mem, qc, cfg.value_fallback_min,
                                      cfg.value_fallback_rare_df)
        have = {f["attribute"] + "=" + f["value"] for f in r["unconfirmed"]}
        r = dict(r)
        r["unconfirmed"] = r["unconfirmed"] + [
            f for f in extra if f["attribute"] + "=" + f["value"] not in have]

    if cfg.subject_filter:
        r = dict(r)
        r["asserted"] = [f for f in r["asserted"] if _subject_ok(f, q_toks_raw)]
        r["wired"] = [w for w in r["wired"] if _subject_ok(w["fact"], q_toks_raw)]
        r["unconfirmed"] = [f for f in r["unconfirmed"] if _subject_ok(f, q_toks_raw)]

    all_facts = (r["asserted"] + [w["fact"] for w in r["wired"]] + r["unconfirmed"])
    ask = _ask_tokens2(q, all_facts, persona_use)

    def _rank(fs):
        return sorted(fs, key=lambda f: -len(
            (_tokens(f["attribute"]) | _tokens(f["value"])) & ask))

    # FIX H: "as-of" latest-valid-fact resolution, PRE-cap and PRE-rank (a
    # narrow-cap selection could otherwise drop the one temporally-correct
    # fact before this stage ever sees it) -- grouped by base attribute so a
    # multi-attribute question keeps one latest-valid answer per attribute,
    # not a single global "most recent fact regardless of topic".
    if cfg.date_latest:
        q_date = _parse_query_date(q)
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
                picked = _asof_select(fs, q_date)
                (keep_a if tier == "a" else keep_w if tier == "w" else keep_u
                 ).extend(picked)
            if keep_a or keep_w or keep_u:
                r = dict(r)
                r["asserted"], r["unconfirmed"] = keep_a, keep_u
                r["wired"] = [w for w in r["wired"] if w["fact"] in keep_w]

    asserted = _rank(r["asserted"])[:cfg.cap_asserted]
    wired = _rank([w["fact"] for w in r["wired"]])[:cfg.cap_wired]
    unconfirmed = _rank(r["unconfirmed"])[:cfg.cap_unconfirmed]

    q_dates = extract_dates(q) if not cfg.date_latest else set()
    date_scoped_empty = False
    if q_dates:
        level = _date_level(q_dates) if cfg.date_granularity else None
        qd = _fact_dates_at(q_dates, level) if level else q_dates

        def _hit(f):
            fd = HR._fact_dates(f)
            if level:
                fd = _fact_dates_at(fd, level)
            return fd & qd

        a_hit = [f for f in asserted if _hit(f)]
        w_hit = [f for f in wired if _hit(f)]
        if cfg.date_scope_unconfirmed:
            u_hit = [f for f in unconfirmed if _hit(f)]
        else:
            u_hit = None
        any_hit = a_hit or w_hit or (u_hit is not None and u_hit)
        if any_hit:
            asserted, wired = a_hit, w_hit
            if u_hit is not None:
                unconfirmed = u_hit
        else:
            date_scoped_empty = True

    facts = asserted + wired + unconfirmed
    if not facts:
        return "Unknown."

    attr_val_toks, attr_toks = set(), set()
    for f in facts:
        attr_val_toks |= _tokens(f["attribute"]) | _tokens(f["value"])
        attr_toks |= _tokens(f["attribute"])
    uncovered = _tokens(q) - attr_val_toks - _STOP - _QWORDS - persona_use
    uncovered = {t for t in uncovered if _QUERY_SYNONYMS.get(t) not in attr_toks}

    ask_all = {t for t in (_tokens(q) - _STOP - _QWORDS - persona_use)
               if not t.isdigit() and t not in _MONTHS and t not in _DATE_PREP}
    unc = uncovered & ask_all
    if cfg.specificity_gate and not _specificity_ok(q_toks_raw, facts):
        return "Unknown."
    if date_scoped_empty or cfg.should_abstain(unc, ask_all):
        return "Unknown."
    return "; ".join(f["value"] for f in asserted + wired + unconfirmed)


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

def _is_unknown_gold(gold):
    return bool(_NO_INFO_RX.search(str(gold)))


def _delivered(gold, answer):
    gt = _tokens(gold)
    if not gt:
        return False
    at = _tokens(answer)
    return len(gt & at) / len(gt) >= 0.5


def load_dev_users(user_indices, min_mentions=2, cache_template=CACHE_TEMPLATE):
    all_users = [json.loads(l) for l in open(HALUMEM_PATH)]
    mems = {}
    for uidx in user_indices:
        cache_path = cache_template.format(i=uidx)
        mem, n_turns = HR.ingest_user(all_users[uidx], cache_path, min_mentions)
        qs = [q for s in all_users[uidx]["sessions"] for q in s.get("questions", [])]
        mems[uidx] = (mem, qs)
    return mems


def score_variant(mems, match_on, cfg):
    """Runs cfg (plus FIX A match on/off) over every user's questions.
    Returns the aggregate table row + composed-rate + n."""
    n_real, n_delivered = 0, 0
    n_unk, n_unk_composed = 0, 0
    n_total, n_composed = 0, 0
    with MatchPatch(match_on):
        for uidx, (mem, qs) in mems.items():
            # persona cache depends on which match() is installed only
            # insofar as persona_tokens() itself doesn't call match() (it
            # doesn't) -- but reset the graph cache per variant run so a
            # stale persona from a previous pass never leaks across cfgs.
            mem.g._persona_toks = None
            for q in qs:
                gold = str(q.get("answer", "")).strip()
                ans = answer_plain(mem, q["question"], cfg)
                n_total += 1
                composed = ans != "Unknown."
                if composed:
                    n_composed += 1
                if _is_unknown_gold(gold):
                    n_unk += 1
                    if composed:
                        n_unk_composed += 1
                elif gold:
                    n_real += 1
                    if _delivered(gold, ans):
                        n_delivered += 1
    return {
        "n_total": n_total,
        "composed_rate": 100 * n_composed / max(n_total, 1),
        "delivered": 100 * n_delivered / max(n_real, 1),
        "n_real": n_real, "n_delivered": n_delivered,
        "composed_on_unknown": 100 * n_unk_composed / max(n_unk, 1),
        "n_unk": n_unk, "n_unk_composed": n_unk_composed,
    }


VARIANTS = [
    ("V0 baseline (shipped match+compose)",
     False, Cfg("V0")),
    ("V1 +FIX A (persona/date-aware match)",
     True, Cfg("V1")),
    ("V2 +FIX C (persona/date in ask+gate)",
     True, Cfg("V2", persona_in_ask=True)),
    ("V3 +FIX B (date-scope unconfirmed too)",
     True, Cfg("V3", persona_in_ask=True, date_scope_unconfirmed=True)),
    ("V4 V3 + bigger unconfirmed cap (3->8)",
     True, Cfg("V4", persona_in_ask=True, date_scope_unconfirmed=True,
                cap_unconfirmed=8)),
    ("V5 V3 + bigger candidate pool (top 12->40)",
     True, Cfg("V5", persona_in_ask=True, date_scope_unconfirmed=True, top=40)),
    ("V6 V3 + permissive gate ('any' coverage)",
     True, Cfg("V6", persona_in_ask=True, date_scope_unconfirmed=True, gate="any")),
    ("V7 V3 + strict gate (abstain on ANY gap)",
     True, Cfg("V7", persona_in_ask=True, date_scope_unconfirmed=True, gate="strict")),
    ("V8 V3 + unconfirmed cap 6",
     True, Cfg("V8", persona_in_ask=True, date_scope_unconfirmed=True,
                cap_unconfirmed=6)),
    ("V9 V3 + FIX D (subject filter)",
     True, Cfg("V9", persona_in_ask=True, date_scope_unconfirmed=True,
                subject_filter=True)),
    ("V10 V9 + FIX E (date granularity)",
     True, Cfg("V10", persona_in_ask=True, date_scope_unconfirmed=True,
                subject_filter=True, date_granularity=True)),
    ("V11 V10 + unconfirmed cap 8",
     True, Cfg("V11", persona_in_ask=True, date_scope_unconfirmed=True,
                subject_filter=True, date_granularity=True, cap_unconfirmed=8)),
    ("V12 V10 + unconfirmed cap 12",
     True, Cfg("V12", persona_in_ask=True, date_scope_unconfirmed=True,
                subject_filter=True, date_granularity=True, cap_unconfirmed=12)),
    ("V13 V10 + gate 'any'",
     True, Cfg("V13", persona_in_ask=True, date_scope_unconfirmed=True,
                subject_filter=True, date_granularity=True, gate="any")),
    ("V14 V10 + FIX F (value fallback >=2)",
     True, Cfg("V14", persona_in_ask=True, date_scope_unconfirmed=True,
                subject_filter=True, date_granularity=True,
                value_fallback=True, value_fallback_min=2, cap_unconfirmed=6)),
    ("V15 V14 + value fallback >=3",
     True, Cfg("V15", persona_in_ask=True, date_scope_unconfirmed=True,
                subject_filter=True, date_granularity=True,
                value_fallback=True, value_fallback_min=3, cap_unconfirmed=6)),
    ("V16 V14 + value fallback >=1",
     True, Cfg("V16", persona_in_ask=True, date_scope_unconfirmed=True,
                subject_filter=True, date_granularity=True,
                value_fallback=True, value_fallback_min=1, cap_unconfirmed=6)),
    ("V17 V14 + fallback ALWAYS merged, cap 10",
     True, Cfg("V17", persona_in_ask=True, date_scope_unconfirmed=True,
                subject_filter=True, date_granularity=True,
                value_fallback=True, value_fallback_min=2,
                value_fallback_always=True, cap_unconfirmed=10)),
    ("V18 V17 + cap 15",
     True, Cfg("V18", persona_in_ask=True, date_scope_unconfirmed=True,
                subject_filter=True, date_granularity=True,
                value_fallback=True, value_fallback_min=2,
                value_fallback_always=True, cap_unconfirmed=15)),
    ("V19 V17 + gate 'any'",
     True, Cfg("V19", persona_in_ask=True, date_scope_unconfirmed=True,
                subject_filter=True, date_granularity=True,
                value_fallback=True, value_fallback_min=2,
                value_fallback_always=True, cap_unconfirmed=10, gate="any")),
    ("V20 V19 + cap 20",
     True, Cfg("V20", persona_in_ask=True, date_scope_unconfirmed=True,
                subject_filter=True, date_granularity=True,
                value_fallback=True, value_fallback_min=2,
                value_fallback_always=True, cap_unconfirmed=20, gate="any")),
    ("V21 V19 + fallback min=1",
     True, Cfg("V21", persona_in_ask=True, date_scope_unconfirmed=True,
                subject_filter=True, date_granularity=True,
                value_fallback=True, value_fallback_min=1,
                value_fallback_always=True, cap_unconfirmed=20, gate="any")),
    ("V22 V19 + cap 40",
     True, Cfg("V22", persona_in_ask=True, date_scope_unconfirmed=True,
                subject_filter=True, date_granularity=True,
                value_fallback=True, value_fallback_min=2,
                value_fallback_always=True, cap_unconfirmed=40, gate="any")),
    ("V23 V22 + cap_asserted/wired 20",
     True, Cfg("V23", persona_in_ask=True, date_scope_unconfirmed=True,
                subject_filter=True, date_granularity=True,
                value_fallback=True, value_fallback_min=2,
                value_fallback_always=True, cap_unconfirmed=40,
                cap_asserted=20, cap_wired=20, gate="any")),
    ("V24 V23 + FIX H (as-of latest fact)",
     True, Cfg("V24", persona_in_ask=True, subject_filter=True,
                value_fallback=True, value_fallback_min=2,
                value_fallback_always=True, cap_unconfirmed=40,
                cap_asserted=20, cap_wired=20, gate="any", date_latest=True)),
    ("V25 V24 + gate majority",
     True, Cfg("V25", persona_in_ask=True, subject_filter=True,
                value_fallback=True, value_fallback_min=2,
                value_fallback_always=True, cap_unconfirmed=40,
                cap_asserted=20, cap_wired=20, gate="majority", date_latest=True)),
    ("V26 V24 + fallback min=1",
     True, Cfg("V26", persona_in_ask=True, subject_filter=True,
                value_fallback=True, value_fallback_min=1,
                value_fallback_always=True, cap_unconfirmed=40,
                cap_asserted=20, cap_wired=20, gate="any", date_latest=True)),
    ("V27 V24 + date_scope_unconfirmed too",
     True, Cfg("V27", persona_in_ask=True, subject_filter=True,
                date_scope_unconfirmed=True,
                value_fallback=True, value_fallback_min=2,
                value_fallback_always=True, cap_unconfirmed=40,
                cap_asserted=20, cap_wired=20, gate="any", date_latest=True)),
    ("V28 V24 + cap 80/40/40",
     True, Cfg("V28", persona_in_ask=True, subject_filter=True,
                value_fallback=True, value_fallback_min=2,
                value_fallback_always=True, cap_unconfirmed=80,
                cap_asserted=40, cap_wired=40, gate="any", date_latest=True)),
    ("V29 V24 + rare-token single-match (df<=3)",
     True, Cfg("V29", persona_in_ask=True, subject_filter=True,
                value_fallback=True, value_fallback_min=2,
                value_fallback_rare_df=3,
                value_fallback_always=True, cap_unconfirmed=40,
                cap_asserted=20, cap_wired=20, gate="any", date_latest=True)),
    ("V30 V29 + rare df<=2",
     True, Cfg("V30", persona_in_ask=True, subject_filter=True,
                value_fallback=True, value_fallback_min=2,
                value_fallback_rare_df=2,
                value_fallback_always=True, cap_unconfirmed=40,
                cap_asserted=20, cap_wired=20, gate="any", date_latest=True)),
    ("V31 V29 + rare df<=5",
     True, Cfg("V31", persona_in_ask=True, subject_filter=True,
                value_fallback=True, value_fallback_min=2,
                value_fallback_rare_df=5,
                value_fallback_always=True, cap_unconfirmed=40,
                cap_asserted=20, cap_wired=20, gate="any", date_latest=True)),
    ("V32 V29 + gate majority",
     True, Cfg("V32", persona_in_ask=True, subject_filter=True,
                value_fallback=True, value_fallback_min=2,
                value_fallback_rare_df=3,
                value_fallback_always=True, cap_unconfirmed=40,
                cap_asserted=20, cap_wired=20, gate="majority", date_latest=True)),
]

for _frac in (0.4, 0.3, 0.25, 0.2, 0.15):
    VARIANTS.append((
        f"V24+gate={_frac} (no rare_df)",
        True, Cfg(f"g{_frac}", persona_in_ask=True, subject_filter=True,
                   value_fallback=True, value_fallback_min=2,
                   value_fallback_always=True, cap_unconfirmed=40,
                   cap_asserted=20, cap_wired=20, gate=_frac, date_latest=True)))
for _frac in (0.4, 0.3, 0.25, 0.2, 0.15):
    VARIANTS.append((
        f"V29+gate={_frac} (rare_df=3)",
        True, Cfg(f"gr{_frac}", persona_in_ask=True, subject_filter=True,
                   value_fallback=True, value_fallback_min=2,
                   value_fallback_rare_df=3,
                   value_fallback_always=True, cap_unconfirmed=40,
                   cap_asserted=20, cap_wired=20, gate=_frac, date_latest=True)))

VARIANTS.append((
    "V33 V24 + FIX I (specificity gate)",
    True, Cfg("V33", persona_in_ask=True, subject_filter=True,
               value_fallback=True, value_fallback_min=2,
               value_fallback_always=True, cap_unconfirmed=40,
               cap_asserted=20, cap_wired=20, gate="any", date_latest=True,
               specificity_gate=True)))
VARIANTS.append((
    "V34 V29(rare_df=3) + FIX I",
    True, Cfg("V34", persona_in_ask=True, subject_filter=True,
               value_fallback=True, value_fallback_min=2,
               value_fallback_rare_df=3,
               value_fallback_always=True, cap_unconfirmed=40,
               cap_asserted=20, cap_wired=20, gate="any", date_latest=True,
               specificity_gate=True)))
VARIANTS.append((
    "V35 V26(fallback min=1) + FIX I",
    True, Cfg("V35", persona_in_ask=True, subject_filter=True,
               value_fallback=True, value_fallback_min=1,
               value_fallback_always=True, cap_unconfirmed=40,
               cap_asserted=20, cap_wired=20, gate="any", date_latest=True,
               specificity_gate=True)))
VARIANTS.append((
    "V36 V35 cap 20/10/10",
    True, Cfg("V36", persona_in_ask=True, subject_filter=True,
               value_fallback=True, value_fallback_min=1,
               value_fallback_always=True, cap_unconfirmed=20,
               cap_asserted=10, cap_wired=10, gate="any", date_latest=True,
               specificity_gate=True)))
VARIANTS.append((
    "V37 V35 gate majority",
    True, Cfg("V37", persona_in_ask=True, subject_filter=True,
               value_fallback=True, value_fallback_min=1,
               value_fallback_always=True, cap_unconfirmed=40,
               cap_asserted=20, cap_wired=20, gate="majority", date_latest=True,
               specificity_gate=True)))
VARIANTS.append((
    "V38 V35 + rare_df=3 too",
    True, Cfg("V38", persona_in_ask=True, subject_filter=True,
               value_fallback=True, value_fallback_min=1,
               value_fallback_rare_df=3,
               value_fallback_always=True, cap_unconfirmed=40,
               cap_asserted=20, cap_wired=20, gate="any", date_latest=True,
               specificity_gate=True)))
VARIANTS.append((
    "V39 V35 cap 100/40/40",
    True, Cfg("V39", persona_in_ask=True, subject_filter=True,
               value_fallback=True, value_fallback_min=1,
               value_fallback_always=True, cap_unconfirmed=100,
               cap_asserted=40, cap_wired=40, gate="any", date_latest=True,
               specificity_gate=True)))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--users", default="10-12")
    ap.add_argument("--min-mentions", dest="min_mentions", type=int, default=2)
    ap.add_argument("--cache-template", dest="cache_template", default=CACHE_TEMPLATE)
    args = ap.parse_args()

    a, b = args.users.split("-") if "-" in args.users else (args.users, args.users)
    user_indices = list(range(int(a), int(b) + 1))

    print(f"loading users {user_indices} from v5.1 14B caches ...")
    mems = load_dev_users(user_indices, args.min_mentions, args.cache_template)
    total_q = sum(len(qs) for _, qs in mems.values())
    print(f"{len(mems)} users, {total_q} questions total\n")

    hdr = (f"{'variant':42s} {'composed%':>10s} {'DELIVERED%':>11s} "
           f"{'(n)':>10s} {'COMP-ON-UNK%':>13s} {'(n)':>10s}")
    print(hdr)
    print("-" * len(hdr))
    for label, match_on, cfg in VARIANTS:
        row = score_variant(mems, match_on, cfg)
        print(f"{label:42s} {row['composed_rate']:10.1f} {row['delivered']:11.1f} "
              f"{row['n_delivered']:>4d}/{row['n_real']:<5d} "
              f"{row['composed_on_unknown']:13.1f} "
              f"{row['n_unk_composed']:>4d}/{row['n_unk']:<5d}")

    print(f"\nTARGETS: DELIVERED >= 35.0 (ceiling 55.6), "
          f"COMPOSED-ON-UNKNOWN <= 25.0")


if __name__ == "__main__":
    main()
