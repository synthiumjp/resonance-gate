"""Write evaluation_uqa.py next to HaluMem's official evaluation.py: the same
scorer with only the memory-update and question-answering parts.

    python make_eval_uqa.py <path to HaluMem/eval>
    cd <path to HaluMem/eval> && python evaluation_uqa.py --frame rgp2 --version ... --user_num 2

2026-10-13: the integrity and accuracy parts judge extracted memory
statements (1,649 accuracy items for one user at ~13-34 s each on the local
judge). sourcedrecall stores messages as written and extracts no memory
statements, so those parts fit it poorly; the update and QA parts are what
systems are compared on. The update and QA code is copied unchanged from the
official file (the text between its "# Memory Update Evaluation" and
"# Memory Type Accuracy" comments); results go to a separate cache and file.
"""
import os
import sys

d = sys.argv[1]
src = open(os.path.join(d, "evaluation.py"), encoding="utf-8").read()

skip = "    # Memory Integrity Evaluation\n    with ProcessPoolExecutor"
assert src.count(skip) == 1
src = src.replace(skip, "    # sourcedrecall: the update and QA parts only (make_eval_uqa.py)\n"
                        "    memory_integrity_inputs, memory_accuracy_inputs = [], []\n\n" + skip)

a, b = "    # Memory Update Evaluation\n", "    # Memory Type Accuracy\n"
i, j = src.index(a, src.index("def aggregate_eval_results")), src.index(b)
agg = "def aggregate_uqa(eval_results):\n" + src[i:j] + "    return eval_results\n\n\n"
src = src.replace("def iter_jsonl(", agg + "def iter_jsonl(", 1)

for old, new in (('eval_results = aggregate_eval_results(eval_results)', 'eval_results = aggregate_uqa(eval_results)'),
                 ('tmp_dir = os.path.join(dir_path, "tmp2")', 'tmp_dir = os.path.join(dir_path, "tmp_uqa")'),
                 ('f"{frame}_eval_stat_result.json"', 'f"{frame}_eval_stat_result_uqa.json"')):
    assert src.count(old) == 1, old
    src = src.replace(old, new)

open(os.path.join(d, "evaluation_uqa.py"), "w", encoding="utf-8").write(src)
print("wrote", os.path.join(d, "evaluation_uqa.py"))
