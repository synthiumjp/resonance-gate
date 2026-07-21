"""Extractor v1 vs v2 probe on SYNTHETIC cases (entry 74).

Targets the entry-68/69 residue with named negative classes -- THIRD-PARTY
attribution, ROLEPLAY/persona, TECH-IDENTIFIER -- plus positive controls
(including multi-role, entry 69) that v2 must NOT lose. All cases are
invented; nothing personal. Runs the local model twice per case.

A negative passes if extraction yields NO bare user-attribute fact from the
other person's/persona's content (relationship-prefixed attributes like
wife_occupation are correct behaviour, not failures). A positive passes if
the expected attribute(s) appear. Usage: probe_extractor.py
"""

import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from llm_profile import SYSTEM, SYSTEM_V2, extract_profile_facts, canon_attr

# (text, kind, spec)
#   kind "neg":  spec = attrs that must NOT appear as bare user facts
#   kind "pos":  spec = [(canon_attr, value_token_regex), ...] all must appear
CASES = [
    # --- THIRD-PARTY: someone else's fact must not become the user's
    ("my wife works as a nurse at the children's hospital", "neg",
     {"occupation"}),
    ("my brother just got promoted to store manager at the supermarket", "neg",
     {"occupation"}),
    ("my friend finally got his m3 ultra, it's much faster than my setup", "neg",
     {"possession", "device"}),
    ("my daughter started studying medicine at the university this year", "neg",
     {"education"}),
    ("my old boss maria now runs a bakery in the city", "neg",
     {"occupation", "location"}),
    # --- ROLEPLAY / PERSONA / COUNTERFACTUAL
    ("pretend i'm a medieval blacksmith and describe my morning", "neg",
     {"occupation"}),
    ("if i were a lawyer i'd have sued them already", "neg", {"occupation"}),
    ("let's do a mock interview: i'll play a junior data analyst at a bank",
     "neg", {"occupation"}),
    ("imagine i live on a space station, what would my day look like", "neg",
     {"location"}),
    # --- TECH IDENTIFIERS
    ("ssh kevin@stormnode02 keeps timing out on the second hop", "neg",
     {"username", "device", "location"}),
    ("i pushed it to git@bitbucket:acmeteam/pipeline.git last night", "neg",
     {"username", "occupation"}),
    # --- regression guards from v1 (metaphor/progress-talk)
    ("let's keep digging into these logs until we find it", "neg",
     {"location"}),
    # --- POSITIVES: v2 must not lose these
    ("i work as a clinical psychologist and also do independent research",
     "pos", [("occupation", r"psycholog|research")]),
    ("i live in melbourne, out in the eastern suburbs", "pos",
     [("location", r"melbourne|suburb")]),
    ("i've been using claude code every day for my projects", "pos",
     [("tool", r"claude")]),
    ("i earn about 120k a year in my main role", "pos",
     [("income", r"120")]),
    ("i'm an emergency services executive during the week and i write fiction "
     "on weekends", "pos", [("occupation", r"executive|emergency|writer|fiction")]),
    ("my wife and i live together in the eastern suburbs", "pos",
     [("location", r"suburb")]),
    ("i own a gaming pc with an amd gpu in it", "pos",
     [("possession", r"pc|computer")]),
]

_REL = re.compile(r"^(wife|husband|partner|spouse|daughter|son|child|brother|"
                  r"sister|mother|father|parent|friend|boss|colleague|"
                  r"coworker|ex_boss|old_boss)_", re.I)


def judge(kind, spec, facts):
    canon = [(canon_attr(f["attribute"]), str(f["value"]).lower(),
              str(f["attribute"]).lower()) for f in facts]
    if kind == "neg":
        # fail only if a FORBIDDEN attribute appears WITHOUT a relationship prefix
        bad = [(a, v) for a, v, raw in canon if a in spec and not _REL.match(raw)]
        return not bad, bad
    missing = [(want, rx) for want, rx in spec
               if not any(a == want and re.search(rx, v) for a, v, _ in canon)]
    return not missing, missing


def main():
    tally = {("v1", "neg"): 0, ("v1", "pos"): 0,
             ("v2", "neg"): 0, ("v2", "pos"): 0}
    for text, kind, spec in CASES:
        res = {}
        for name, system in (("v1", SYSTEM), ("v2", SYSTEM_V2)):
            facts = extract_profile_facts(text, system=system)
            ok, detail = judge(kind, spec, facts)
            tally[(name, kind)] += ok
            res[name] = (ok, detail, facts)
        v1ok, v2ok = res["v1"][0], res["v2"][0]
        mark = "==" if v1ok == v2ok else ("v2+" if v2ok else "v2-")
        print(f"[{'ok' if v1ok else 'XX'}->{'ok' if v2ok else 'XX'} {mark:3s}] "
              f"({kind}) {text[:58]}")
        if not v2ok:
            print(f"         v2 detail: {res['v2'][1]} facts={res['v2'][2]}")
    n_neg = sum(1 for _, k, _ in CASES if k == "neg")
    n_pos = len(CASES) - n_neg
    for name in ("v1", "v2"):
        print(f"{name}: {tally[(name, 'neg')] + tally[(name, 'pos')]}"
              f"/{len(CASES)}  (neg {tally[(name, 'neg')]}/{n_neg}, "
              f"pos {tally[(name, 'pos')]}/{n_pos})")


if __name__ == "__main__":
    main()
