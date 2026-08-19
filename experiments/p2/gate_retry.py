"""Validator-with-RETRY (entry 131, MemFlow arXiv:2605.03312 pattern).

Instead of flipping gate-failed attempts to Unknown (entry 130's filter,
which converts them to omissions), RE-COMPOSE each flagged row with a
stricter EXTRACTIVE prompt: quote the memory line that answers, or Unknown.
The probe flags the composer's least-grounded attempts; the retry forces
those specific answers back onto the evidence.

Emits: answers file = champion answers with flagged rows replaced by retry
answers, plus the list of changed row indices (so judging can splice).
"""
import argparse
import json
import os
import pickle
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

EXTRACT_PROMPT = (
    "Below are memory lines about a user, then a question.\n\nMEMORIES:\n{context}\n\n"
    "QUESTION: {question}\n\n"
    "Answer ONLY if one or two memory lines directly contain the answer: give a short "
    "answer taken near-verbatim from those lines (you may drop the tags). If no line "
    "directly contains it, reply exactly: Unknown. Never combine loosely related lines "
    "into a guess.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", required=True)
    ap.add_argument("--train-states", required=True)
    ap.add_argument("--train-labels", required=True)
    ap.add_argument("--eval-states", required=True)
    ap.add_argument("--answers", required=True)
    ap.add_argument("--percentile", type=float, default=5.0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    probe = pickle.load(open(args.probe, "rb"))
    L, sc, clf = probe["layer"], probe["scaler"], probe["clf"]
    tr = np.load(args.train_states)
    votes = None
    for path in args.train_labels.split(","):
        v = np.array([int(json.loads(l)["verdict"] == "Correct") for l in open(path)],
                     dtype=float)
        votes = v if votes is None else votes + v
    ytr = (votes / len(args.train_labels.split(",")) >= 0.5).astype(int)
    ptr = clf.predict_proba(sc.transform(tr["states"][:, L].astype(np.float32)))[:, 1]
    thr = float(np.percentile(ptr[ytr == 1], args.percentile))

    ev = np.load(args.eval_states)
    pev = clf.predict_proba(sc.transform(ev["states"][:, L].astype(np.float32)))[:, 1]
    rows = [json.loads(l) for l in open(args.answers)]
    assert len(rows) == len(pev)

    from llms import llm_request
    changed = []
    with open(args.out, "w") as f:
        for i, (r, p) in enumerate(zip(rows, pev)):
            r = dict(r)
            if p < thr and r["response"].strip().rstrip(".").lower() != "unknown":
                try:
                    retry = llm_request(EXTRACT_PROMPT.format(
                        context=r["context"], question=r["question"]))
                except Exception:
                    retry = "Unknown."
                r["response"] = retry.strip()
                changed.append(i)
            f.write(json.dumps(r) + "\n")
            if changed and len(changed) % 20 == 0 and i == changed[-1]:
                print(f"  ...retried {len(changed)}", flush=True)
    with open(args.out + ".changed", "w") as f:
        json.dump(changed, f)
    n_unk = sum(1 for i in changed
                if json.loads(open(args.out).readlines()[i])["response"]
                .strip().rstrip(".").lower() == "unknown")
    print(f"threshold {thr:.3f} (p{args.percentile:g}); retried {len(changed)}/{len(rows)}; "
          f"{n_unk} retries abstained, {len(changed)-n_unk} re-answered")


if __name__ == "__main__":
    main()
