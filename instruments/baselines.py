"""E4 confidence baselines: five sources per item, all attached to THE SAME
forced RG answer so every comparison is within-item.

  GATE       — endogenous: primary scalar = b; secondaries b/(b+d) and 1-u
               are logged for the dev-time choice (recorded at the freeze).
  VERBALISED — the mouth states confidence in the rendered answer; frozen
               elicitation prompt below; parsed numerically.
  PROBE      — the trained foil. docs/ contains no probe-to-logit method doc
               (checked 2026-07-19), so this is a MINIMAL ADAPTATION, fully
               logged: llama.cpp exposes token logits, not residual streams,
               so the probe is a seeded logistic regression over answer-token
               logit features (mean/min logprob, mean entropy, mean top-2
               margin, length) at the report position, trained on DEV
               correctness labels only. Reconcile with the documented method
               if it lands before the freeze.
  JUDGE      — LLM-judge rating with a fixed rubric. judge == mouth
               (disclosed; offline by design).
  NULL       — shuffled-resolution control: gate scalars permuted within
               accuracy strata, seeded.
"""

import numpy as np

VERBALISE_PROMPT = (  # frozen artifact — E4 elicitation prompt v1
    "You are a memory assistant reviewing one of your own answers.\n"
    "Question topic: {subj} / {rel}.\n"
    "Your answer was: \"{answer}\"\n"
    "How confident are you that this answer is correct? Reply with ONLY an "
    "integer from 0 to 100."
)

JUDGE_PROMPT = (  # frozen artifact — E4 judge rubric v1 (judge == mouth)
    "You are grading an answer from a personal-memory assistant.\n"
    "Rubric: 100 = certainly correct given a reliable memory store; 50 = "
    "coin-flip; 0 = certainly wrong or unsupported.\n"
    "Question topic: {subj} / {rel}.\n"
    "Answer given: \"{answer}\"\n"
    "Reply with ONLY an integer from 0 to 100."
)


def gate_scalars(op):
    """(primary, alternatives) from one Opinion2."""
    b, d, u = float(op.b), float(op.d), float(op.u)
    return {"gate_b": b,
            "gate_b_over_bd": b / (b + d) if (b + d) > 1e-12 else 0.5,
            "gate_1mu": 1.0 - u}


def _parse_int(text, lo=0, hi=100):
    import re
    m = re.search(r"\b(\d{1,3})\b", text or "")
    if not m:
        return None
    v = int(m.group(1))
    return min(max(v, lo), hi)


def verbalised(subj, rel, answer, seed=None):
    from llm import generate
    out = generate("/no_think You answer with a single integer only.",
                   VERBALISE_PROMPT.format(subj=subj, rel=rel, answer=answer),
                   max_tokens=8, temperature=0.0, seed=seed)
    v = _parse_int(out)
    return (v if v is not None else 50) / 100.0


def judge(subj, rel, answer, seed=None):
    from llm import generate
    out = generate("/no_think You answer with a single integer only.",
                   JUDGE_PROMPT.format(subj=subj, rel=rel, answer=answer),
                   max_tokens=8, temperature=0.0, seed=seed)
    v = _parse_int(out)
    return (v if v is not None else 50) / 100.0


# ------------------------------------------------------------------ PROBE

_probe_llm = None


def _get_probe_llm():
    """Separate context with logits_all so answer-token logits are readable."""
    global _probe_llm
    if _probe_llm is None:
        import os
        from llama_cpp import Llama
        import llm as mouth_llm
        _probe_llm = Llama(mouth_llm.MODEL_PATH, n_ctx=512, logits_all=True,
                           n_threads=os.cpu_count(), seed=42, verbose=False,
                           n_gpu_layers=0 if os.environ.get("RG_CPU") == "1" else -1)
    return _probe_llm


def probe_features(subj, rel, answer):
    """Answer-token logit features at the report position."""
    llm = _get_probe_llm()
    prefix = f"Q: {subj} — {rel}?\nA:"
    full = prefix + " " + answer
    ptoks = llm.tokenize(prefix.encode(), add_bos=True)
    ftoks = llm.tokenize(full.encode(), add_bos=True)
    llm.reset()
    llm.eval(ftoks)
    logits = np.array(llm.scores[: len(ftoks)], dtype=np.float64)
    feats, n_ans = [], 0
    lps, ents, margins = [], [], []
    for pos in range(len(ptoks), len(ftoks)):
        row = logits[pos - 1]
        row = row - row.max()
        p = np.exp(row)
        p /= p.sum()
        tok = ftoks[pos]
        lps.append(np.log(max(p[tok], 1e-12)))
        ents.append(float(-(p * np.log(np.maximum(p, 1e-12))).sum()))
        top2 = np.partition(row, -2)[-2:]
        margins.append(float(top2[1] - top2[0]))
        n_ans += 1
    if n_ans == 0:
        return np.zeros(5)
    return np.array([np.mean(lps), np.min(lps), np.mean(ents),
                     np.mean(margins), float(n_ans)])


class LogisticProbe:
    """Seeded numpy logistic regression (the trained foil's head)."""

    def __init__(self, seed=31):
        self.seed = seed
        self.w = None
        self.mu = None
        self.sd = None

    def fit(self, X, y, epochs=3000, lr=0.05, l2=1e-3):
        rng = np.random.default_rng(self.seed)
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-9
        Xn = np.hstack([(X - self.mu) / self.sd, np.ones((len(X), 1))])
        w = rng.normal(0, 0.01, Xn.shape[1])
        for _ in range(epochs):
            p = 1 / (1 + np.exp(-Xn @ w))
            g = Xn.T @ (p - y) / len(y) + l2 * w
            w -= lr * g
        self.w = w
        return self

    def predict(self, X):
        X = np.asarray(X, dtype=np.float64)
        Xn = np.hstack([(X - self.mu) / self.sd, np.ones((len(X), 1))])
        return 1 / (1 + np.exp(-Xn @ self.w))


def null_shuffle(gate_conf, correct, seed=97):
    """Shuffled-resolution control per the plan wording: permute gate scalars
    WITHIN accuracy strata (seeded). MEASURED FINDING (E4, entry 10): this
    null is AUROC2-INVARIANT by construction — rank statistics depend only on
    the class-conditional distributions, which stratified permutation
    preserves exactly. It nulls item-linkage statistics (regression, ECE
    pairing), not AUROC2. Use null_shuffle_full for the AUROC2 null; the
    registered null definition is a freeze-time decision."""
    rng = np.random.default_rng(seed)
    gate_conf = np.asarray(gate_conf, dtype=np.float64).copy()
    correct = np.asarray(correct, dtype=bool)
    for stratum in (correct, ~correct):
        idx = np.where(stratum)[0]
        gate_conf[idx] = gate_conf[idx[rng.permutation(len(idx))]]
    return gate_conf


def null_shuffle_full(gate_conf, seed=98):
    """Unstratified permutation: destroys the confidence-correctness linkage
    entirely — the effective AUROC2 null (expected 0.5)."""
    rng = np.random.default_rng(seed)
    gate_conf = np.asarray(gate_conf, dtype=np.float64)
    return gate_conf[rng.permutation(len(gate_conf))]
