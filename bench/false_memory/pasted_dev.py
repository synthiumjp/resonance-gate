"""Pasted-text detection on the development set (cases_dev_pasted.jsonl),
no model: for each scenario, the user message holding the pasted text (the
longest user turn of the gold conversation) through prose._drop_pasted.

  class e: passes if the forbidden claim's words are gone from what is kept
           as the user's own (fewer than half of its content words remain).
  class f: passes if every expected term is still in what is kept.

    python pasted_dev.py [-v]"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "experiments", "p2"))
from prose import _drop_pasted  # noqa: E402

STOP = set("the user wants assistant always never their they with from that this have has"
           " been about will would should them what which when where there here".split())


def words(s):
    return [w[:5] for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2 and w not in STOP]


def main():
    v = "-v" in sys.argv
    cases = [json.loads(l) for l in open(os.path.join(HERE, "cases_dev_pasted.jsonl"))]
    ok = {"e": 0, "f": 0}
    n = {"e": 0, "f": 0}
    for c in cases:
        p = c["probes"][0]
        conv = c["conversations"][p.get("gold_conversation") or 0]
        msg = max((t["content"] for t in conv["turns"] if t["role"] == "user"), key=len)
        own = " ".join(_drop_pasted(msg).split()).lower()
        if c["class"] == "e":
            # the sentence of the message that carries the forbidden claim
            # must not be kept as the user's
            pr = p["forbid"]["prop"]
            ws = set(words(" ".join(pr if isinstance(pr, list) else [pr]).replace("The user", "")))
            sents = [x for x in re.split(r"(?<=[.!?:])\s+|\n+", msg) if x.strip()]
            best = max(reversed(sents), key=lambda x: len(ws & set(words(x))))
            key = " ".join(best.split()).lower()[:40]
            if ws & set(words(best)):
                good = key not in own
            else:       # the claim is not worded as in the message (Dr., Welsh)
                good = len(own) * 2 < len(" ".join(msg.split()))
        else:
            good = all(t.lower() in own for t in p["expect"]["terms"])
        n[c["class"]] += 1
        ok[c["class"]] += good
        if v and not good:
            print(f"FAIL {c['id']} {c['class']} {c['subtype']}\n   msg: {' '.join(msg.split())[:200]}\n   own: {own[:200]}")
    print(f"pasted claim or instruction removed from the user's own: {ok['e']}/{n['e']}; "
          f"own material kept: {ok['f']}/{n['f']}")


if __name__ == "__main__":
    main()
