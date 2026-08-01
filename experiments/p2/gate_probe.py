"""Evidence-sufficiency probe: per-layer logistic probes on last-token hidden
states of a small reader model over (evidence, question). Deterministic
labels from gate_dataset.py; train users 13-19, eval 10-12 (held out).

Reports AUROC per layer on the eval split -- the number that decides whether
a post-hoc sufficiency gate (insufficient -> force Unknown) is worth a real
judged run. Literature reference point: 0.97-0.99 achievable
(arXiv:2607.08456); prompt-level methods cap ~0.67.

Usage: gate_probe.py --train states_train.npz --eval states_eval.npz
"""
import argparse

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True)
    ap.add_argument("--eval", dest="eval_", required=True)
    ap.add_argument("--out", default=None, help="save best probe (pkl) here")
    ap.add_argument("--train-labels", default=None,
                    help="judged jsonl: label = verdict=='Correct' (overrides "
                         "the npz containment labels)")
    ap.add_argument("--eval-labels", default=None)
    args = ap.parse_args()
    tr = np.load(args.train)
    ev = np.load(args.eval_)
    Xtr, ytr = tr["states"].astype(np.float32), tr["labels"]
    Xev, yev = ev["states"].astype(np.float32), ev["labels"]

    def judged_labels(path):
        import json
        return np.array([int(json.loads(l)["verdict"] == "Correct")
                         for l in open(path)])
    if args.train_labels:
        ytr = judged_labels(args.train_labels)
        assert len(ytr) == len(Xtr), f"{len(ytr)} labels vs {len(Xtr)} states"
    if args.eval_labels:
        yev = judged_labels(args.eval_labels)
        assert len(yev) == len(Xev), f"{len(yev)} labels vs {len(Xev)} states"
    n_layers = Xtr.shape[1]
    print(f"train {Xtr.shape} pos={ytr.mean():.2f}  eval {Xev.shape} pos={yev.mean():.2f}")
    best = (0.0, -1, None)
    for L in range(n_layers):
        sc = StandardScaler().fit(Xtr[:, L])
        clf = LogisticRegression(max_iter=2000, C=0.1).fit(sc.transform(Xtr[:, L]), ytr)
        auc = roc_auc_score(yev, clf.predict_proba(sc.transform(Xev[:, L]))[:, 1])
        marker = ""
        if auc > best[0]:
            best = (auc, L, (sc, clf))
            marker = "  <-- best"
        print(f"layer {L:2}  AUROC {auc:.3f}{marker}")
    print(f"\nBEST: layer {best[1]}  AUROC {best[0]:.3f}")
    if args.out and best[2]:
        import pickle
        with open(args.out, "wb") as f:
            pickle.dump({"layer": best[1], "scaler": best[2][0],
                         "clf": best[2][1], "auroc_eval": best[0]}, f)
        print(f"saved {args.out}")


if __name__ == "__main__":
    main()
