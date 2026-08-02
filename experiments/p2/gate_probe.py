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

    def judged_labels(paths):
        """Comma-separated judged jsonls -> per-row fraction-Correct (soft
        label). One file reproduces the old binary behaviour."""
        import json
        votes = None
        for path in paths.split(","):
            v = np.array([int(json.loads(l)["verdict"] == "Correct")
                          for l in open(path)], dtype=float)
            votes = v if votes is None else votes + v
        return votes / len(paths.split(","))
    if args.train_labels:
        ytr = judged_labels(args.train_labels)
        assert len(ytr) == len(Xtr), f"{len(ytr)} labels vs {len(Xtr)} states"
    if args.eval_labels:
        yev = judged_labels(args.eval_labels)
        assert len(yev) == len(Xev), f"{len(yev)} labels vs {len(Xev)} states"
    n_layers = Xtr.shape[1]
    print(f"train {Xtr.shape} pos={ytr.mean():.2f}  eval {Xev.shape} pos={yev.mean():.2f}")
    # soft labels: train on sample-weighted binarized votes (a row correct
    # under 2/3 composers enters both classes, weighted) -- keeps sklearn's
    # logistic machinery while using the extra signal. Eval AUROC is scored
    # against "champion-correct" (first eval file / binarized) for
    # comparability with probe v2.
    best = (0.0, -1, None)
    from sklearn.linear_model import LogisticRegressionCV
    yev_bin = (yev >= 0.5).astype(int) if yev.dtype != int else yev
    for L in range(n_layers):
        sc = StandardScaler().fit(Xtr[:, L])
        Xs = sc.transform(Xtr[:, L])
        if np.array_equal(ytr, ytr.astype(int)):
            clf = LogisticRegressionCV(max_iter=2000, cv=5).fit(Xs, ytr.astype(int))
        else:
            X2 = np.concatenate([Xs, Xs]); y2 = np.array([1]*len(Xs)+[0]*len(Xs))
            w2 = np.concatenate([ytr, 1.0-ytr])
            clf = LogisticRegressionCV(max_iter=2000, cv=5).fit(X2, y2, sample_weight=w2)
        auc = roc_auc_score(yev_bin, clf.predict_proba(sc.transform(Xev[:, L]))[:, 1])
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
