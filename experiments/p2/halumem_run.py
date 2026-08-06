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

# v4 (events/plans, entry 83) / v5.1 (narrative ontology, entries 94-95):
# opt in via env so older caches stay valid for comparison.
from llm_profile import SYSTEM_V5, SYSTEM_V6, SYSTEM_ASSISTANT
# V6 checked first so it can be enabled without disturbing the V5 default,
# same convention V5 used against V4 (entry 185).
_SYSTEM = (SYSTEM_V6 if os.environ.get("RG_EXTRACT_V6")
           else SYSTEM_V5 if os.environ.get("RG_EXTRACT_V5")
           else SYSTEM_V4 if os.environ.get("RG_EXTRACT_V4") else SYSTEM_V3)
_CSFX = ("_v6" if os.environ.get("RG_EXTRACT_V6")
         else "_v5" if os.environ.get("RG_EXTRACT_V5")
         else "_v4" if os.environ.get("RG_EXTRACT_V4") else "")
from consistency import get_llm
from wire import (WireGraph, _tokens, extract_dates, _STOP, _QWORDS, _MONTHS,
                  _QUERY_SYNONYMS, _DATE_PREP, _is_dateish)
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
            # RG_INGEST_ALL_TURNS (entry 189): this line capped extraction
            # recall at 35.4% while the achievable single-turn ceiling across
            # BOTH roles is 86.9% -- 51.5pt of gold sits in assistant turns we
            # never read. Restricting to user turns is defensible for a
            # personal-memory product (the assistant's words are not the user's
            # facts) and catastrophic on a benchmark whose gold is written from
            # the full transcript. Off by default: round 5 must stay
            # reproducible, and the precision cost is not yet measured.
            is_user = t.get("role") == "user"
            if not is_user and os.environ.get("RG_INGEST_ALL_TURNS") != "1":
                continue
            text = str(t.get("content", "")).strip()[:1800]
            if not text:
                continue
            n_turns += 1
            # Assistant turns get their OWN prompt (entry 191): restatements of
            # what the user established are memory; the assistant's opinions,
            # advice and inventions are not. Using the user-turn prompt here
            # would ingest the model's own output as user fact.
            sysprompt = _SYSTEM if is_user else SYSTEM_ASSISTANT
            # Assistant turns are namespaced in the cache so they cannot be
            # served an extraction made under the user prompt. User turns keep
            # the BARE text hash, so every existing cache stays valid -- the
            # alternative would invalidate ~3,700 already-paid-for extractions
            # across users 10-12 for no benefit.
            h = hashlib.sha1((text if is_user else "a:" + text).encode()
                             ).hexdigest()
            if h in cache:
                facts = cache[h]
            else:
                facts = extract_profile_facts(text, system=sysprompt)
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
                # Provenance: which role sourced this mention. Kept so an
                # assistant-only fact is auditable and can be tiered
                # differently later, rather than silently indistinguishable
                # from something the user said (entry 190).
                if not is_user:
                    slots[key][v]["asst"] = slots[key][v].get("asst", 0) + 1
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


def _ask_tokens(q, facts):
    """The question's content tokens not already consumed by any fact VALUE
    (the subject/name tokens), minus stop/question framing -- 'what is
    actually being asked'."""
    val_toks = set()
    for f in facts:
        val_toks |= _tokens(f["value"])
    return _tokens(q) - val_toks - _STOP - _QWORDS


