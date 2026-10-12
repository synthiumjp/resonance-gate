"""Train experiments/p2/paste_clf.py's weights (2026-10-13).

    python train.py DATA_DIR OUT.py [--seed 7]

DATA_DIR holds:
  others.jsonl        {"genre", "writer", "text"}: texts written by someone else (agent-written)
  own.jsonl           {"genre", "text"}: the user's own writing, "{OWNER}" for their name
  intros_other.jsonl  {"place": before|after|next|inline, "text"}: words around someone
                      else's text, "{SRC}" for the source
  intros_own.jsonl    {"place", "text", "neutral"?}: words around the user's own text
  emails.jsonl        {"body"}: public Enron emails (aeslc train), none used in any test set
  chat.jsonl          {"text", "next"}: ordinary chat turns (LoCoMo), the user's own

Each example is a block, the user's words around it (frame) and their next
message (after), composed the way people paste: an introduction before or
after, the source said only in the next message, an "intro:" line, a
neutral request, or nothing. Labels: 1 someone else's, 0 the user's.
Writes a module with the bias, the hashed weights (non-zero only) and a
threshold chosen on held-back examples for few own texts marked.
"""
import json
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "experiments", "p2"))
import paste_clf  # noqa: E402

D, OUT = sys.argv[1], sys.argv[2]
SEED = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 7
LEX = "--lexical" in sys.argv          # word n-grams as well as the abstract features
rng = random.Random(SEED)
load = lambda f: [json.loads(l) for l in open(os.path.join(D, f), encoding="utf-8") if l.strip()]  # noqa: E731
others, own, io_, iw = load("others.jsonl"), load("own.jsonl"), load("intros_other.jsonl"), load("intros_own.jsonl")
emails, chat = load("emails.jsonl"), load("chat.jsonl")
OWNERS = ["Amara Okafor", "Liam Chen", "Sofia Rossi", "Kenji Sato", "Priya Nair", "Tomás García",
          "Hannah Weber", "Yusuf Demir", "Chloe Martin", "Dmitri Volkov", "Aisha Bello", "Noah Kim",
          "Elena Petrova", "Mateo Silva", "Grace O'Brien", "Ravi Kumar", "Zoe Clarke", "Jonas Berg"]
SRCS = ["my boss", "my landlord", "my sister", "a friend", "my mum", "Priya", "Tom", "a guy on reddit",
        "the school", "a client", "my manager", "our neighbour", "my flatmate", "the council", "a recruiter",
        "my cousin", "someone in the group chat", "a customer", "my old boss", "Dan from work"]
by = lambda rows, place: [r["text"] for r in rows if r.get("place") == place and not r.get("neutral")]  # noqa: E731
IO = {p: by(io_, p) for p in ("before", "after", "next", "inline")}
IW = {p: by(iw, p) for p in ("before", "after", "next")}
NEUTRAL = [r["text"] for r in iw if r.get("neutral")]


def src(s):
    return s.replace("{SRC}", rng.choice(SRCS))


def compose(block, label, owner):
    """-> (block, frame, after) as a paste would come in."""
    r = rng.random()
    if label:
        if r < 0.32 and IO["before"]:
            return block, src(rng.choice(IO["before"])), ""
        if r < 0.50 and IO["after"]:
            return block, src(rng.choice(IO["after"])), ""
        if r < 0.70 and IO["next"]:
            return block, "", src(rng.choice(IO["next"]))
        if r < 0.80 and IO["inline"]:
            return block, src(rng.choice(IO["inline"])).replace("...", "").strip(), ""
        if r < 0.92 and NEUTRAL:
            return block, rng.choice(NEUTRAL), ""
        return block, "", ""
    if r < 0.30 and IW["before"]:
        return block, rng.choice(IW["before"]), ""
    if r < 0.45 and IW["after"]:
        return block, rng.choice(IW["after"]), ""
    if r < 0.60 and IW["next"]:
        return block, "", rng.choice(IW["next"])
    if r < 0.80 and NEUTRAL:
        return block, rng.choice(NEUTRAL), ""
    return block, "", ""


