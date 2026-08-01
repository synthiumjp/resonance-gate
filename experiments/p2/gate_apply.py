"""Apply the sufficiency probe as a post-hoc gate over saved composer answers.

Threshold is PRE-REGISTERED from the train split: the 10th percentile of the
probe score over train rows whose label is positive -- i.e. we accept losing
<=10% of genuinely-answerable attempts, no eval peeking.

Usage:
  gate_apply.py --probe P.pkl --train-states T.npz --train-labels J.jsonl \
                --eval-states E.npz --answers A.jsonl --out GATED.jsonl
"""
import argparse
import json
import pickle

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", required=True)
    ap.add_argument("--train-states", required=True)
    ap.add_argument("--train-labels", required=True,
                    help="judged jsonl (verdict=='Correct' = positive)")
    ap.add_argument("--eval-states", required=True)
    ap.add_argument("--answers", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    probe = pickle.load(open(args.probe, "rb"))
    L, sc, clf = probe["layer"], probe["scaler"], probe["clf"]

    tr = np.load(args.train_states)
    ytr = np.array([int(json.loads(l)["verdict"] == "Correct")
                    for l in open(args.train_labels)])
    ptr = clf.predict_proba(sc.transform(tr["states"][:, L].astype(np.float32)))[:, 1]
    thr = float(np.percentile(ptr[ytr == 1], 10))

    ev = np.load(args.eval_states)
    pev = clf.predict_proba(sc.transform(ev["states"][:, L].astype(np.float32)))[:, 1]
    rows = [json.loads(l) for l in open(args.answers)]
    assert len(rows) == len(pev)
    flipped = 0
    with open(args.out, "w") as f:
        for r, p in zip(rows, pev):
            r = dict(r)
            if p < thr and r["response"].strip().rstrip(".").lower() != "unknown":
                r["response"] = "Unknown."
                flipped += 1
            f.write(json.dumps(r) + "\n")
    print(f"threshold {thr:.3f} (train 10th pct of Correct class); "
          f"flipped {flipped}/{len(rows)}")


if __name__ == "__main__":
    main()
