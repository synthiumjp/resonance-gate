"""E5.1 — one command: fair corpus -> frozen loop -> all confidence sources
-> STRICT-scored type-2 analysis -> stratified report.

The stage question (audit A1): on a confusable corpus, under strict scoring,
does the gate's geometry rank correctness BEYOND store membership? The
registered null-to-beat is ORACLE (exact-key membership), not verbalised
confidence.

Frozen dirs + instruments/ are READ-ONLY: type2.py, baselines.LogisticProbe,
opinion, the substrate/gate/mouth are imported and used, never modified. The
embedding cache is redirected (e5/_env.py) before any registry is built.

Usage:
  python e5/run_e51.py                 # full run (mouth on GPU), writes report
  python e5/run_e51.py --no-mouth      # skip VERBALISED-INFORMED (fast, geometry only)
The leak pass emits candidate outputs for leak_v3's external judge but does
NOT call the API (that needs the registrant's key decision) — see the
'--leak-outputs' file it writes and e5/leak_v3.py.
"""

import argparse
import json
import os

import _env
_env.patch_cache()

import numpy as np

from corpus_v2 import CorpusV2Config, build_v2, score_item
from oracle import oracle_scores, membership
import baselines_v2 as bl2
from baselines import LogisticProbe
from type2 import auroc2, ece, meta_d_prime, paired_bootstrap
from opinion import C_REF, S_REF, sigmoid
from l2_ambiguity import C_L2, S_L2
from speak import ABSTAIN_TEXT, deliberate_text, gen_leadin, render, verify_leadin

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(HERE, "e51_report.md")
LEAK_OUTPUTS = os.path.join(HERE, "e51_leak_candidates.jsonl")


def collect(cfg):
    """Frozen loop over corpus items -> corpus, per-item rows, feature matrix."""
    c = build_v2(cfg)
    rows = _collect_rows(c)
    X = np.array([[r["a"], r["m_l1"], r["m_l2"], r["m_ref"],
                   float(c.memory.k), float(len(c.memory.ent))] for r in rows])
    return c, rows, X


