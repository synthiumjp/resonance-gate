"""A/B the two extraction-artifact fixes (entry 187), with the null.

Arms, all off the SAME cached extraction so nothing about what was extracted
changes -- only how it is rendered and when it is emitted:
    base       round-5 behaviour
    no-tier    RG_ARTIFACT_NO_TIER=1   drop the "(provisional)" hedge
    once       RG_EMIT_ONCE=1          emit a fact on first appearance only
    both

Scored with the cheap containment proxy entry 162 used to justify the
proposition change before paying for a judged run: what fraction of gold memory
points is covered by some emitted string. Judged extraction F1 is ~5,500 calls
per arm, so it is spent only if the proxy moves.

THE NULL IS THE POINT. Coverage is a containment metric, and entries 151-153
retracted three findings that were token soup passing a containment test. Each
arm is therefore also scored against SHUFFLED gold -- the same measurement with
each session's gold replaced by another session's. A real gain must beat its own
null by more than the baseline beats its null.
"""
import argparse
import json
import os
import re
import sys

os.environ.setdefault("RG_EXTRACT_V5", "1")
EVAL = os.path.expanduser("~/rg_private/halumem/official/HaluMem/eval")
sys.path.insert(0, EVAL)
sys.path.insert(0, "/home/jp/rg/experiments/p2")

STOP = set("the a an is are was were of to in on at for and or with his her "
           "their its it he she they as by from that this what which who".split())


def toks(s):
    return {w for w in re.findall(r"[a-z0-9]+", str(s).lower())
            if w not in STOP and len(w) > 2}


def covered(gold_txt, emitted_tok, thresh=0.5):
    """Is this gold memory point covered by any single emitted string?

    Per-string rather than against the union: entry 151/152 showed that pooling
    all emissions and testing containment lets unrelated fragments assemble a
    match. One gold point must be carried by one emitted memory."""
    g = toks(gold_txt)
    if not g:
        return False
    return any(len(g & e) / len(g) >= thresh for e in emitted_tok)


def run_arm(users, data, cache_tmpl, no_tier, emit_once):
    import importlib
    for k, v in (("RG_ARTIFACT_NO_TIER", no_tier), ("RG_EMIT_ONCE", emit_once)):
        os.environ[k] = "1" if v else "0"
    import eval_rgp2 as E
    importlib.reload(E)

    per_session = []          # (gold_texts, emitted_strings)
    for ui in users:
        cache = os.path.expanduser(cache_tmpl.format(i=ui))
        if not os.path.exists(cache):
            print(f"  user {ui}: no cache, skipped")
            continue
        sessions = data[ui]["sessions"]
        prev_state = {}
        for k, s in enumerate(sessions):
            if s.get("is_generated_qa_session") or "memory_points" not in s:
                continue
            mem, _ = E.RG.ingest_user({"sessions": sessions[:k + 1]}, cache,
                                      min_mentions=2)
            cur = list(mem.g.nodes.items()) + list(mem.g.provisional.items())
            import propositions as PR
            owner = PR.owner_name([nd for _, nd in cur])
            if emit_once:
                new = [E._fact_str(nd, owner=owner) for nid, nd in cur
                       if nid not in prev_state]
            else:
                new = [E._fact_str(nd, owner=owner) for nid, nd in cur
                       if prev_state.get(nid) != nd["tier"]]
            prev_state = {nid: nd["tier"] for nid, nd in cur}
            gold = [m.get("memory_content", "") for m in s["memory_points"]
                    if isinstance(m, dict)]
            per_session.append((gold, new))
    return per_session


def score(per_session, shuffle=False):
    """Returns (recall, precision, f1, n_gold, n_emit).

    Recall alone cannot show fix 2's benefit: dropping emissions that match no
    gold leaves recall flat and raises PRECISION, which is the half of F1 the
    1.66x over-extraction was capping."""
    n_gold = n_cov = n_emit = n_useful = 0
    m = len(per_session)
    for i, (gold, emitted) in enumerate(per_session):
        # Shuffled null: this session's gold judged against ANOTHER session's
        # emissions. Offset by half the corpus so no session sees its own.
        src = per_session[(i + m // 2) % m][1] if shuffle else emitted
        et = [toks(e) for e in src]
        gt = [toks(g) for g in gold]
        n_emit += len(emitted)
        for g in gold:
            n_gold += 1
            if covered(g, et):
                n_cov += 1
        # precision: does this emitted memory carry any gold point?
        for e in emitted:
            te = toks(e)
            if any(g and len(g & te) / len(g) >= 0.5 for g in gt):
                n_useful += 1
    rec = n_cov / max(n_gold, 1)
    prec = n_useful / max(n_emit, 1)
    f1 = 2 * rec * prec / max(rec + prec, 1e-9)
    return rec, prec, f1, n_gold, n_emit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", default="10,11,12")
    ap.add_argument("--cache",
                    default="~/rg_private/halumem/dev/cache_u{i}_v5_14b.jsonl")
    args = ap.parse_args()

    import eval_rgp2 as E
    data = list(E.iter_jsonl(E.DEFAULT_DATA_PATH))
    users = [int(x) for x in args.users.split(",")]

    print(f"{'arm':>10} {'recall':>8} {'precision':>9} {'F1':>6} "
          f"{'nullF1':>7} {'gain':>11} {'emitted':>7} {'ratio':>6}")
    base_gain = None
    for name, nt, eo in (("base", False, False), ("no-tier", True, False),
                         ("once", False, True), ("both", True, True)):
        ps = run_arm(users, data, args.cache, nt, eo)
        cov, prec, f1, ng, ne = score(ps)
        nul, nprec, nf1, _, _ = score(ps, shuffle=True)
        gain = f1 - nf1
        if base_gain is None:
            base_gain = gain
        flag = ""
        if name != "base":
            flag = "  BEATS BASE" if gain > base_gain else "  no"
        print(f"{name:>10} {100*cov:7.2f}% {100*prec:8.2f}% {100*f1:6.2f}% "
              f"{100*nf1:7.2f}% {100*gain:9.2f}pt {ne:7} {ne/max(ng,1):6.2f}x{flag}")


if __name__ == "__main__":
    main()
