"""E5.1 fair confidence sources (within-item, same design as E4 baselines.py
but a separate module; instruments/ is read-only).

  GATE            — endogenous, frozen: 1-u primary; b, b/(b+d) secondary.
  ORACLE          — zero-parameter exact-key store membership (oracle.py).
  ORACLE+cos      — membership + top-1 cosine (oracle.py).
  VERBALISED-INF  — the audit's missing channel: the mouth is TOLD what the
                    substrate resolved (the rendered record, or the honest
                    "nothing resolved" state) and rates confidence that the
                    resolved answer is the correct one. Fixed elicitation
                    prompt below, logged. This is the strongest fair
                    LLM-side comparator: it has the retrieval result the
                    Phase C verbalised baseline was denied.
  FOIL-v2         — the H2 logistic head (baselines.LogisticProbe over the
                    frozen gate features a, m_l1, m_l2, m_ref, k, N),
                    RETRAINED on an E5 dev split (disjoint seed) and
                    evaluated on the E5 eval split. Tests whether H2's
                    untrained-vs-trained parity survives a hard corpus.
"""

import numpy as np

from baselines import LogisticProbe  # frozen instrument, read-only use

FEATURES = ["a", "m_l1", "m_l2", "m_ref", "k", "N"]

VERBALISE_INFORMED_PROMPT = (  # E5.1 elicitation prompt v1 (frozen for the run)
    "You are a memory assistant checking one of your own retrievals.\n"
    "The user asked about: {subj} / {rel}.\n"
    "{resolved}\n"
    "How confident are you that this is the correct answer to the user's "
    "question? Reply with ONLY an integer from 0 to 100."
)


def gate_sources(rows):
    """1-u primary + b, b/(b+d) secondary from the frozen Opinion2."""
    b = np.array([r["op"].b for r in rows])
    d = np.array([r["op"].d for r in rows])
    u = np.array([r["op"].u for r in rows])
    bbd = np.where(b + d > 1e-12, b / (b + d), 0.5)
    return {"GATE(1-u)": 1.0 - u, "GATE(b)": b, "GATE(b/(b+d))": bbd}


def _resolved_clause(action, record):
    if action == "answer" and record is not None:
        from speak import render
        return f'Your memory returned: "{render(record)}"'
    if action == "deliberate":
        return ("Your memory found more than one matching record and could "
                "not choose between them.")
    return "Your memory returned nothing for this question."


def verbalised_informed(rows, seed0):
    """The informed mouth baseline. rows carry action + record from the
    frozen query path. Returns array on [0, 1]."""
    from llm import generate
    from baselines import _parse_int
    out = np.zeros(len(rows))
    for i, r in enumerate(rows):
        clause = _resolved_clause(r["action"], r.get("record"))
        prompt = VERBALISE_INFORMED_PROMPT.format(subj=r["subj"], rel=r["rel"],
                                                  resolved=clause)
        txt = generate("/no_think You answer with a single integer only.",
                       prompt, max_tokens=8, temperature=0.0, seed=seed0 + i)
        v = _parse_int(txt)
        out[i] = (v if v is not None else 50) / 100.0
    return out


def foil_v2(X_dev, y_dev, X_eval, train_seed):
    """Retrain the H2 head on E5 dev, predict on E5 eval. 2-fold cross-fit
    dev AUROC2 is reported by the caller; here we return the eval-split
    predictions from the full-dev-fit head plus the head itself."""
    head = LogisticProbe(seed=train_seed).fit(X_dev, y_dev)
    return head.predict(X_eval), head