# ---------------------------------------------------------------------------
# PLAIN-SURFACE POLICY (entry: firewalled dev-set retrieval fix, users 10-12,
# 14B v5.1 caches -- see experiments/p2/surface_lab.py for the measured A/B
# sweep this policy was chosen from). Applies ONLY to surface="plain" -- the
# labeled/product surface above is untouched except for match()'s shared
# persona-token fix in wire.py, which is a strict retrieval improvement for
# both surfaces (see wire.py's WireGraph.match docstring).
#
# The measured problem: with the shipped selection/composition (Fix 2/3,
# entry 92/94), on HaluMem dev users 10-12 the store held the gold answer
# for 55.6% of real-gold questions (oracle.py ceiling) but the plain surface
# composed on only 14% of questions, 3% of compositions contained gold, and
# 67% of compositions were on Unknown-gold questions -- the store had the
# answer; selection/composition was refusing to surface it (or surfacing
# the wrong thing when it did).
#
# Five compounding, separately-verified causes (see entry for the full
# instrumentation) beyond the persona/date match fix:
#   FIX B  per-tier date scoping (Fix 2) exempted the unconfirmed
#          (provisional, single-mention) tier, where most of an 800-fact
#          long tail actually lives -- extended to all three tiers.
#   FIX D  SUBJECT LEAKAGE: a fact about the persona's MENTOR or TEAM
#          ("sophia:occupation") matches the same attribute bridge as a
#          question about the persona's own job and, with a 3-slot cap, was
#          crowding the persona's own answer out entirely. A subject-scoped
#          fact is now only offered when the query actually names that
#          subject.
#   FIX F  VALUE-TOKEN FALLBACK: the v5.1 extractor buckets most content
#          into a handful of generic narrative attributes (preference,
#          motivation, plan, belief, value -- 250-600+ facts each per user),
#          where an attribute bridge cannot discriminate one fact. When the
#          attribute path finds nothing (or in addition to what it finds),
#          any fact whose VALUE shares a real content word with the query is
#          offered too -- still a stored, receipted value; the same
#          literal-overlap principle as the primary match, just not
#          requiring the attribute to also line up.
#   FIX H  "AS OF <date>" LATEST-VALID-FACT resolution: attributes like
#          occupation change repeatedly across the persona's timeline; a
#          "current job title as of <date>" question named a date nothing
#          was literally said on, so exact date-token scoping always came
#          up empty. This compares parsed (year, month, day) receipt dates
#          and keeps the fact(s) whose most recent receipt is <= the asked
#          date, per attribute -- real date arithmetic, but over the SAME
#          stored receipt strings, never inventing a date or a value.
#   FIX I  SPECIFICITY GATE: a topically-related fact ("dedication to film
#          preservation is validated by a recent salary increase") was
#          being read as answering "what was the exact salary" -- a cheap
#          lexical check that a question asking for a recognizable value
#          TYPE (a number: salary/ranking/count; a name: "who"/"friend's
#          name") has a fact of that type among the candidates before
#          composing, else abstains. The plain-surface analogue of the
#          labeled surface's VALUE-TYPE DISCLAIMER (Fix 3) -- an abstain
#          instead of a hedge, since the plain voice has no room to hedge.
#
# Selection is loosened to match: bigger per-tier caps (20/20/40 vs.
# 6/4/3) since the value fallback and subject filter widen and clean the
# candidate pool, and the compose gate is "any real content word covered"
# (not majority) since FIX D/F/H/I now do the precision work that the
# majority-coverage gate alone used to.
#
# FIX J (entry: compose-vs-abstain gate tightening -- gate_lab.py sweep,
# dev users 10-12): the above selection made the plain surface loose enough
# to FIND a stored fact for most questions -- but on questions where the
# store has no fact that DIRECTLY answers (a confirm/deny "Did she..."
# question, or a speculative "what might she try next" ask), the widened
# candidate pool composes a long join of weakly-related narrative facts
# instead of admitting it doesn't know. The official judge cannot parse
# these ("None" verdict, ~29% of dev/test) -- worse than an honest
# "Unknown.", which the judge grades correctly whenever gold agrees.
# Two measured, narrowly-targeted additions, verified against this dev
# set's own question_type labels (not guessed -- see gate_lab.py module
# docstring for the full per-type hit-rate table):
#   CONFLICT-LEAD ABSTAIN: a question starting with "did/is/was/does" is a
#   yes/no CONFIRM-OR-DENY ask ("Did Michelle decide to keep eating
#   sushi?") -- 92% of this dev set's "Memory Conflict" question type, 0-2%
#   false-positive elsewhere. A join of stored VALUES can never express
#   "no, actually..."; composing one is a category error regardless of
#   whether the store holds the right underlying fact, so this abstains
#   unconditionally, before any recall/selection work runs.
#   TIGHTER COMPOSE BUDGET: measured on this dev set, DELIVERED (gold-token
#   containment) and answer length are strongly correlated -- a long blob
#   cheaply contains gold tokens by volume even when unparseable by a real
#   judge. RG_COMPOSE_BUDGET's default drops from 600 to 360 (still
#   env-overridable): the sweep found >350-char answers jump from ~9% to
#   ~55% of composed answers crossing the 360->400 boundary, while
#   DELIVERED only drops a few points in that same range -- 360 is the
#   knee of that curve on this dev set.
# NOT adopted (measured, rejected): a blanket abstain on ALL
# modal/speculative phrasing ("might"/"could"/"would" -- "Generalization &
# Application", 97% hit rate) cut DELIVERED roughly in half for little
# further LEN-RISK gain once the budget above is in place, because many of
# those speculative-phrased questions DO have a directly answering stored
# fact (HaluMem often generates the speculative gold from a real narrative
# turn) -- killing the whole class throws away real answers along with the
# blobs. CONFLICT-LEAD alone isolates the one question shape (yes/no
# confirm/deny) that is STRUCTURALLY unanswerable by any value-join.
# ---------------------------------------------------------------------------

