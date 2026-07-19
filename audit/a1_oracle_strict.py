"""A1 supplements (from audit/per_item.csv — run a1_a7_gate_recompute.py
first): (1) the zero-parameter store-membership oracle; (2) sensitivity of
the headline AUROC2 to strict scoring of forced answers on ambiguous items."""

import csv
import os

import numpy as np
from sklearn.metrics import roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
rows = list(csv.DictReader(open(os.path.join(HERE, "per_item.csv"))))
correct = np.array([int(r["correct"]) for r in rows])
kind = np.array([r["kind"] for r in rows])
gate = np.array([float(r["gate_1mu"]) for r in rows])

written = (kind != "ood").astype(float)  # computable exactly from the L2 store
print("AUROC2 written-key oracle (0 params):", round(roc_auc_score(correct, written), 4))
print("AUROC2 GATE(1-u) headline:           ", round(roc_auc_score(correct, gate), 4))
m = kind != "ood"
print("GATE within written items:", round(roc_auc_score(correct[m], gate[m]), 4),
      f"(n={m.sum()}, n_incorrect={int((1 - correct[m]).sum())})")

for k in ("coll", "ref"):
    mm = kind == k
    print(f"{k}: n={mm.sum()} labelled-correct={correct[mm].sum()} "
          f"mean gate 1-u={gate[mm].mean():.3f}")
strict = correct.copy()
strict[(kind == "coll") | (kind == "ref")] = 0
print("AUROC2 GATE under strict coll/ref scoring:",
      round(roc_auc_score(strict, gate), 4))
