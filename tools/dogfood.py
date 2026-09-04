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
   "I like it a lot actually."}],
]

# ---------------------------------------------------------------- the probes
# RECALL: ordinary phrasings, and the substring that identifies a correct hit.
ANSWERABLE = {
    "Where do I work?":                 "Lumen Health",
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
    "What car do I drive?":             "car is a Volvo",
    # e263: the copular perfect keeps its aspect
    "Am I a vegetarian?":               "has been a vegetarian",
    # e259: a relative pronoun resolved to its antecedent
    "What did I learn last year?":      "Postgres",
}

# ABSTENTION: never mentioned by anyone, in any turn.
UNSEEN = [
    "Do I have any children?", "What is my blood type?",
    "Where did I go to university?", "What is my favourite film?",
    "What city was I born in?", "Do I have a dog?", "What is my salary?",
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
]


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
            if not out.get("abstain"):
                got = facts_of(out)
                leaks.append((q, got[0][:60] if got else "-"))
        abst = len(UNSEEN) - len(leaks)

        # ---- PURITY
        impure = []
        for frag, who in MUST_NOT_ASSERT:
            if frag.lower() in blob.lower():
                impure.append((frag, who))
        pure = len(MUST_NOT_ASSERT) - len(impure)

        n = len(ANSWERABLE)
        print(f"\n  RECALL      rank-1 {r1}/{n}   in-pool {pool}/{n}")
        print(f"  ABSTENTION  {abst}/{len(UNSEEN)} honest on never-mentioned topics")
        print(f"  PURITY      {pure}/{len(MUST_NOT_ASSERT)} things nobody asserted stayed out of the store")
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
        rc = 0 if not impure and not leaks else 1
        print(f"\n  {'PASS' if rc == 0 else 'FAIL'} on the two properties that must never regress "
              f"(purity, abstention)")
        return rc
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