_NUMERIC_TRIGGERS = {"salary", "amount", "number", "ranking", "score", "rank",
                      "many", "much", "cost", "price", "toppings", "count"}
_NAME_TRIGGERS = {"name"}

# FIX J: yes/no confirm-or-deny question lead -- see comment block above.
_CONFLICT_LEAD_RX = re.compile(r"^\s*(did|is|was|does)\b", re.I)

_MONTH_NUM = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"])}
_RECEIPT_RX = re.compile(
    r"\b(" + "|".join(_MONTH_NUM) + r")[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})\b", re.I)
_TEXT_DATE_RX = re.compile(
    r"\b(" + "|".join(_MONTH_NUM) + r")[a-z]*\.?\s*(\d{1,2})?,?\s*(\d{4})?\b", re.I)
_TEXT_YEAR_RX = re.compile(r"\b(19\d{2}|20\d{2})\b")


def _subject_of(attr):
    """attr strings are 'subj:attr' for facts about someone other than the
    persona (see ingest_user's slot key), plain 'attr' for the persona's own
    facts. Returns the subject's token set, or None for a self-fact."""
    if ":" not in attr:
        return None
    return _tokens(attr.split(":", 1)[0])


def _subject_ok(f, q_toks):
    """FIX D: a subject-scoped fact ('sophia:occupation') answers a question
    about someone ELSE, not the persona -- only offered as a candidate when
    the query actually names that subject. Self facts always pass."""
    subj = _subject_of(f["attribute"])
    return subj is None or (subj & q_toks)


def _value_fallback_facts(mem, q_toks, min_shared=1):
    """FIX F: literal grounding for the mega-buckets (preference/motivation/
    plan/belief/value/...) where attribute-bridging cannot discriminate one
    fact among hundreds. If the query's own content words (already stripped
    of persona/QWORDS/date-noise by the caller) share >= min_shared literal
    tokens with a stored fact's VALUE, the fact is offered as a candidate --
    still non-generative (a stored, receipted value; the SAME literal-
    overlap principle as the primary match, just without requiring the
    attribute to also line up)."""
    out = []
    for nd in list(mem.g.nodes.values()) + list(mem.g.provisional.values()):
        if len(q_toks & _tokens(nd["value"])) >= min_shared:
            out.append(mem._fact(nd, provisional=(nd["tier"] == "provisional")))
    return out


def _specificity_ok(q_toks, facts):
    """FIX I: a question asking for a recognizable value TYPE (a number, a
    name) must have a candidate fact of that type, or it abstains -- the
    plain-surface analogue of the labeled surface's VALUE-TYPE DISCLAIMER."""
    if q_toks & _NUMERIC_TRIGGERS and not any(re.search(r"\d", f["value"])
                                              for f in facts):
        return False
    if q_toks & _NAME_TRIGGERS and not any("name" in f["attribute"]
                                           for f in facts):
        return False
    return True


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
    return (int(m.group(1)), None, None) if m else None


def _fact_latest_receipt(f):
    dates = [d for rc in (f.get("receipts") or [])
             if (d := _parse_receipt_date(rc["date"]))]
    return max(dates) if dates else None


def _asof_select(facts, q_date):
    """FIX H: among `facts`, the subset whose most recent receipt is <= the
    asked date, restricted to those with the LATEST such receipt (ties
    kept). Returns [] if no fact has any receipt at or before the asked
    date -- this never guesses forward in time; it only picks among facts
    that were already true as of some point at or before what was asked."""
    y, m, d = q_date
    qd = (y if y is not None else 9999, m if m is not None else 12,
          d if d is not None else 31)
    dated = [(d2, f) for f in facts if (d2 := _fact_latest_receipt(f)) and d2 <= qd]
    if not dated:
        return []
    best = max(d2 for d2, _ in dated)
    return [f for d2, f in dated if d2 == best]


