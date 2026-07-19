"""A6: reproduce the frozen H2 foil head from the DEV corpus (seed 20260719,
config from instruments/h2_foil.py) without writing to instruments/, and
compare against the committed h2_foil_head.json. If the committed head could
only have come from dev-only training with the documented seeds, every weight
must match to float precision.

Also: dev-vs-confirmatory feature-shift check (the Deviation-1 landmine
class) and the linear-foil-strength question (is a logistic head the
strongest fair foil? — gradient-boosted comparison, cross-fit, audit-only).

Writes audit/a6_output.txt.
"""

import json
import os

import numpy as np

import _common
_common.patch_cache()

HERE = os.path.dirname(os.path.abspath(__file__))
L = []


def say(s=""):
    print(s)
    L.append(s)


def main():
    from corpus import CorpusConfig, build
    from h2_foil import collect, DEV_SEED, TRAIN_SEED, FEATURES
    from baselines import LogisticProbe
    from type2 import auroc2

    committed = json.load(open(os.path.join(_common.R, "instruments",
                                            "h2_foil_head.json")))

    cfg = CorpusConfig(seed=DEV_SEED, n_entities=500, n_facts=160,
                       n_id=150, n_ood=90, n_coll=20, n_ref=20)
    X, y = collect(cfg)
    say(f"dev corpus rebuilt: n={len(y)} acc={y.mean():.4f}")

    head = LogisticProbe(seed=TRAIN_SEED + 2).fit(X, y)
    dw = np.abs(np.array(committed["w"]) - head.w).max()
    dmu = np.abs(np.array(committed["mu"]) - head.mu).max()
    say(f"refit vs committed head: max|dw|={dw:.2e} max|dmu|={dmu:.2e} "
        f"keep match={list(head.keep) == committed['keep']}")
    say(f"-> committed head {'IS' if dw < 1e-9 else 'IS NOT'} exactly the "
        f"dev-only fit with the documented seeds")

    # cross-fit dev number
    rng = np.random.default_rng(TRAIN_SEED)
    fold = rng.permutation(len(y)) % 2
    pred = np.zeros(len(y))
    for f in (0, 1):
        tr, te = fold != f, fold == f
        pred[te] = LogisticProbe(seed=TRAIN_SEED + f).fit(X[tr], y[tr]).predict(X[te])
    say(f"dev cross-fit AUROC2: recomputed {auroc2(pred, y):.4f} vs committed "
        f"{committed['dev_auroc2_crossfit']:.4f}")
    say()

    # feature shift dev -> confirmatory
    c = _common.build_registered_corpus()
    rowsC, XC = _common.phase_c_rows(c)
    yC = np.array([r["correct"] for r in rowsC])
    say("feature means dev -> confirmatory (constant-on-dev features were the "
        "Deviation-1 failure):")
    for j, name in enumerate(FEATURES):
        say(f"  {name:6s} dev {X[:, j].mean():9.4f} (sd {X[:, j].std():.4f})  "
            f"conf {XC[:, j].mean():9.4f} (sd {XC[:, j].std():.4f})")
    say()

    # is a LINEAR foil the ceiling? gradient-boosted trees, same features,
    # same cross-fit protocol, registered assignment seed for folds
    from sklearn.ensemble import HistGradientBoostingClassifier
    rng = np.random.default_rng(999000022)
    foldC = rng.permutation(len(yC)) % 2
    predg = np.zeros(len(yC))
    predl = np.zeros(len(yC))
    for f in (0, 1):
        tr, te = foldC != f, foldC == f
        gb = HistGradientBoostingClassifier(random_state=0, max_iter=300)
        gb.fit(XC[tr], yC[tr])
        predg[te] = gb.predict_proba(XC[te])[:, 1]
        predl[te] = LogisticProbe(seed=f).fit(XC[tr], yC[tr]).predict(XC[te])
    gate_1mu = np.array([1.0 - r["op"].u for r in rowsC])
    say("stronger-foil check on confirmatory items (cross-fit, audit-only):")
    say(f"  GATE(1-u)              {auroc2(gate_1mu, yC):.4f}")
    say(f"  frozen linear foil     0.9920 (committed)")
    say(f"  cross-fit linear foil  {auroc2(predl, yC):.4f}")
    say(f"  cross-fit GBM foil     {auroc2(predg, yC):.4f}")
    say(f"  GBM - GATE gap         {auroc2(predg, yC) - auroc2(gate_1mu, yC):+.4f} "
        f"(H2 margin was 0.02)")

    with open(os.path.join(HERE, "a6_output.txt"), "w") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
