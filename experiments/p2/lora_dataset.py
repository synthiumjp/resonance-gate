"""Build supervised training data for a specialised extractor (LoRA).

Post-processing is exhausted: composition is worth +0.6pt pooled (e220),
all-turns +1.65pt judged-null (e212). We need +11pt of integrity recall for
F1 0.50 and +21pt for Mem0 parity, and the leaders reach 80-87 F1 with typed
extraction architectures. Gold is 96% prose (e217), so their advantage is in
WHAT they emit per turn -- the extractor itself, which section 4b says cannot
be fixed by prompting. That leaves training one.

HaluMem ships exactly the supervision needed: 20 users, ~15k gold memory
points, each session carrying both its dialogue and its gold points.

CONTAMINATION DISCIPLINE, and it is the whole reason this file exists rather
than a one-liner. Every official number this project reports is users 0-9.
Training on any part of them would make every subsequent evaluation
meaningless and unrecoverable -- there is no way to un-see training data. So:

    TRAIN   users 10-19   (10 users)
    EVAL    users 0-9     never touched, officials stay clean

This mirrors the entry-130 gate, which trained on u13-19 for the same reason.
The split is asserted at build time and the eval users are refused loudly, not
silently filtered.

ALIGNMENT. Gold points are per-SESSION; a model is prompted per-TURN. Each
gold point is assigned to the single turn that best covers its content tokens
(the same measure as e189's ceiling analysis, which put single-turn any-role
reachability at 86.9%). Points no turn covers are UNLEARNABLE from a single
turn and are dropped -- the count is reported, because it is the ceiling on
what this training data can teach.

Output is chat-format JSONL, one example per turn that has at least one
attributable gold point, plus a configurable share of NEGATIVE turns (gold
says nothing here) so the model learns to emit an empty list. Without those it
will hallucinate a memory for every turn -- the failure mode e185 measured as
1.66x over-extraction.
"""
import argparse
import collections
import json
import os
import random
import re

DATA = os.path.expanduser("~/rg_private/halumem/HaluMem-Medium.jsonl")
TRAIN_USERS = list(range(10, 20))
EVAL_USERS = list(range(0, 10))

STOP = set("the a an is are was were of to in on at for and or with his her "
           "their its it he she they as by from that this what which who".split())

SYSTEM = ("Extract the memory points a long-term memory system should store "
          "from this message. Output a JSON array of objects with keys "
          '"type" (Persona|Event|Relationship) and "content" (one complete '
          "sentence naming the person). Output [] if there is nothing to "
          "store.")


def toks(s):
    return {w for w in re.findall(r"[a-z0-9]+", str(s).lower())
            if w not in STOP and len(w) > 2}


def build(users, per_turn_cover=0.5, neg_ratio=0.3, seed=0):
    rng = random.Random(seed)
    rows = [json.loads(l) for l in open(DATA, encoding="utf-8")]
    out, stats = [], collections.Counter()

    for ui in users:
        if ui in EVAL_USERS:
            raise SystemExit(
                f"REFUSING to build training data from user {ui}: users "
                f"{EVAL_USERS[0]}-{EVAL_USERS[-1]} are the evaluation split "
                "and every official number depends on them staying unseen.")
        u = rows[ui]
        for sess in u["sessions"]:
            turns = [t for t in (sess.get("dialogue") or [])
                     if str(t.get("content", "")).strip()]
            if not turns:
                continue
            ttok = [toks(t.get("content", "")) for t in turns]
            assigned = collections.defaultdict(list)
            for mp in sess.get("memory_points", []):
                g = toks(mp.get("memory_content"))
                if not g:
                    continue
                stats["gold_total"] += 1
                best, bi = 0.0, None
                for i, tk in enumerate(ttok):
                    c = len(g & tk) / len(g)
                    if c > best:
                        best, bi = c, i
                if bi is None or best < per_turn_cover:
                    stats["gold_unattributable"] += 1
                    continue
                stats["gold_attributed"] += 1
                assigned[bi].append(mp)

            for i, t in enumerate(turns):
                mps = assigned.get(i)
                if not mps and rng.random() > neg_ratio:
                    continue
                tgt = [{"type": str(m.get("memory_type", "")).replace(" Memory", ""),
                        "content": m.get("memory_content", "")} for m in (mps or [])]
                out.append({"messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content":
                        f"[{t.get('role','user')}] " + str(t["content"]).strip()[:1800]},
                    {"role": "assistant", "content": json.dumps(tgt, ensure_ascii=False)},
                ]})
                stats["neg" if not mps else "pos"] += 1
    return out, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    ap.add_argument("--cover", type=float, default=0.5)
    ap.add_argument("--neg-ratio", type=float, default=0.3)
    a = ap.parse_args()

    ex, st = build(TRAIN_USERS, a.cover, a.neg_ratio)
    g = st["gold_total"] or 1
    print(f"TRAIN users {TRAIN_USERS[0]}-{TRAIN_USERS[-1]}  "
          f"(EVAL {EVAL_USERS[0]}-{EVAL_USERS[-1]} untouched)")
    print(f"  gold points          {st['gold_total']}")
    print(f"    attributable       {st['gold_attributed']}  "
          f"({st['gold_attributed']/g:.1%})  <- ceiling this data can teach")
    print(f"    unattributable     {st['gold_unattributable']}  "
          f"({st['gold_unattributable']/g:.1%})  no single turn covers >= {a.cover}")
    print(f"  examples             {len(ex)}  "
          f"({st['pos']} positive, {st['neg']} negative)")
    lens = [len(e["messages"][1]["content"]) + len(e["messages"][2]["content"])
            for e in ex]
    lens.sort()
    print(f"  chars/example        median {lens[len(lens)//2]}, "
          f"p90 {lens[int(.9*len(lens))]}, max {lens[-1]}")
    tgts = [json.loads(e["messages"][2]["content"]) for e in ex]
    n = collections.Counter(len(t) for t in tgts)
    print(f"  targets/example      {dict(sorted(n.items())[:6])}")
    ty = collections.Counter(x["type"] for t in tgts for x in t)
    print(f"  target types         {dict(ty)}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            for e in ex:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        print(f"\n  wrote {a.out}")
    print("\n  NOTE: the attributable share is the ceiling on what a per-turn")
    print("  model can learn from this data. Session-level gold that no single")
    print("  turn supports is not a modelling failure, it is unlearnable here.")


if __name__ == "__main__":
    main()