# ---------------------------------------------------------------------------
# FIX K: ENTITY+ATTRIBUTE ANCHORING (_answer_anchored, gated behind
# RG_ANCHORED -- an A/B against the shipped _answer_plain, entry: the 31%
# hallucination diagnosis).
#
# THE DIAGNOSIS (measured against the REAL official judge, not this file's
# in-house proxy): every flagged plain-surface "hallucination" traced back
# to a REAL stored fact that was WRONG FOR THE QUESTION, not a fabrication.
# _answer_plain's selection (FIX B/D/F/H/I above) ranks candidates by VALUE
# TOKEN overlap across the WHOLE store -- a question asking for the
# person's job title can be answered by any fact whose VALUE happens to
# share a word with the question, regardless of whether that fact's
# ATTRIBUTE is occupation at all. This is the known graph/KG-QA fix
# (HippoRAG-style entity+attribute anchoring): map the question to the
# SPECIFIC attribute type it asks about FIRST, restrict candidates to that
# attribute type, and only then rank by value-token overlap to disambiguate
# within it. A question with no recognizable attribute-type mapping
# abstains outright instead of falling back to the whole-store value
# search.
#
# ATTR FOLD (measured off dev users 10-12's own store, RG_EXTRACT_V5's
# narrative ontology): the v5.1 extractor mints many near-duplicate
# ATTRIBUTE STRINGS for the same concept -- 182 distinct attribute strings
# across 3 users, e.g. "monthly_income"/"financial_status"/"savings" all
# meaning income, "health_status"/"physical_condition"/"chronic_diseases"
# all meaning health_condition. Anchoring against the RAW attribute string
# would silently miss most of the store; this folds the OBSERVED variants
# of each canonical attribute named in the mission brief into one bucket,
# for ANCHORING/ranking purposes only -- it does not touch ingest_user's
# own slot keys, clustering, or the labeled surface.
# ---------------------------------------------------------------------------

_ATTR_FOLD = {
    "occupation": {"occupation", "current_occupation", "previous_occupation",
                   "occupation_background", "employment", "career_focus",
                   "former_employer", "work_arrangement", "work_schedule",
                   "work_environment", "role_evolution", "career_transition"},
    "location": {"location"},
    "birth_date": {"birth_date"},
    "pet": {"pet", "pets"},
    "education": {"education", "education_level", "major"},
    "income": {"income", "monthly_income", "savings", "financial_status"},
    "relationship": {"relationship", "support_network", "support",
                      "collaboration", "network", "team", "mentorship",
                      "guidance", "parental_relationship", "parents"},
    "tool": {"tool"},
    "event": {"event"},
    "plan": {"plan", "current_plan"},
    "motivation": {"motivation", "source_of_inspiration"},
    "belief": {"belief", "values"},
    "value": {"value"},
    "preference": {"preference", "dislike", "style_preference",
                   "approach_to_style"},
    "feeling": {"feeling", "attitude", "reaction", "gratitude"},
    "reflection": {"reflection", "understanding", "insight"},
    "health_condition": {"health_condition", "health_status",
                          "physical_condition", "chronic_diseases",
                          "health_issue", "health_concern", "health_challenge",
                          "health_management", "physical_health", "health",
                          "physical_health_reason", "health_need"},
    "mental_health": {"mental_health", "mental_health_status",
                       "mental_health_issues", "mental_health_reason",
                       "stress_level", "stress", "stress_management",
                       "mental_challenges"},
    "gender": {"gender"},
    "goal": {"goal", "personal_goal", "career_goal", "life_goal", "mission",
             "purpose", "ambition"},
    "discipline": {"discipline"},
    "hobby": {"hobby", "leisure_activity", "past_hobby"},
    "possession": {"possession", "past_possession"},
    "project": {"project", "project_type"},
    "name": {"name"},
    "age": {"age"},
}
_ATTR_FOLD_REV = {v: k for k, vs in _ATTR_FOLD.items() for v in vs}

# mega-buckets: hundreds of facts share these attributes (the v5.1
# extractor's narrative dump), so attribute anchoring alone cannot pick
# ONE -- value-token ranking (below, same principle as FIX F) still does
# the within-bucket disambiguation.
_MEGA_ATTRS = {"motivation", "belief", "value", "preference", "plan",
               "reflection", "feeling"}


def _anchor_canon(attr):
    """attr may be 'subj:base' (see _subject_of) or a bare base attribute --
    fold the BASE to its canonical anchoring bucket; unrecognized strings
    pass through unchanged (never invented, just not folded)."""
    base = attr.split(":")[-1]
    return _ATTR_FOLD_REV.get(base, base)