def sk_bootstrap_diff(a, b, correct, B, seed):
    """Paired bootstrap CI of AUROC2(a) - AUROC2(b)."""
    rng = np.random.default_rng(seed)
    n = len(correct)
    diffs = []
    for _ in range(B):
        idx = rng.integers(n, size=n)
        c = correct[idx]
        if c.all() or not c.any():
            continue
        diffs.append(auroc2(a[idx], c) - auroc2(b[idx], c))
    v = np.array(diffs)
    return (auroc2(a, correct) - auroc2(b, correct),
            float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-mouth", action="store_true")
    args = ap.parse_args()
    L = []

    def say(s=""):
        print(s)
        L.append(s)

    # ---- DEV split: train FOIL-v2 (disjoint seed, never scored)
    dev_cfg = CorpusV2Config(seed=_env.SEED_DEV_CORPUS)
    dev_c, dev_rows, X_dev = collect(dev_cfg)
    y_dev = np.array([r["strict"] for r in dev_rows])

    # ---- EVAL split: the single scored run
    eval_cfg = CorpusV2Config(seed=_env.SEED_EVAL_CORPUS)
    c, rows, X = collect(eval_cfg)
    mem = c.memory
    n = len(rows)
    strict = np.array([r["strict"] for r in rows])
    either = np.array([r["either"] for r in rows])
    fam = np.array([r["family"] for r in rows])
    action = np.array([r["action"] for r in rows])
    answered = action == "answer"

    say("# E5.1 report — fair-corpus type-2 analysis (strict scoring primary)")
    say("")
    say(f"artifact: rg-freeze-1.0 (frozen, read-only). judge model for leak: "
        f"see e5/leak_v3.py (not run here).")
    say(f"seeds: dev_corpus={_env.SEED_DEV_CORPUS} eval_corpus="
        f"{_env.SEED_EVAL_CORPUS} assign={_env.SEED_ASSIGN} "
        f"boot={_env.SEED_BOOT} perm={_env.SEED_PERM}")
    say(f"eval corpus: k={mem.k} N={len(mem.ent)} items={n} "
        f"rejected_writes={len(c.rejected_writes)}")
    say(f"strict accuracy={strict.mean():.4f}  either-object accuracy="
        f"{either.mean():.4f}")
    say(f"answered (routed ANSWER): {answered.sum()}  "
        f"answered-errors (strict): {int((answered & ~strict).sum())}  "
        f"answered-errors (either): {int((answered & ~either).sum())}")
    say("")

    # ---------- confidence sources
    gate = bl2.gate_sources(rows)
    member, member_cos = oracle_scores(mem, rows)
    sources = dict(gate)
    sources["ORACLE"] = member
    sources["ORACLE+cos"] = member_cos

    # FOIL-v2: 2-fold cross-fit dev AUROC2 (honest) + full-dev head on eval
    rng = np.random.default_rng(_env.SEED_FOIL_TRAIN)
    fold = rng.permutation(len(y_dev)) % 2
    pred_dev = np.zeros(len(y_dev))
    for f in (0, 1):
        tr, te = fold != f, fold == f
        pred_dev[te] = LogisticProbe(seed=_env.SEED_FOIL_TRAIN + f).fit(
            X_dev[tr], y_dev[tr]).predict(X_dev[te])
    foil_dev_auc = auroc2(pred_dev, y_dev)
    foil_eval, foil_head = bl2.foil_v2(X_dev, y_dev, X, _env.SEED_FOIL_TRAIN + 2)
    sources["FOIL-v2"] = foil_eval

    if not args.no_mouth:
        say("[running VERBALISED-INFORMED on the mouth...]")
        sources["VERBALISED-INF"] = bl2.verbalised_informed(rows, _env.SEED_ASSIGN)

    # ---------- STRICT-scored AUROC2: overall + answered-only
    order = ["GATE(1-u)", "GATE(b)", "GATE(b/(b+d))", "ORACLE", "ORACLE+cos",
             "FOIL-v2"] + (["VERBALISED-INF"] if "VERBALISED-INF" in sources else [])
    boot = paired_bootstrap({k: sources[k] for k in order}, strict,
                            B=2000, seed=_env.SEED_BOOT)
    say("## AUROC2 (STRICT scoring) — overall and restricted to answered items")
    say("")
    say("| source | overall AUROC2 | 95% CI | answered-only AUROC2 |")
    say("|---|---|---|---|")
    ac, as_ = strict[answered], None
    for k in order:
        lo, hi = boot["ci"][k]
        v = sources[k][answered]
        aonly = auroc2(v, strict[answered])
        say(f"| {k} | {boot['point'][k]:.4f} | ({lo:.4f}, {hi:.4f}) | "
            f"{aonly:.4f} |")
    say("")
    say(f"answered-only n={int(answered.sum())} "
        f"(correct={int(strict[answered].sum())}, "
        f"errors={int((~strict[answered]).sum())}) — the error-ranking test")
    say("")

    # ---------- THE number: GATE(1-u) vs ORACLE, and vs ORACLE+cos
    say("## GATE vs ORACLE (the stage's number)")
    for base in ("ORACLE", "ORACLE+cos"):
        for g in ("GATE(1-u)", "GATE(b/(b+d))", "GATE(b)"):
            d, lo, hi = sk_bootstrap_diff(sources[g], sources[base], strict,
                                          2000, _env.SEED_BOOT + 1)
            excl = "excludes 0" if (lo > 0 or hi < 0) else "CONTAINS 0"
            say(f"  {g} - {base} (overall, strict): {d:+.4f} "
                f"CI ({lo:+.4f}, {hi:+.4f}) — {excl}")
        # answered-only
        for g in ("GATE(1-u)", "GATE(b/(b+d))", "GATE(b)"):
            d, lo, hi = sk_bootstrap_diff(sources[g][answered],
                                          sources[base][answered],
                                          strict[answered], 2000,
                                          _env.SEED_BOOT + 2)
            excl = "excludes 0" if (lo > 0 or hi < 0) else "CONTAINS 0"
            say(f"  {g} - {base} (ANSWERED-ONLY, strict): {d:+.4f} "
                f"CI ({lo:+.4f}, {hi:+.4f}) — {excl}")
        say("")

    # ---------- FOIL-v2 / H2 parity on hard corpus
    gap = boot["point"]["FOIL-v2"] - boot["point"]["GATE(1-u)"]
    say("## H2 parity on a hard corpus (FOIL-v2 retrained on E5 dev)")
    say(f"  FOIL-v2 dev cross-fit AUROC2={foil_dev_auc:.4f}; eval AUROC2="
        f"{boot['point']['FOIL-v2']:.4f}; GATE(1-u) eval={boot['point']['GATE(1-u)']:.4f}")
    say(f"  FOIL-v2 - GATE(1-u) gap (strict, overall): {gap:+.4f} "
        f"(Phase C margin was 0.02)")
    say("")

    # ---------- near-synonym collision behaviour (the Lisbon/Boston defect)
    say("## Near-synonym collision behaviour (f_syn) — the audit A4 defect")
    both_ways, syn_pairs_seen = _both_ways_rate(c, rows)
    say(f"  synonym pairs where BOTH member queries route ANSWER with "
        f"DIFFERENT objects (confidently answers both ways): "
        f"{both_ways}/{syn_pairs_seen} = {both_ways / max(syn_pairs_seen,1):.3f}")
    syn_mask = fam == "f_syn"
    clean_mask = (fam == "f_id") & strict
    say(f"  GATE 1-u on f_syn items: mean={sources['GATE(1-u)'][syn_mask].mean():.4f} "
        f"(clean-ID correct mean={sources['GATE(1-u)'][clean_mask].mean():.4f}) "
        f"— u carries no ambiguity term, so collisions look confident")
    # stored-d AUC under FAIR collisions vs clean ID (Phase C got 1.00 on
    # byte-identical keys; here keys differ by a near-synonym relation)
    m_l2 = np.array([r["m_l2"] for r in rows])
    p_sto = 1.0 - sigmoid((m_l2 - C_L2) / S_L2)
    if syn_mask.any() and clean_mask.any():
        lab = np.concatenate([np.ones(syn_mask.sum()), np.zeros(clean_mask.sum())])
        sco = np.concatenate([p_sto[syn_mask], p_sto[clean_mask]])
        say(f"  stored-d AUC (f_syn collisions vs clean-ID): {auroc2(sco, lab):.4f} "
            f"(Phase C on byte-identical keys: 1.0000)")
        say(f"  f_syn m_l2: min={m_l2[syn_mask].min():.4f} "
            f"max={m_l2[syn_mask].max():.4f} mean={m_l2[syn_mask].mean():.4f} "
            f"(byte-identical collisions would be exactly 0)")
    say("")

    # ---------- per-family strict outcomes
    say("## Per-family strict outcomes")
    say("| family | n | answered | ans_err | strict_acc | mean 1-u | mean ORACLE |")
    say("|---|---|---|---|---|---|---|")
    for f in sorted(set(fam)):
        m = fam == f
        am = m & answered
        say(f"| {f} | {int(m.sum())} | {int(am.sum())} | "
            f"{int((am & ~strict).sum())} | {strict[m].mean():.3f} | "
            f"{sources['GATE(1-u)'][m].mean():.3f} | {member[m].mean():.3f} |")
    say("")

    # ---------- Phase C continuity: either-object scoring
    boot_e = paired_bootstrap({"GATE(1-u)": sources["GATE(1-u)"],
                               "ORACLE": member}, either, B=2000,
                              seed=_env.SEED_BOOT + 5)
    say("## Phase C continuity (either-object scoring)")
    say(f"  GATE(1-u) either-object AUROC2={boot_e['point']['GATE(1-u)']:.4f} "
        f"(Phase C headline was 0.979)")
    say(f"  strict-scoring GATE(1-u)={boot['point']['GATE(1-u)']:.4f} — "
        f"the delta to the Phase C framing")
    say("")

    # ---------- descriptive extras
    metas = meta_d_prime(sources["GATE(1-u)"], strict, seed=_env.SEED_ASSIGN + 40000)
    say("## Descriptive")
    say(f"  meta-d' (strict): " + (f"d'={metas['d_prime']:.3f} "
        f"meta-d'={metas['meta_d']:.3f} M={metas['m_ratio']:.3f}"
        if metas.get("eligible") else f"excluded ({metas.get('reason')})"))
    say(f"  ECE GATE(1-u) strict={ece(sources['GATE(1-u)'], strict):.4f}")
    say("")

    # ---------- leak candidate outputs across ALL surfaces (judge not run)
    n_leak = _emit_leak_candidates(c, rows, LEAK_OUTPUTS,
                                   with_mouth=not args.no_mouth)
    say("## Leak (candidate outputs for leak_v3 external judge)")
    say(f"  wrote {n_leak} candidate outputs across surfaces "
        f"(answer / deliberate-referential / deliberate-stored / abstain / "
        f"social lead-in) to {os.path.basename(LEAK_OUTPUTS)}")
    say(f"  judge pass NOT run (needs registrant API-key decision): "
        f"`python e5/leak_v3.py --pass e5/{os.path.basename(LEAK_OUTPUTS)}` "
        f"after `--characterise`.")

    with open(REPORT, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"\n[e51] wrote {REPORT}")


# ---- helpers that need the corpus object -----------------------------------

def _collect_rows(c):
    """Re-run the frozen loop over an already-built corpus to get rows only."""
    mem = c.memory
    rows = []
    for it in c.items:
        q = mem.query(it.subj_term, it.rel)
        subj = mem.ent.resolve(it.subj_term, top=1)[0][0]
        rel = mem.rel.resolve(it.rel, top=1)[0][0]
        a, m_l1, top1 = mem._unbind(subj, rel)
        strict, either = score_item(it, top1)
        rows.append({"it": it, "family": it.family, "op": q.op,
                     "action": q.action, "tag": q.tag, "record": q.record,
                     "candidates": q.candidates, "subj": subj, "rel": rel,
                     "answer": top1, "a": a, "m_l1": m_l1, "m_l2": q.m_l2,
                     "m_ref": q.m_ref, "strict": strict, "either": either})
    return rows


def _both_ways_rate(c, rows):
    """Count synonym pairs where both member queries route ANSWER and return
    different objects — the Lisbon/Boston defect."""
    by_key = {}
    for r in rows:
        it = r["it"]
        if it.family != "f_syn":
            continue
        # pair identity = frozenset of the two relations + subject
        pair = it.meta.get("pair")
        key = (it.subj_term if it.kind == "syn_true" else it.subj_term, pair)
        by_key.setdefault((r["subj"], frozenset(pair)), []).append(r)
    both, seen = 0, 0
    for k, members in by_key.items():
        if len(members) != 2:
            continue
        seen += 1
        if all(m["action"] == "answer" for m in members) and \
                members[0]["answer"] != members[1]["answer"]:
            both += 1
    return both, seen


def _emit_leak_candidates(c, rows, path, with_mouth):
    """Generate outputs across all fact-bearing surfaces, ready for the
    leak_v3 judge. facts = the full active record set (triples)."""
    mem = c.memory
    facts = [list(m["triple"]) for i, m in enumerate(mem.store.meta)
             if mem.store.active[i] and m]
    out = []
    idc = 0
    for r in rows:
        it = r["it"]
        surface = None
        if r["action"] == "answer" and r["record"] is not None:
            body = render(r["record"])
            surface = "answer"
        elif r["action"] == "deliberate" and r["candidates"]:
            body = deliberate_text(r["tag"], r["candidates"])
            surface = f"deliberate-{r['tag']}"
        else:
            body = ABSTAIN_TEXT
            surface = "abstain"
        # half of them carry a verified social lead-in (the least-templated
        # emitted surface)
        if with_mouth and idc % 2 == 0:
            lead = verify_leadin(gen_leadin(body, llm_seed=_env.SEED_ASSIGN + 20000 + idc))
            output = (lead + " " + body).strip()
            if lead:
                surface += "+leadin"
        else:
            output = body
        out.append({"id": idc, "surface": surface, "output": output,
                    "allowed_bodies": [body], "facts": facts})
        idc += 1
    with open(path, "w") as f:
        for o in out:
            f.write(json.dumps(o) + "\n")
    return len(out)


if __name__ == "__main__":
    main()
