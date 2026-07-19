"""A2: characterise the VERBALISED baseline's response distribution on the
registered corpus (seed family 999000021-24), same prompts and per-item seeds
as phase_c.py. Backend here is CPU (llama-cpp CPU wheel); the registered run
was GPU — deltas are reported, the distribution shape is the target.

Also logs raw model text so prompt/parse coercion is auditable.
Writes audit/a2_output.txt + audit/a2_raw.jsonl. Read-only elsewhere.
"""

import json
import os

import numpy as np

import _common
_common.patch_cache()

SEED_ASSIGN = 999000022
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    from speak import render
    import baselines as bl
    from llm import generate
    from type2 import auroc2

    c = _common.build_registered_corpus()
    rows, _ = _common.phase_c_rows(c)
    correct = np.array([r["correct"] for r in rows])
    kinds = np.array([r["it"].kind for r in rows])

    raws, vals = [], []
    for i, r in enumerate(rows):
        answer = render((r["subj"], r["rel"], r["answer"]))
        raw = generate("/no_think You answer with a single integer only.",
                       bl.VERBALISE_PROMPT.format(subj=r["subj"], rel=r["rel"],
                                                  answer=answer),
                       max_tokens=8, temperature=0.0, seed=SEED_ASSIGN + i)
        v = bl._parse_int(raw)
        vals.append((v if v is not None else 50) / 100.0)
        raws.append({"i": i, "kind": r["it"].kind, "correct": bool(r["correct"]),
                     "answer": answer, "raw": raw, "parsed": v})
        if i % 40 == 0:
            print(f"[{i}/280]", flush=True)

    vals = np.array(vals)
    L = []

    def say(s=""):
        print(s)
        L.append(s)

    say(f"n={len(vals)}  AUROC2(verbalised)={auroc2(vals, correct):.4f} "
        f"(committed GPU run: 0.4933)")
    uniq, cnt = np.unique(vals, return_counts=True)
    say("value distribution (value: count):")
    for u, ct in zip(uniq, cnt):
        say(f"  {u:.2f}: {ct}")
    say(f"parse failures (defaulted to 0.50): "
        f"{sum(1 for r in raws if r['parsed'] is None)}")
    say(f"mean by class: correct={vals[correct].mean():.3f} "
        f"incorrect={vals[~correct].mean():.3f}")
    say(f"mean by kind: " + str({k: round(float(vals[kinds == k].mean()), 3)
                                 for k in ('id', 'ood', 'coll', 'ref')}))
    top = uniq[np.argmax(cnt)]
    say(f"modal value {top:.2f} covers {cnt.max()}/{len(vals)} "
        f"= {cnt.max() / len(vals):.1%} of items")

    with open(os.path.join(HERE, "a2_raw.jsonl"), "w") as f:
        for r in raws:
            f.write(json.dumps(r) + "\n")
    with open(os.path.join(HERE, "a2_output.txt"), "w") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