ex = []
for o in others:
    for _ in range(3):
        ex.append((compose(o["text"], 1, None), 1, rng.choice(OWNERS)))
for e in emails:
    ex.append((compose(e["body"], 1, None), 1, rng.choice(OWNERS)))
for o in own:
    for _ in range(3):
        owner = rng.choice(OWNERS)
        ex.append((compose(o["text"].replace("{OWNER}", owner.split()[0]), 0, owner), 0, owner))
for e in rng.sample(emails, min(len(emails) // 4, 400)):
    owner = rng.choice(OWNERS)
    body = e["body"].rstrip() + "\n" + owner.split()[0]
    ex.append(((body, rng.choice(IW["before"] or [""]), ""), 0, owner))
for c in chat:
    ex.append(((c["text"], "", c.get("next") or ""), 0, rng.choice(OWNERS)))
# hard negatives (own_hard.jsonl, {"message", "next"}): whole messages of the
# user's own that look like pastes, split as the model will see them at use
# (paste_clf.candidates), every split labelled the user's
if os.path.exists(os.path.join(D, "own_hard.jsonl")):
    for h in load("own_hard.jsonl"):
        owner = rng.choice(OWNERS)
        msg = h["message"].replace("{OWNER}", owner.split()[0])
        for s, e, frame in paste_clf.candidates(msg):
            if len(msg[s:e].split()) >= 20 and (frame.strip() or h.get("next")):
                for _ in range(2):
                    ex.append(((msg[s:e], frame, h.get("next") or ""), 0, owner))
rng.shuffle(ex)

rows, cols, vals, y = [], [], [], []
for k, ((block, frame, after), label, owner) in enumerate(ex):
    for i, v in paste_clf.features(block, frame, after, owner, lexical=LEX).items():
        rows.append(k)
        cols.append(i)
        vals.append(v)
    y.append(label)
from scipy.sparse import csr_matrix  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

X = csr_matrix((vals, (rows, cols)), shape=(len(ex), paste_clf.DIM))
y = np.array(y)
cut = int(len(ex) * 0.8)
m = LogisticRegression(C=1.0, max_iter=2000)
m.fit(X[:cut], y[:cut])
p = m.predict_proba(X[cut:])[:, 1]
yt = y[cut:]
# the threshold: at most 3% of the user's own texts marked as someone else's
own_p = np.sort(p[yt == 0])
thr = float(own_p[int(len(own_p) * 0.97)]) if len(own_p) else 0.5
MIN_T = float(sys.argv[sys.argv.index("--min-threshold") + 1]) if "--min-threshold" in sys.argv else 0.8
thr = max(thr, MIN_T)          # dev sets: below 0.8 the user's own texts are marked (notebook e329)
rec = float((p[yt == 1] >= thr).mean())
fpr = float((p[yt == 0] >= thr).mean())
print(f"examples {len(ex)} (others {int(y.sum())}, own {int(len(y) - y.sum())}); held back {len(yt)}: "
      f"threshold {thr:.3f}, someone else's found {rec:.3f}, own marked {fpr:.3f}")
m.fit(X, y)                     # final weights on everything
w = m.coef_[0]
keep = {int(i): round(float(w[i]), 3) for i in np.nonzero(np.abs(w) >= 0.01)[0]}
with open(OUT, "w", encoding="utf-8") as f:
    f.write('"""Generated by tools/paste_clf/train.py (seed %d, %d examples); do not edit."""\n' % (SEED, len(ex)))
    f.write(f"DIM = {paste_clf.DIM}\nLEXICAL = {LEX}\nBIAS = {float(m.intercept_[0]):.4f}\nTHRESHOLD = {thr:.4f}\n")
    f.write("W = {\n")
    for i in sorted(keep):
        f.write(f"    {i}: {keep[i]},\n")
    f.write("}\n")
print(f"wrote {OUT}: {len(keep)} weights")