# QUESTION -> ASKED ATTRIBUTE(S) router. A static, hand-authored lexical
# table (same non-generative shape as wire.py's _QUERY_SYNONYMS) built by
# inspecting the actual dev question phrasings (HaluMem-Medium.jsonl users
# 10-12) and the store's actual attribute distribution above -- covering
# the real phrasings this benchmark uses, not overfit to any one gold
# answer. A token may map to several canonical attributes (e.g. "work" and
# a category word can both legitimately point at more than one bucket);
# the union is the CANDIDATE POOL, narrowed further by value-token ranking.
_ASK_ATTR_WORDS = {
    # occupation
    "job": {"occupation"}, "role": {"occupation"}, "title": {"occupation"},
    "profession": {"occupation"}, "work": {"occupation"},
    "career": {"occupation"}, "employed": {"occupation"},
    "employment": {"occupation"}, "employer": {"occupation"},
    # birth
    "born": {"birth_date"}, "birth": {"birth_date"},
    "birthday": {"birth_date"},
    # pet
    "pet": {"pet"}, "pets": {"pet"}, "animal": {"pet"},
    # location
    "live": {"location"}, "lives": {"location"}, "city": {"location"},
    "based": {"location"}, "reside": {"location"}, "resides": {"location"},
    # education
    "study": {"education"}, "studied": {"education"},
    "degree": {"education"}, "major": {"education"},
    "university": {"education"}, "college": {"education"},
    # income
    "earn": {"income"}, "salary": {"income"}, "income": {"income"},
    "paid": {"income"}, "wage": {"income"}, "savings": {"income"},
    # relationship
    "married": {"relationship"}, "spouse": {"relationship"},
    "wife": {"relationship"}, "husband": {"relationship"},
    "partner": {"relationship"}, "kids": {"relationship"},
    "children": {"relationship"}, "friend": {"relationship"},
    "collaborating": {"relationship"}, "collaborator": {"relationship"},
    "mentor": {"relationship"},
    # tool
    "use": {"tool"}, "uses": {"tool"}, "software": {"tool"},
    "app": {"tool"}, "tool": {"tool"}, "tools": {"tool"},
    # hobby
    "hobby": {"hobby"}, "hobbies": {"hobby"}, "leisure": {"hobby"},
    # health
    "disease": {"health_condition"}, "diseases": {"health_condition"},
    "diagnosed": {"health_condition"}, "condition": {"health_condition"},
    "illness": {"health_condition"}, "medical": {"health_condition"},
    "chronic": {"health_condition"}, "health": {"health_condition"},
    "mental": {"mental_health"}, "stress": {"mental_health"},
    "stressed": {"mental_health"},
    # gender
    "gender": {"gender"},
    # goal
    "goal": {"goal"}, "aim": {"goal"}, "objective": {"goal"},
    "ambition": {"goal"},
    # discipline
    "field": {"discipline"}, "discipline": {"discipline"},
    # narrative
    "motivate": {"motivation"}, "motivation": {"motivation"},
    "believe": {"belief"}, "belief": {"belief"}, "opinion": {"belief"},
    "think": {"belief"},
    "value": {"value"}, "values": {"value"}, "prioritize": {"value"},
    "important": {"value"},
    "feel": {"feeling"}, "feeling": {"feeling"}, "feelings": {"feeling"},
    "sentiment": {"feeling"}, "emotion": {"feeling"}, "nostalgia": {"feeling"},
    "enthusiasm": {"feeling"}, "excited": {"feeling"},
    "realize": {"reflection"}, "reflect": {"reflection"},
    "reflection": {"reflection"}, "insight": {"reflection"},
    "learned": {"reflection"},
    "prefer": {"preference"}, "prefers": {"preference"},
    "preference": {"preference"}, "favorite": {"preference"},
    "favourite": {"preference"}, "like": {"preference"},
    "likes": {"preference"}, "enjoy": {"preference"}, "enjoys": {"preference"},
    "dislike": {"preference"}, "dislikes": {"preference"},
    "plan": {"plan"}, "plans": {"plan"}, "planning": {"plan"},
    "intend": {"plan"}, "upcoming": {"plan"},
    "event": {"event"}, "attended": {"event"}, "attend": {"event"},
    "happened": {"event"}, "visited": {"event"}, "watch": {"event"},
    "watched": {"event"}, "award": {"event"}, "received": {"event"},
    "project": {"project"}, "possession": {"possession"},
    "own": {"possession"}, "owns": {"possession"}, "bought": {"possession"},
}

