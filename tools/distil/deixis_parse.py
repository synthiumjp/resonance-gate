"""Person deixis from the parse: each noun in the owner's speech is anchored
to a grammatical person -- its possessor (my/our = 1, your = 2), else the
subject of its clause (I/we = 1, you = 2), else none. A note whose content
noun the owner only ever anchors in the second person is the other
speaker's. Tested against the 14B judge's labels."""
import json, sys
from collections import Counter, defaultdict
sys.path.insert(0, "/Users/chrismarmo/jpwork/sdr-distil/server")
sys.path.insert(0, "/Users/chrismarmo/jpwork/sdr-distil")
from sourcedrecall.notes import _stems, _stem
from rgx import Extractor
nlp = Extractor()._parser()
C = json.load(open("/Users/chrismarmo/jpwork/locomo10.json"))
IDX = {"Caroline": 0, "Melanie": 0, "Gina": 1, "Jon": 1}
P1 = {"i", "me", "my", "mine", "we", "us", "our", "ours", "myself", "ourselves"}
P2 = {"you", "your", "yours", "yourself", "yourselves"}

def person(w):
    w = w.lower()
    return 1 if w in P1 else 2 if w in P2 else 0

def anchor(sent, tok):
    words = sent.words
    kids = defaultdict(list)
    for w in words:
        kids[w.head].append(w)
    for k in kids[tok.id]:
        if k.deprel == "nmod:poss":
            return person(k.text) or 3
    h = tok
    for _ in range(6):                     # up to the clause head
        subj = [k for k in kids[h.id] if k.deprel in ("nsubj", "nsubj:pass")]
        if subj:
            return person(subj[0].text) or 3
        if h.head == 0:
            return 0
        h = words[h.head - 1]
    return 0

CACHE = {}
def noun_anchors(owner, conv_i, sess):
    key = (owner, conv_i, sess)
    if key not in CACHE:
        s = C[conv_i]["conversation"]["session_" + sess[1:]]
        a = defaultdict(Counter)
        for t in s:
            if t["speaker"] != owner:
                continue
            for sent in nlp(t["text"]).sentences:
                for w in sent.words:
                    if w.upos in ("NOUN", "PROPN"):
                        a[_stem(w.lemma.lower())][anchor(sent, w)] += 1
        CACHE[key] = a
    return CACHE[key]

for store in sys.argv[1:]:
    rows = json.load(open(store + "_judged.json"))
    res = {k: (Counter(), Counter()) for k in ("any_noun_2only", "majority_2only")}
    for r in rows:
        a = noun_anchors(r["owner"], IDX[r["owner"]], r["sess"])
        stems = [x for x in _stems(r["note"]) - _stems(r["owner"]) if x in a]
        two_only = [x for x in stems if a[x][2] and not a[x][1] and not a[x][0] and not a[x][3]]
        bad = {"any_noun_2only": bool(two_only),
               "majority_2only": bool(stems) and len(two_only) * 2 >= len(stems)}
        for k, v in bad.items():
            res[k][0 if v else 1][r["label"]] += 1
    for k, (d, kept) in res.items():
        print(store.split("/")[-1], k, "dropped", dict(d), "| kept", dict(kept))

if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[-1] == "--show":
    pass
