"""Generate a user's extraction artifact from the PARSER, no model calls.

Same JSON shape as lora_artifact.py so the judged A/B can score either
generator without knowing which produced it. Runs on CPU: spaCy only.

Each proposition carries the session and turn it came from -- the receipt --
and passes the deterministic check layer (grammar_check.prefilter) which
removes provably invented content at zero measured cost to recall.
"""
import argparse
import collections
import json
import os
import re
import sys

DATA = os.path.expanduser("~/rg_private/halumem/HaluMem-Medium.jsonl")
P2 = "/home/jp/rg/experiments/p2"
if P2 not in sys.path:
    sys.path.insert(0, P2)
TRAIN_USERS = set(range(10, 20))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scope", default="user", choices=("user", "all"))
    ap.add_argument("--no-check", action="store_true")
    ap.add_argument("--cap", type=int, default=0,
                    help="keep only the top-N records per SESSION by "
                         "grammar_check.quality. e229: surplus records cost "
                         "recall because the integrity judge reads a session's "
                         "emissions as one blob.")
    a = ap.parse_args()
    if a.user in TRAIN_USERS:
        raise SystemExit(f"REFUSING: user {a.user} is a TRAINING user.")

    import spacy
    import grammar_parse as G
    import grammar_check as C
    nlp = spacy.load("en_core_web_sm")

    user = [json.loads(l) for l in open(DATA, encoding="utf-8")][a.user]
    owner = None
    for s in user["sessions"]:
        for mp in s.get("memory_points", []):
            m = re.match(r"User's name is (.+?)\s*$", str(mp.get("memory_content", "")))
            if m:
                owner = m.group(1).strip()
    print(f"user {a.user}, owner {owner!r}, scope {a.scope}, check={not a.no_check}")

    per = collections.defaultdict(list)
    dropped = collections.Counter()
    nturns = 0
    for si, s in enumerate(user["sessions"]):
        for ti, t in enumerate(s.get("dialogue") or []):
            txt = str(t.get("content", "")).strip()
            if not txt or (a.scope == "user" and t.get("role") != "user"):
                continue
            nturns += 1
            for p, kind in G.extract(txt, nlp, owner,
                                     role=t.get("role", "user")):
                if not a.no_check:
                    ok, why = C.prefilter(p, txt, owner)
                    if not ok:
                        dropped[why.split(" (")[0]] += 1
                        continue
                per[si].append({"content": p, "type": kind,
                                "session": si, "turn": ti,
                                "q": round(C.quality(p, txt, owner), 4)})
        if si % 20 == 0:
            print(f"  session {si}/{len(user['sessions'])}", flush=True)

    n = sum(len(v) for v in per.values())
    print(f"turns {nturns} -> {n} propositions; dropped {dict(dropped)}")
    if a.cap:
        kept = 0
        for si in list(per):
            ranked = sorted(per[si], key=lambda x: -x.get("q", 0))
            # dedupe identical content before capping, so the cap is spent on
            # distinct facts rather than repeats
            seen, uniq = set(), []
            for x in ranked:
                k = x["content"].lower()
                if k in seen:
                    continue
                seen.add(k)
                uniq.append(x)
            per[si] = uniq[:a.cap]
            kept += len(per[si])
        print(f"  capped at {a.cap}/session -> {kept} propositions "
              f"({kept/max(1,n):.0%} of raw)")
        n = kept
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"user": a.user, "owner": owner, "scope": a.scope,
                   "generator": "grammar_parse+check", "unparseable": 0,
                   "dropped": dict(dropped),
                   "sessions": {str(k): v for k, v in per.items()}}, fh)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