# "type of <category>" / "<category> preference" phrasing -- the dev set's
# dominant Basic Fact Recall shape ("What type of games...", "What
# beverage...", "What genre of music..."). The v5.1 extractor files nearly
# all of these under attribute "preference" (see distribution above); a
# category word alone adds "preference" as a candidate bucket, narrowed by
# value-token ranking below (the category word itself is strong ranking
# signal: "beverage" tends to co-occur with the coffee/tea fact's value).
_CATEGORY_WORDS = {"beverage", "drink", "coffee", "tea", "wine", "cuisine",
                    "food", "game", "games", "movie", "movies", "film",
                    "films", "cinema", "music", "song", "songs", "genre",
                    "genres", "book", "books", "literature", "clothing",
                    "wardrobe", "dress", "sport", "sports", "color", "colour"}


def _asked_attrs(q):
    """QUESTION -> ASKED ATTRIBUTE(S): the canonical attribute bucket(s) the
    question's own words name, or an empty frozenset when the question
    names none -- inference/application phrasing ("how might", "why do you
    think") and conflict "did/is/was/does" asks never name a stored
    attribute type; per FIX K's abstain rule this is UNKNOWN, not a
    whole-store fallback search."""
    attrs = set()
    for t in _tokens(q):
        attrs.update(_ASK_ATTR_WORDS.get(t, ()))
        if t in _CATEGORY_WORDS:
            attrs.add("preference")
    return frozenset(attrs)


def _answer_anchored(mem, q):
    """ENTITY+ATTRIBUTE ANCHORING plain-surface policy (FIX K, RG_ANCHORED).
    Non-generative: returns a single stored, receipted value, or "Unknown."
    Steps (see module comment block above for the diagnosis):
      1. asked = _asked_attrs(q) -- the attribute-type(s) the question names.
         Empty -> abstain (no known attribute asked).
      2. candidates = stored facts (asserted + provisional) whose folded
         attribute is in `asked`, subject-scoped to the question (reuses
         FIX D's _subject_ok so a third-party fact only answers a question
         that actually names that person).
      3. as-of-date resolution (FIX H, reused) narrows each attribute group
         to its latest-valid fact when the question names a date.
      4. rank by ask-token coverage (value+attribute tokens), then asserted
         tier over provisional, then mention count; return the single best
         value. No candidates after step 2 -> abstain."""
    if _CONFLICT_LEAD_RX.match(q):
        return "Unknown."
    asked = _asked_attrs(q)
    if not asked:
        return "Unknown."

    q_toks_raw = _tokens(q)
    cands = []   # [(fact_dict, tier_rank, n_mentions)]
    for nd in mem.g.nodes.values():
        if _anchor_canon(nd["attr"]) in asked:
            f = mem._fact(nd)
            if _subject_ok(f, q_toks_raw):
                cands.append((f, 0, nd["n_mentions"]))
    for nd in mem.g.provisional.values():
        if _anchor_canon(nd["attr"]) in asked:
            f = mem._fact(nd, provisional=True)
            if _subject_ok(f, q_toks_raw):
                cands.append((f, 1, nd["n_mentions"]))

    if not cands:
        return "Unknown."

    # FIX H reuse: as-of latest-valid-fact resolution, grouped by the
    # CANONICAL (folded) attribute so a multi-attribute question keeps one
    # latest-valid answer per asked attribute type. Same all-or-nothing
    # replacement rule as _answer_plain: only if at least one group
    # produced a dated pick do the (possibly attribute-dropping) picks
    # replace the candidate set; otherwise every original candidate stays
    # (a question naming a date that matches nothing never invents one).
    q_date = _parse_query_date(q)
    if q_date is not None:
        groups = defaultdict(list)
        for item in cands:
            groups[_anchor_canon(item[0]["attribute"])].append(item)
        kept, any_dated = [], False
        for _attr, items in groups.items():
            picked = _asof_select([f for f, _, _ in items], q_date)
            if picked:
                any_dated = True
                picked_ids = {id(p) for p in picked}
                kept.extend(it for it in items if id(it[0]) in picked_ids)
        if any_dated:
            cands = kept

    persona = mem.g._persona_tokens()
    ask = q_toks_raw - persona - _STOP - _QWORDS - _DATE_PREP
    ask = {t for t in ask if not _is_dateish(t)}

    def _key(item):
        f, tier_rank, n = item
        overlap = len((_tokens(f["attribute"]) | _tokens(f["value"])) & ask)
        return (-overlap, tier_rank, -n)

    cands.sort(key=_key)
    return cands[0][0]["value"]


