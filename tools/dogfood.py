#!/usr/bin/env python3
"""The product harness: ingest ordinary conversation, then measure what a
USER would notice.

WHY THIS EXISTS. e258 and e259 both came from using the product; nine entries
of benchmark decomposition surfaced neither. But the ad-hoc set that found
them had a hole (e264): it contained no assistant turns that ASK, so it could
not see the defect class that produces FALSE FACTS -- the assistant asks "are
you interested in X?" and the store asserts the user IS. The metric read flat
through two entries that fixed exactly that.

FOUR AXES, because a memory can fail in four different ways and three of them
are invisible if you only measure recall:

  RECALL      a fact the user stated is retrievable by an ordinary question
  ABSTENTION  a topic never mentioned returns an honest "never seen"
  PURITY      nothing the user never asserted is in the store at all
  TIERING     hearsay and single-mentions are LABELED, not passed off as
              corroborated

PURITY is the one the ad-hoc set was blind to and the one that matters most:
a missing fact is a bad answer, an invented one is a broken promise.

    python tools/dogfood.py                 # full scorecard
    python tools/dogfood.py --v3            # with RG_PROFILE_V3
    python tools/dogfood.py --show-store    # dump what was stored
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OWNER = "Alex Reyes"

# ---------------------------------------------------------------- the corpus
# Ordinary conversation, written to contain the traps a real assistant sets:
# it asks, it suggests, it recalls things back. None of that is the user
# speaking, and none of it may become a fact about them.
SESSIONS = [
 # --- session 1: plain statements, and an assistant that ASKS ---------------
 [{"role": "user", "content":
   "I've been at Lumen Health for about three years now, I'm a backend "
   "engineer there."},
  {"role": "assistant", "content":
   "Three years is a good tenure. What are you working on?"},
  {"role": "user", "content":
   "Mostly the billing service. It's written in Go."},
  {"role": "assistant", "content":
   "Are there specific conferences or meetups you're particularly interested "
   "in attending this year?"},
  {"role": "user", "content":
   "Not really, I don't travel much for work."},
  {"role": "assistant", "content":
   "That's fair. Would you say you prefer remote collaboration?"},
  {"role": "user", "content":
   "Yes, I work from home three days a week. My partner Sam works from home "
   "too."},
  {"role": "assistant", "content":
   "What specific aspects of remote work are most valuable to you?"},
  {"role": "user", "content":
   "The quiet, mostly. I left my last job at Perrin because the commute was "
   "brutal, almost 90 minutes each way."}],

 # --- session 2: suggestions, hypotheticals, negation, correction -----------
 [{"role": "user", "content":
   "I'm thinking about learning Rust this year. My manager Priya suggested it."},
  {"role": "assistant", "content":
   "You might also enjoy Zig, and you would probably like Haskell given your "
   "interest in type systems."},
  {"role": "user", "content":
   "If I moved to Berlin I'd need to learn German, but that's not happening "
   "any time soon."},
  {"role": "assistant", "content":
   "I remember you mentioning that you play the cello."},
  {"role": "user", "content":
   "I don't drink coffee, by the way. I switched to tea years ago."},
  {"role": "assistant", "content":
   "Noted. Is there a particular tea you're drawn to?"},
  {"role": "user", "content":
   "I got promoted to senior engineer last month. Also I'm allergic to "
   "peanuts, in case you ever suggest recipes."}],

 # --- session 3: the cases e262-e267 fixed, which the corpus could not see --
 # Every entry after e261 was measured against a corpus with no instance of
 # what it changed, so the scorecard read flat while real defects were being
 # closed. e264 named that hole once and it reopened three entries later, so
 # extending this corpus is now part of landing a write-path fix.
 [{"role": "user", "content":
   "My car is a Volvo. It is very reliable, I have never had trouble with it."},
  {"role": "assistant", "content":
   "The support you've received from your network is a powerful force."},
  {"role": "user", "content":
   "My bike is red and my scooter is blue. It is my favourite."},
  {"role": "user", "content":
   "I've been a vegetarian since 2019."},
  {"role": "user", "content":
   "I use Postgres, which I learned last year."},
  {"role": "user", "content":
   "I like it a lot actually."},
  {"role": "user", "content":
   "I have a dog and a cat at home."}],

 # --- session 4: THE USER'S WORLD, not the user's profile -------------------
 # People already KNOW the facts about themselves. What they need a memory for
 # is their WORLD -- the systems, projects and things around them, which is
 # exactly what an owner-subject-only store throws away. The guard rail is
 # that an entity must be one the USER established as theirs; generic world
 # knowledge from either speaker stays out.
 [{"role": "user", "content":
   "I work on the billing service. It is written in Go and it handles about "
   "ten thousand invoices a day."},
  {"role": "assistant", "content":
   "Cats are independent animals. There are several good databases available."},
  {"role": "user", "content":
   "We use Postgres for the main database. The main database is replicated "
   "across three regions."},
  {"role": "user", "content":
   "My team owns the checkout flow. The checkout flow is the oldest code in "
   "the company."}],

 # --- session 5: things CHANGE. The axis the harness could not see ---------
 # Updating is the system's measured worst column (12.6% vs Zep 47.3%) and
 # nothing here tested it. A memory that cannot update is not a LIVING memory,
 # which is the whole product claim. Each fact below was asserted in an
 # earlier session and is superseded here.
 [{"role": "user", "content":
   "I left Lumen Health last month. I work at Acme now."},
  {"role": "user", "content":
   "I sold the Volvo. I drive a Skoda now."},
  {"role": "user", "content":
   "I am no longer a vegetarian, I started eating fish again."}],

 # --- session 6: a CONTRADICTION with no cessation -------------------------
 # The user changes a single-valued fact without saying the old one ended.
 # Nothing can decide this from the text, so the store must SURFACE it rather
 # than silently pick -- which is what the server README promises.
 [{"role": "user", "content":
   "My main editor is Vim."},
  {"role": "user", "content":
   "My main editor is Emacs."},
  {"role": "user", "content":
   "I like Go. I like Rust. I like Python."}],
]

# ---------------------------------------------------------------- the probes
# RECALL: ordinary phrasings, and the substring that identifies a correct hit.
ANSWERABLE = {
    "Where do I work?":                 "Acme",     # superseded in session 5
    "What is my job title?":            "backend engineer",
    "Who is my manager?":               "Priya",
    "What am I allergic to?":           "allergic to peanuts",
    "Why did I leave my last job?":     "commute",
    "Who is Sam?":                      "Sam",
    "What language is the billing service in?": "Go",
    "Did I get promoted?":              "promoted to senior",
    "Do I work from home?":             "works from home",
    "What am I learning?":              "Rust",
    "Do I drink coffee?":               "coffee",
    "Do I travel for work?":            "travel",
    # e267: a pronoun resolved to a single owner-possessed antecedent
    "What is my car like?":             "car is very reliable",
    "What car do I drive?":             "Skoda",
    # e263: the copular perfect keeps its aspect
    # superseded in session 5 -- the CURRENT answer is the negative. Third
    # time a corpus extension has invalidated one of my own probes (e268,
    # e272, e273): a recall needle names a fact, and facts change.
    "Am I a vegetarian?":               "no longer a vegetarian",
    # e259: a relative pronoun resolved to its antecedent
    "What did I learn last year?":      "Postgres",
    # --- the user's WORLD (session 4). People know their own facts; what
    # they forget is the systems around them.
    "What is the billing service written in?":   "billing service is written in Go",
    "How many invoices does billing handle?":    "ten thousand invoices",
    "Is the main database replicated?":          "replicated across three regions",
    "What do I know about the checkout flow?":   "checkout flow is the oldest code",
    # e275: PARAPHRASE. Real questions rarely reuse the stored fact's words.
    # The corpus had exactly one such case, which is why lexical grounding
    # looked almost free -- a corpus weakness read as evidence.
    "Do I own any pets?":               "dog",
    "What is my role at work?":         "backend engineer",
    "Which company employs me?":        "Acme",     # superseded in session 5
    "What do I eat?":                   "fish",
    "How do I commute?":                "home",
    "What is my beverage of choice?":   "tea",
}

# ABSTENTION: never mentioned by anyone, in any turn.
UNSEEN = [
    "Do I have any children?", "What is my blood type?",
    "Where did I go to university?", "What is my favourite film?",
    "What city was I born in?", "What is my salary?",
    "Which gym do I go to?", "When is my birthday?",
]

# HEARSAY-ONLY: the ASSISTANT mentioned it and the user never confirmed it.
# Not abstention -- UNSEEN above means "never mentioned by ANYONE", and the
# assistant is somebody. e249 settled this on the other read path: the memory
# HAS seen the topic, it just holds no assertion. It must come back LABELED,
# never as the user's own fact.
#
# `check_probes()` did not catch this one, because "play" sits in its
# stopword list -- a judgement call made to stop false alarms, which also
# hides real contamination. Worth knowing about the guard.
HEARSAY_ONLY = [
    ("What instrument do I play?", "cello"),
]

# KNOWN LIMITATION, deliberately NOT counted as abstention: a question about
# an entity the store DOES know, asking for an attribute it does NOT hold.
# "What is my partner's job?" returns "partner Sam works from home too" --
# related, true, and not an answer. UNSEEN above is defined as "never
# mentioned by anyone", and the partner IS mentioned, so scoring this as an
# abstention failure measured the wrong thing.
#
# It is a real property and worth fixing (an agent should say "I know Sam
# works from home, not what their job is"), but it is ATTRIBUTE-level
# abstention, not topic-level, and folding it into the abstention count would
# make that number mean two different things.
PARTIAL_KNOWLEDGE = [
    ("What is my partner's job?", "Sam", "job"),
]

# PURITY: strings that must NOT appear anywhere in the asserted store. Each is
# something a naive extractor would happily lift from an assistant turn or a
# hypothetical. The comment says who actually said it.
MUST_NOT_ASSERT = [
    # the assistant ASKED whether he is interested -- he is not on record
    ("interested in attending", "assistant asked, user never confirmed"),
    ("particularly drawn",      "assistant asked about tea"),
    # the assistant SUGGESTED these -- the user never said either
    ("enjoy Zig",               "assistant suggested"),
    ("Zig",                     "assistant suggested"),
    ("Haskell",                 "assistant suggested"),
    # a HYPOTHETICAL the user explicitly negated
    ("moved to Berlin",         "user's counterfactual, explicitly not happening"),
    ("learn German",            "consequent of a counterfactual"),
    # a NEGATED fact must not be stored as positive
    ("drinks coffee",           "user said they do NOT"),
    # assistant RECALL about the user is hearsay, never the user's own fact
    ("plays the cello",         "assistant hearsay; user never said it"),
    ("play the cello",          "assistant hearsay; user never said it"),
    # e267: TWO owner-possessed candidates -- must decline, never guess
    ("bike is my favourite",    "ambiguous antecedent: bike or scooter"),
    ("scooter is my favourite", "ambiguous antecedent: bike or scooter"),
    ("bike is Alex",            "ambiguous antecedent, resolved anyway"),
    ("scooter is Alex",         "ambiguous antecedent, resolved anyway"),
    # e262: a complement that is only an unresolved referent
    ("likes it a lot",          "deictic-empty; no referent in scope"),
    # e264: an aux must agree after the person shift, never read "have"
    ("Reyes have received",     "aux not agreed after the person shift"),
    ("Reyes've",                "clitic survived the person shift"),
    # e263: a copular perfect must not flatten to the present
    ("Reyes is a vegetarian since", "copular perfect flattened to present"),
    # GENERIC world knowledge is not the user's world, from either speaker
    ("Cats are independent",    "generic knowledge, nobody's world"),
    ("independent animals",     "generic knowledge, nobody's world"),
    ("several good databases",  "assistant generic, user never said it"),
]


# CURRENCY: (question, the value that is now TRUE, the value that is STALE).
# The new value must be retrievable; the stale one must not be handed back as
# though it still holds. Both may legitimately be in the store -- a receipt is
# permanent -- so what is measured is what RECALL returns, not what is stored.
CURRENCY = [
    ("Where do I work?",        "Acme",   "Lumen Health"),
    ("What car do I drive?",    "Skoda",  "Volvo"),
    ("Am I a vegetarian?",      "no longer a vegetarian", "has been a vegetarian"),
]


# CONFLICT: (attribute fragment, the two values that cannot both be current).
# A single-valued slot with two live values must raise an ASK. A multi-valued
# one must not -- liking three languages is not a contradiction.
CONFLICTS_EXPECTED = [("editor", "vim", "emacs")]
CONFLICTS_FORBIDDEN = ["like", "have"]


def check_probes():
    """Guard against the failure mode that has now bitten five times: a recall
    needle names a FACT, and facts change. Every corpus extension can silently
    invalidate a needle -- the car, the vegetarian, the dog, the employer --
    and each time the harness reported a system failure that was really a
    probe failure.

    Two rules, both cheap:
      * no ANSWERABLE needle may name a value CURRENCY lists as stale;
      * no UNSEEN question may share a distinctive word with the corpus.
    Returns a list of complaints; empty means the probes are self-consistent.
    """
    import re
    bad = []
    stale = {s.lower() for _, _, s in CURRENCY}
    corpus_l = " ".join(t["content"].lower()
                        for sess in SESSIONS for t in sess)
    for q, needle in ANSWERABLE.items():
        for st in stale:
            if st in needle.lower():
                bad.append(f"ANSWERABLE {q!r} wants {needle!r}, which CURRENCY "
                           f"lists as superseded")
        # e277: THE CHECK THAT WOULD HAVE CAUGHT THE PETS PROBE. "Do I own any
        # pets?" wanted "dog"; the corpus contained no dog, no cat and no pet.
        # It was moved from UNSEEN to ANSWERABLE on my belief that the corpus
        # mentioned one -- that was a TEST FILE, not the corpus -- and it then
        # ran as a permanent false miss AND was written up in the notebook as
        # a real capability gap. A needle must have lexical support in the
        # corpus, or it is a probe for a fact that does not exist.
        nt = [t for t in re.findall(r"[a-z]+", needle.lower()) if len(t) > 2]
        # ALL tokens, not ANY: a needle is quoted from a record, so every
        # content word in it should appear in the source. `any` let one
        # incidental match excuse the whole needle -- "Kind of Blue" passed
        # because the corpus says "kind of", which is precisely how the pets
        # probe survived.
        # Review 2026-09-05: a LEFT boundary alone made this a prefix test --
        # "commut aller engin" passed on "commute"/"allergic"/"engineer".
        # Allow only a short inflectional suffix, so a stem still matches its
        # own forms and nothing else.
        missing = [t for t in nt
                   if not re.search(rf"\b{t}(?:s|es|ed|d|ing|ly|er|ers)?\b",
                                    corpus_l)]
        if nt and missing:
            bad.append(f"ANSWERABLE {q!r} wants {needle!r}: {missing} appear "
                       f"NOWHERE in the corpus -- a probe for a fact that "
                       f"does not exist")
    corpus = " ".join(t["content"].lower()
                      for sess in SESSIONS for t in sess)
    # Generic question nouns are not topics: "What is my blood TYPE" is about
    # blood, and "favourite film" is about film. Without these the check
    # flagged both because the corpus says "type systems" and "favourite
    # language" -- a self-check that cries wolf gets ignored, which is worse
    # than not having one.
    common = set("""what who where when which how do does did is are was were
                 my i me a an the of in on at for to about any have has go
                 play am be been there thing type kind sort favourite favorite
                 name number""".split())
    for q in UNSEEN:
        # e277: was `len(t) > 3`, which silently excluded every three-letter
        # topic -- gym, car, dog, job. The exact words this check exists for.
        toks = {t for t in re.findall(r"[a-z]+", q.lower())
                if t not in common and len(t) >= 3}
        hit = [t for t in toks if re.search(rf"\b{t}s?\b", corpus)]
        if hit:
            bad.append(f"UNSEEN {q!r} mentions {hit} -- the corpus talks about it")
    return bad


def build(tmp, v3):
    os.environ["RG_MEMORY_DIR"] = os.path.join(tmp, "mem")
    os.environ["SOURCEDRECALL_STATE"] = os.path.join(tmp, "state")
    os.environ["SOURCEDRECALL_BROWSER_PORT"] = "0"
    os.environ["SOURCEDRECALL_OWNER"] = OWNER
    if v3:
        os.environ["RG_PROFILE_V3"] = "1"
    else:
        os.environ.pop("RG_PROFILE_V3", None)
    os.makedirs(os.environ["RG_MEMORY_DIR"], exist_ok=True)
    os.makedirs(os.environ["SOURCEDRECALL_STATE"], exist_ok=True)
    sys.path.insert(0, os.path.join(_ROOT, "server"))
    sys.path.insert(0, _ROOT)
    from sourcedrecall import profile_memory as pmem
    for i, sess in enumerate(SESSIONS):
        pmem.profile_ingest(sess, title=f"session {i+1}", owner_name=OWNER)
    return pmem


def facts_of(out):
    if out.get("ranked"):
        return [str(f.get("text") or f.get("value")) for f in out["ranked"]]
    got = []
    for key in ("asserted", "unconfirmed", "wired"):
        for v in (out.get(key) or []):
            f = v.get("fact") if key == "wired" else v
            got.append(str(f.get("text") or f.get("value")))
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v3", action="store_true")
    ap.add_argument("--show-store", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    complaints = check_probes()
    if complaints:
        print("PROBE SELF-CHECK FAILED -- fix the harness before reading it:")
        for c in complaints:
            print(f"  {c}")
        print()

    tmp = tempfile.mkdtemp(prefix="rg-dogfood-")
    try:
        pmem = build(tmp, args.v3)
        st = pmem.profile_status()
        mem = pmem._state["mem"]
        allnodes = (list(mem.g.nodes.values())
                    + list(mem.g.provisional.values()))
        hearsay = list(getattr(mem.g, "hearsay", {}).values())
        blob = " || ".join((d.get("text") or "") for d in allnodes)

        print(f"store: asserted={st['asserted']} provisional={st['provisional']} "
              f"hearsay={len(hearsay)}   retrieval={'v3' if args.v3 else 'token-overlap'}")
        if args.show_store:
            for d in allnodes:
                print(f"   {d['tier']:12s} {d.get('text')}")
            for d in hearsay:
                print(f"   {'hearsay':12s} {d.get('text')}")

        # ---- RECALL
        r1 = pool = 0
        misses = []
        for q, needle in ANSWERABLE.items():
            got = facts_of(pmem.profile_recall(q))
            if got and needle.lower() in got[0].lower():
                r1 += 1
            if any(needle.lower() in g.lower() for g in got):
                pool += 1
            else:
                misses.append((q, needle, got[0][:60] if got else "-"))

        # ---- ABSTENTION
        leaks = []
        for q in UNSEEN:
            out = pmem.profile_recall(q)
            got = facts_of(out)
            # Review 2026-09-05: the flag alone was trusted. A response that
            # says abstain=True and still carries facts in `ranked`/`asserted`
            # scored as honest; the payload is what a caller renders, so it
            # is what this axis has to read.
            if not out.get("abstain") or got:
                leaks.append((q, got[0][:60] if got else "-"))
        abst = len(UNSEEN) - len(leaks)

        # ---- PURITY
        impure = []
        for frag, who in MUST_NOT_ASSERT:
            if frag.lower() in blob.lower():
                impure.append((frag, who))
        pure = len(MUST_NOT_ASSERT) - len(impure)

        # ---- CURRENCY
        cur_new = cur_stale = 0
        cur_rows = []
        for q, fresh, stale in CURRENCY:
            got = facts_of(pmem.profile_recall(q))
            top3 = " || ".join(got[:3]).lower()
            has_new = fresh.lower() in top3
            # A superseded fact is DEMOTED, not hidden -- a receipt is
            # permanent and "you told me X, then Y" is a better answer than
            # silence. What must never happen is the stale value coming back
            # FIRST, as though it still held.
            has_stale = bool(got) and stale.lower() in got[0].lower()
            cur_new += has_new
            cur_stale += not has_stale
            cur_rows.append((q, fresh, stale, has_new, has_stale,
                             got[0][:58] if got else "-"))

        # ---- CONFLICT
        try:
            raised = pmem.profile_conflicts().get("conflicts", [])
        except Exception:
            raised = []
        by_attr = {c["attribute"].lower():
                   {str(v["value"]).lower() for v in c["values"]}
                   for c in raised}
        conf_ok = 0
        conf_rows = []
        for frag, a, b in CONFLICTS_EXPECTED:
            hit = any(frag in at and a in " ".join(vs) and b in " ".join(vs)
                      for at, vs in by_attr.items())
            conf_ok += hit
            if not hit:
                conf_rows.append(f"missing ask for {frag!r} ({a} vs {b})")
        false_asks = [at for at in by_attr
                      if any(at.startswith(f) for f in CONFLICTS_FORBIDDEN)]
        for at in false_asks:
            conf_rows.append(f"FALSE ask on multi-valued {at!r}: {by_attr[at]}")

        n = len(ANSWERABLE)
        print(f"\n  RECALL      rank-1 {r1}/{n}   in-pool {pool}/{n}")
        print(f"  ABSTENTION  {abst}/{len(UNSEEN)} honest on never-mentioned topics")
        print(f"  PURITY      {pure}/{len(MUST_NOT_ASSERT)} things nobody asserted stayed out of the store")
        print(f"  CURRENCY    {cur_new}/{len(CURRENCY)} return the CURRENT value   "
              f"{cur_stale}/{len(CURRENCY)} keep the stale one off rank 1")
        print(f"  CONFLICT    {conf_ok}/{len(CONFLICTS_EXPECTED)} real contradictions raised an ask   "
              f"{len(false_asks)} false asks on multi-valued slots")
        for r in conf_rows:
            print(f"      {r}")
        for q, fresh, stale, hn, hs, first in cur_rows:
            if hn and not hs:
                continue
            flag = []
            if not hn:
                flag.append(f"missing {fresh!r}")
            if hs:
                flag.append(f"STALE {stale!r} returned FIRST")
            print(f"      {q:28s} {'; '.join(flag)}")
            print(f"          top: {first}")
        if args.verbose or misses:
            print("\n  recall misses:")
            for q, needle, first in misses:
                print(f"    want '{needle}'  for {q!r}\n        got: {first}")
        if leaks:
            print("\n  ABSTENTION LEAKS (answered a never-mentioned topic):")
            for q, f in leaks:
                print(f"    {q:34s} -> {f}")
        if impure:
            print("\n  PURITY FAILURES (a fact nobody asserted is in the store):")
            for frag, who in impure:
                print(f"    {frag!r:28s} <- {who}")
        # Review 2026-09-05: the gate read purity and abstention only, so a
        # system that stored NOTHING and abstained on everything exited PASS.
        # Every fact the user stated must at least be in the retrieved pool;
        # that is an invariant of the product, not a tuned threshold.
        lost = pool < n
        rc = 0 if not impure and not leaks and not lost else 1
        print(f"\n  {'PASS' if rc == 0 else 'FAIL'} on the three properties that must never regress "
              f"(purity, abstention, every stated fact in the pool)")
        return rc
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
