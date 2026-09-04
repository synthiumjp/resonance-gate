"""E5.1 pilot: family-mix tuning on the DEV seed (5551001) only. Counts
answered-error yield per family under the frozen artifact and writes
e5/pilot_mix.md. The EVAL seed is never touched here."""

import os

import _env
_env.patch_cache()

import numpy as np

from corpus_v2 import CorpusV2Config, build_v2, score_item

HERE = os.path.dirname(os.path.abspath(__file__))


def run_pilot(cfg, log_lines):
    c = build_v2(cfg)
    mem = c.memory
    say = log_lines.append
    say(f"pilot seed={cfg.seed}: k={mem.k} N={len(mem.ent)} "
        f"items={len(c.items)} rejected_writes={len(c.rejected_writes)}")
    fam_stats = {}
    n_err_ans = 0
    for it in c.items:
        q = mem.query(it.subj_term, it.rel)
        subj = mem.ent.resolve(it.subj_term, top=1)[0][0]
        rel = mem.rel.resolve(it.rel, top=1)[0][0]
        a, m_l1, top1 = mem._unbind(subj, rel)
        strict, either = score_item(it, top1)
        f = fam_stats.setdefault(it.family, {"n": 0, "answer": 0,
                                             "ans_err": 0, "ans_ok": 0,
                                             "routes": {}})
        f["n"] += 1
        f["routes"][q.action] = f["routes"].get(q.action, 0) + 1
        if q.action == "answer":
            f["answer"] += 1
            if strict:
                f["ans_ok"] += 1
            else:
                f["ans_err"] += 1
                n_err_ans += 1
    for fam in sorted(fam_stats):
        s = fam_stats[fam]
        say(f"  {fam:14s} n={s['n']:3d} answered={s['answer']:3d} "
            f"ans_err={s['ans_err']:3d} ans_ok={s['ans_ok']:3d} "
            f"routes={s['routes']}")
    say(f"  TOTAL answered-errors (strict): {n_err_ans}  (target >= 60)")
    return n_err_ans


def main():
    L = ["# E5.1 pilot log — family-mix tuning (DEV seed 5551001 only)", "",
         "Tuning trajectory (answered-errors, strict, frozen artifact):",
         "  1. initial mix (id=100, ood=50, syn=30, nearkey=16, conf=30, "
         "para=12, ref=12): 16 — most hazards routed RECOLLECT/DELIBERATE; "
         "f_confusable 30/30 recollect (kept as a finding).",
         "  2. + isolation filter (subjects for f_syn/f_id/f_distract need "
         "registry m_ref >= 0.25) + f_distract family; "
         "id=40, syn=55, conf=15, distract=15: 52.",
         "  3. syn=65, conf=12, distract=8: 60 (k=244).",
         "  4. syn=72: 61 (k=259 — recollect eats the gain near paging).",
         "  5. FINAL: syn=74, id=36, conf=8, para=6, distract=8: 63 at "
         "k=251. Frozen as CorpusV2Config defaults.", ""]
    cfg = CorpusV2Config(seed=_env.SEED_DEV_CORPUS)
    n = run_pilot(cfg, L)
    L.append("")
    L.append(f"final default config: {cfg}")
    with open(os.path.join(HERE, "pilot_mix.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