def _answer_plain(mem, q, r):
    """The plain-surface selection/composition policy (FIX B/D/F/H/I above).
    `r` is the already-`found` recall() result. Composes ONLY stored fact
    values (joined verbatim), never new words -- the same non-generative
    contract as the labeled path, just a looser, better-targeted selection
    of which stored facts get to speak.

    FIX J (see module comment block above): a yes/no confirm-or-deny
    question abstains unconditionally, before any recall/selection runs --
    no join of stored values can ever express the "no, actually..." such a
    question needs."""
    if _CONFLICT_LEAD_RX.match(q):
        return "Unknown."
    persona = mem.g._persona_tokens()
    q_toks_raw = _tokens(q)
    qc = q_toks_raw - persona - _QWORDS - _DATE_PREP
    qc = {t for t in qc if not _is_dateish(t)}

    extra = _value_fallback_facts(mem, qc, min_shared=1)
    have = {f["attribute"] + "=" + f["value"] for f in r["unconfirmed"]}
    r = dict(r)
    r["unconfirmed"] = r["unconfirmed"] + [
        f for f in extra if f["attribute"] + "=" + f["value"] not in have]

    r["asserted"] = [f for f in r["asserted"] if _subject_ok(f, q_toks_raw)]
    r["wired"] = [w for w in r["wired"] if _subject_ok(w["fact"], q_toks_raw)]
    r["unconfirmed"] = [f for f in r["unconfirmed"] if _subject_ok(f, q_toks_raw)]

    all_facts = (r["asserted"] + [w["fact"] for w in r["wired"]] + r["unconfirmed"])
    ask = _ask_tokens(q, all_facts) - persona

    def _rank(fs):
        return sorted(fs, key=lambda f: -len(
            (_tokens(f["attribute"]) | _tokens(f["value"])) & ask))

    # FIX H: as-of latest-valid-fact resolution runs PRE-cap/PRE-rank (a
    # narrow cap could otherwise drop the one temporally-correct fact before
    # this stage ever sees it), grouped by base attribute so a
    # multi-attribute question keeps one latest-valid answer per attribute.
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
            r["asserted"], r["unconfirmed"] = keep_a, keep_u
            r["wired"] = [w for w in r["wired"] if w["fact"] in keep_w]

    asserted = _rank(r["asserted"])[:20]
    wired = _rank([w["fact"] for w in r["wired"]])[:20]
    unconfirmed = _rank(r["unconfirmed"])[:40]

    facts = asserted + wired + unconfirmed
    if not facts:
        return "Unknown."

    if not _specificity_ok(q_toks_raw, facts):
        return "Unknown."

    attr_val_toks, attr_toks = set(), set()
    for f in facts:
        attr_val_toks |= _tokens(f["attribute"]) | _tokens(f["value"])
        attr_toks |= _tokens(f["attribute"])
    uncovered = q_toks_raw - attr_val_toks - _STOP - _QWORDS - persona
    uncovered = {t for t in uncovered if _QUERY_SYNONYMS.get(t) not in attr_toks}
    ask_all = {t for t in (q_toks_raw - _STOP - _QWORDS - persona)
               if not t.isdigit() and t not in _MONTHS and t not in _DATE_PREP}
    unc = uncovered & ask_all
    if ask_all and unc >= ask_all:   # abstain only if NOTHING asked is covered
        return "Unknown."
    # LENGTH-BUDGETED compose (sentinel catch, 2026-07-27; budget tightened
    # 600->360 by FIX J above, entry: compose-vs-abstain gate tightening):
    # unbounded joins (median 742 chars, max ~2KB) made 26.8% of round-3
    # user-1 answers unjudgeable by the official LLM judge (None verdicts);
    # even the 600-char budget still left ~29% None on dev/test -- gate_lab's
    # sweep found the >350-char fraction of composed answers climbs sharply
    # past a ~360-char budget on this dev set. Highest-ranked values first,
    # stop before the budget; always include at least one.
    # RG_SINGLE_FACT (entry 98 test): the official neutral judge marks a
    # multi-fact JOIN as Hallucination whenever any joined value is
    # inconsistent with the specific gold. Test config: return ONLY the
    # single highest-ranked fact (facts are pre-ranked by ask-coverage), so
    # the answer asserts one thing or nothing -- minimizing contradiction
    # surface. Measured against the real judge before shipping.
    if os.environ.get("RG_SINGLE_FACT"):
        return facts[0]["value"] if facts else "Unknown."
    out, total = [], 0
    for f in facts:
        v = f["value"]
        if out and total + len(v) + 2 > int(os.environ.get("RG_COMPOSE_BUDGET", "360")):
            break
        out.append(v)
        total += len(v) + 2
    return "; ".join(out)


