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
from llm_profile import (SYSTEM, SYSTEM_V2, SYSTEM_V3, extract_profile_facts,
                         canon_attr)

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

# WORLD cases (v3): the fact must be attributed to a NON-SELF subject.
#   kind "wpos": spec = [(subject_rx, attr_rx, value_rx)] all must appear on a
#   non-self subject, and NONE of those attrs may appear as a bare self fact.
WORLD_CASES = [
    ("(.venv) chrismarmo@studio jspace-metacog % python train.py crashed with "
     "oom again", "neg", {"username", "email", "location", "device", "occupation"}),
    ("my friend chris owns the mac studio i ssh into for the big jobs", "wpos",
     [(r"chris|friend", r"possession|device", r"mac|studio")]),
    ("my wife is doing her student placement in maternal and child health",
     "wpos", [(r"wife", r"placement|occupation|education", r"maternal|child")]),
    ("my old supervisor is over at swinburne university these days", "wpos",
     [(r"supervisor", r".*", r"swinburne")]),
]

# v4 (HaluMem entry TBD): EVENT/PLAN probe cases -- v3's "things people might
# do" ban also swallowed concrete EVENTS ("attended a pottery workshop"),
# which HaluMem showed cost us most of our gold memory-point coverage. Same
# (text, kind, spec) "pos"/"neg" shape as CASES. NOT wired into main() yet --
# the orchestrator runs this arm against SYSTEM_V4 separately.
EVENT_CASES = [
    ("i went to a pottery workshop with my sister on january 6th", "pos",
     [("event", r"pottery|workshop")]),
    ("we're planning a trip to japan in november for our anniversary", "pos",
     [("plan", r"japan|trip")]),
    ("i finally ran the half marathon last saturday, finished in just over "
     "two hours", "pos", [("event", r"marathon")]),
    ("maybe i should learn the piano someday", "neg",
     {"event", "plan", "hobby"}),
]

_REL = re.compile(r"^(wife|husband|partner|spouse|daughter|son|child|brother|"
                  r"sister|mother|father|parent|friend|boss|colleague|"
                  r"coworker|ex_boss|old_boss)_", re.I)


def judge(kind, spec, facts):
    canon = [(canon_attr(f["attribute"]), str(f["value"]).lower(),
              str(f["attribute"]).lower(), f.get("subject", "self"))
             for f in facts]
    if kind == "neg":
        # fail only if a FORBIDDEN attribute lands on the USER: bare attr,
        # subject self. Relationship-prefixed (v2) or non-self subject (v3)
        # is correct attribution, not a failure.
        bad = [(a, v) for a, v, raw, s in canon
               if a in spec and s == "self" and not _REL.match(raw)]
        return not bad, bad
    if kind == "wpos":
        missing = []
        for s_rx, a_rx, v_rx in spec:
            hit = any(re.search(s_rx, s) and re.search(a_rx, a) and
                      re.search(v_rx, v)
                      for a, v, _, s in canon if s != "self")
            leak = any(re.fullmatch(a_rx, a) and re.search(v_rx, v)
                       for a, v, raw, s in canon
                       if s == "self" and not _REL.match(raw))
            if not hit or leak:
                missing.append((s_rx, a_rx, "missing" if not hit else "self-leak"))
        return not missing, missing
    missing = [(want, rx) for want, rx in spec
               if not any(a == want and re.search(rx, v)
                          for a, v, _, s in canon if s == "self")]
    return not missing, missing


ARMS = (("v2", SYSTEM_V2), ("v3", SYSTEM_V3))


def main():
    all_cases = CASES + WORLD_CASES
    tally = {(n, k): 0 for n, _ in ARMS for k in ("neg", "pos", "wpos")}
    for text, kind, spec in all_cases:
        res = {}
        for name, system in ARMS:
            facts = extract_profile_facts(text, system=system)
            ok, detail = judge(kind, spec, facts)
            tally[(name, kind)] += ok
            res[name] = (ok, detail, facts)
        aok, bok = res[ARMS[0][0]][0], res[ARMS[1][0]][0]
        mark = "==" if aok == bok else (f"{ARMS[1][0]}+" if bok else f"{ARMS[1][0]}-")
        print(f"[{'ok' if aok else 'XX'}->{'ok' if bok else 'XX'} {mark:3s}] "
              f"({kind}) {text[:58]}")
        if not bok:
            print(f"         {ARMS[1][0]} detail: {res[ARMS[1][0]][1]} "
                  f"facts={res[ARMS[1][0]][2]}")
    counts = {k: sum(1 for _, kk, _ in all_cases if kk == k)
              for k in ("neg", "pos", "wpos")}
    for name, _ in ARMS:
        tot = sum(tally[(name, k)] for k in counts)
        print(f"{name}: {tot}/{len(all_cases)}  ("
              + ", ".join(f"{k} {tally[(name, k)]}/{n}"
                          for k, n in counts.items()) + ")")


if __name__ == "__main__":
    main()
