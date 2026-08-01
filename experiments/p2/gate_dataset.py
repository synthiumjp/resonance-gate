"""Evidence-sufficiency gate dataset (entry 119 planned): (context, question,
label) pairs for probe training, from the deterministic oracle criterion --
no judge, no model.

Label semantics: sufficient=1 iff the question has a REAL gold answer and the
retrieved k=120 context (current committed retrieval config) contains >=50%
of its content tokens in union. No-info golds (Memory Boundary) label 0 --
the gate's correct action there is abstain, same as evidence-absent.

Split: train users (default 13-19) / eval users (default 10-12, the held-out
measurement set every judged number derives from -- NEVER train on these).
Output JSONL (PRIVATE dir -- contexts embed benchmark text):
  ~/rg_private/halumem/dev/gate_train.jsonl, gate_eval.jsonl
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import halumem_run as HR
import retrieve as RV
from wire import _tokens
from oracle import _NO_INFO_RX
from dev_set import _load_users, _parse_users_arg, _cache_path, _cache_complete

OUT_DIR = os.path.expanduser("~/rg_private/halumem/dev")


def rows_for(users, indices, template):
    for uidx in indices:
        user = users[uidx]
        cp = _cache_path(uidx, template)
        complete, have, total = _cache_complete(user, cp)
        if not complete:
            print(f"user {uidx}: cache incomplete ({have}/{total}) -- skipped")
            continue
        mem, _ = HR.ingest_user(user, cp)
        index = RV.build_index(mem)
        for s in user["sessions"]:
            for q in s.get("questions", []):
                question = q.get("question", "")
                gold = str(q.get("answer", "")).strip()
                if not question or not gold:
                    continue
                context = RV.retrieve(mem, question, index=index)
                gt = _tokens(gold)
                if _NO_INFO_RX.search(gold) or not gt:
                    label = 0
                else:
                    u = _tokens(context)
                    label = int(len(gt & u) / len(gt) >= 0.5)
                yield {"user": uidx, "question": question, "context": context,
                       "label": label, "qtype": q.get("question_type", "?"),
                       "gold": gold, "answer": gold,
                       "evidence": q.get("evidence", "")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-users", default="13-19")
    ap.add_argument("--eval-users", default="10-12")
    ap.add_argument("--train-template",
                    default="~/rg_private/halumem/dev/cache_u{i}_17b.jsonl")
    ap.add_argument("--eval-template",
                    default="~/rg_private/halumem/dev/cache_u{i}_v5_14b.jsonl")
    args = ap.parse_args()
    users = _load_users()
    for name, arg, tmpl in (("gate_train", args.train_users, args.train_template),
                            ("gate_eval", args.eval_users, args.eval_template)):
        path = os.path.join(OUT_DIR, f"{name}.jsonl")
        n = pos = 0
        with open(path, "w") as f:
            for row in rows_for(users, _parse_users_arg(arg), tmpl):
                f.write(json.dumps(row) + "\n")
                n += 1
                pos += row["label"]
        print(f"{name}: {n} rows, {pos} sufficient ({100*pos/max(n,1):.1f}%) -> {path}")


if __name__ == "__main__":
    main()