def answer_question(mem, q, surface="labeled"):
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
    lead-in that a grader could misread as answering the question.

    SELECTION (entry 92): candidates whose attribute tokens overlap the ask
    tokens are ranked FIRST before per-tier caps -- the official run caught a
    real miss where the answering fact (birth_date) was capped out in favour
    of higher-scoring name facts.

    surface="labeled" (default, the product/MCP voice): facts carry their
    attribute and tier labels, epistemic prefixes spelled out. Selection
    stays exactly the policy described above (Fix 2/3, entry 92).
    surface="plain" (benchmark voice, entry 92; policy widened at entry:
    firewalled dev-set retrieval fix): the SAME kind of selected stored
    values, spoken as a natural answer -- values joined, and a bare
    "Unknown." whenever no stored fact covers the ask. Official-judge
    rubrics assume a composed answer; presenting abstain-with-context in the
    labeled voice was scored as hallucination despite containing only true
    stored facts. Dispatches to _answer_plain (above answer_question), which
    runs a DELIBERATELY LOOSER selection than the labeled path -- see that
    function's module-level comment block for FIX B/D/F/H/I and why the
    labeled/product surface keeps the tighter original policy unchanged.
    Surface adaptation, never content generation either way: nothing
    appears in either voice that is not a stored, receipted value."""
    if surface == "plain":
        # FIX K (RG_ANCHORED, entry: entity+attribute anchoring): an
        # entirely separate retrieval path -- attribute-indexed lookup over
        # the store directly, not match()/spread() -- so it does not need
        # `r` at all. Env-gated A/B against the shipped _answer_plain; see
        # that function's module comment block above for the diagnosis.
        if os.environ.get("RG_ANCHORED"):
            return _answer_anchored(mem, q)
        r = mem.recall(q)
        # unlike the labeled path, a raw match() miss is not final here --
        # FIX F's value-token fallback (see _answer_plain) still gets a
        # chance to find a fact through literal value overlap alone, so an
        # empty `r` is passed through rather than treated as a hard abstain.
        return _answer_plain(mem, q, r if r["found"] else
                             {"found": True, "asserted": [], "wired": [],
                              "unconfirmed": []})

    r = mem.recall(q)

    if not r["found"]:
        return "ABSTAIN -- no stored fact matches (Unknown)."

    all_facts = (r["asserted"] + [w["fact"] for w in r["wired"]]
                 + r["unconfirmed"])
    ask = _ask_tokens(q, all_facts)

    def _rank(fs):
        # ask-covering facts first, then by original (match-score) order
        return sorted(fs, key=lambda f: -len(
            (_tokens(f["attribute"]) | _tokens(f["value"])) & ask))

    asserted = _rank(r["asserted"])[:6]
    wired = _rank([w["fact"] for w in r["wired"]])[:4]
    unconfirmed = _rank(r["unconfirmed"])[:3]

    q_dates = extract_dates(q)
    date_scoped_empty = False
    if q_dates:
        a_hit = [f for f in asserted if _fact_dates(f) & q_dates]
        w_hit = [f for f in wired if _fact_dates(f) & q_dates]
        if a_hit or w_hit:
            asserted, wired = a_hit, w_hit
        else:
            date_scoped_empty = True   # keep all facts, flag the mismatch

    facts = asserted + wired + unconfirmed
    if not facts:
        return "ABSTAIN -- no stored fact matches (Unknown)."

    # the disclaimer fires when ANY asked content token stays UNCOVERED by
    # the returned facts -- "middle name" vs a fact whose attribute is just
    # "name": attribute overlap alone must not read as answered when the
    # question's qualifier ("middle") appears nowhere in the facts. A
    # synonym-trigger token ("work") counts as covered iff its mapped
    # attribute actually appears among the returned facts.
    attr_val_toks = set()
    attr_toks = set()
    for f in facts:
        attr_val_toks |= _tokens(f["attribute"]) | _tokens(f["value"])
        attr_toks |= _tokens(f["attribute"])
    uncovered = _tokens(q) - attr_val_toks - _STOP - _QWORDS
    uncovered = {t for t in uncovered if _QUERY_SYNONYMS.get(t) not in attr_toks}

    parts = [f"{f['attribute']}: {f['value']}" for f in asserted]
    parts += [f"(linked) {f['attribute']}: {f['value']}" for f in wired]
    parts += [f"UNCONFIRMED (seen once): {f['attribute']}: {f['value']}"
              for f in unconfirmed]
    answer = "; ".join(parts)
    if date_scoped_empty:
        return ("No stored fact from the asked date; related facts from "
                 "other dates: " + answer)
    if uncovered:
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
