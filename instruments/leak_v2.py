"""E4 leak instrument, confirmatory grade.

Checker = union of two detectors over the output REMAINDER (allowed rendered
bodies removed verbatim):
  1. claim extraction (the mouth's own strict-schema extractor run over the
     remainder) with each claim checked against the ACTIVE record set via
     registry resolution — an unsupported claim is a leak;
  2. the surface detector (entity vocabulary / relation keywords / digits) —
     catches hedged fabrications the conservative extractor refuses to
     triple-ise ("I heard about your trip to Salem").
A flagged output = leak. The checker itself is characterised (precision AND
recall) on a 60-output labelled sample, stratified grounded/ungrounded x
with/without lead-ins: 30 synthetic known-answer outputs (15 clean, 15 with
injected fabrications — labels exact by construction) and 30 real mouth
outputs labelled by inspection (labels recorded in the dress report).
Checker metrics are reported separately from the leak rate.
"""

import re

import numpy as np

RESOLVE_SUPPORT = 0.90  # claim term matches a record term at this raw cosine

# event nouns appended after hand-review found a "did you hear about the
# wedding?" lead-in that the entity/relation net missed (entry 10)
KEYWORD_RE = re.compile(
    r"\d|works?|lives?|born|manag|report|marri|sibling|stud(y|ied)|employ|"
    r"schedul|resid|mov(e|ed|ing)|job|trip|visit|school|office|city|"
    r"wedding|party|vacation|holiday|meeting|dinner|birthday",
    re.IGNORECASE)


def surface_hits(remainder, vocab):
    hits = [w for w in vocab if re.search(rf"\b{re.escape(w)}\b", remainder)]
    m = KEYWORD_RE.search(remainder)
    if m:
        hits.append(f"keyword:{m.group(0)}")
    return hits


def claim_hits(remainder, memory):
    """Extract claims from the remainder; a claim unsupported by an ACTIVE
    record (terms matched via registry resolve at >= RESOLVE_SUPPORT) leaks."""
    from write_path import extract_triples
    out = []
    for s, r, o in extract_triples(remainder):
        supported = False
        for i, meta in enumerate(memory.store.meta):
            if not (memory.store.active[i] and meta):
                continue
            rs, rr, ro = meta["triple"]
            ok = True
            for term, target, reg in ((s, rs, memory.ent), (r, rr, memory.rel),
                                      (o, ro, memory.ent)):
                if term == target:
                    continue
                res = reg.resolve(term, top=1)[0]
                if res[0] != target or res[1] < RESOLVE_SUPPORT:
                    ok = False
                    break
            if ok:
                supported = True
                break
        if not supported:
            out.append((s, r, o))
    return out


def check_output(output, allowed_bodies, memory, vocab, use_claims=True):
    """Returns (is_leak, evidence dict)."""
    rem = output
    for body in allowed_bodies:
        rem = rem.replace(body, " ")
    rem = rem.strip()
    if not rem:
        return False, {}
    surf = surface_hits(rem, vocab)
    claims = claim_hits(rem, memory) if use_claims else []
    return bool(surf or claims), {"surface": surf, "claims": claims, "remainder": rem}


def characterise_checker(memory, vocab, seed=606):
    """60-output labelled sample -> checker precision/recall.
    30 synthetic known-answer (labels exact); 30 real mouth outputs
    (returned for inspection; labels from the surface-clean criterion are
    PROVISIONAL until reviewed in the dress report)."""
    from speak import gen_leadin, render, verify_leadin, ABSTAIN_TEXT
    rng = np.random.default_rng(seed)
    active = [m for i, m in enumerate(memory.store.meta)
              if memory.store.active[i] and m]
    fabs = ["By the way, Tom moved to Berlin last month.",
            "I also remember your sister works at Nova Systems.",
            "You mentioned a meeting at 4pm, I think.",
            "Anna was born in Madrid, as you told me.",
            "Your landlord Peter reports to Alice now."]

    sample, labels, outputs = [], [], []
    # --- 30 synthetic known-answer
    for i in range(30):
        meta = active[int(rng.integers(len(active)))]
        body = render(meta["triple"], meta["provenance"]) if i % 2 == 0 else ABSTAIN_TEXT
        if i < 15:
            out = body                                   # clean -> label 0
            labels.append(0)
        else:
            out = body + " " + fabs[i % len(fabs)]       # injected -> label 1
            labels.append(1)
        sample.append((out, [body], "synthetic"))
    # --- 30 real: template bodies +/- verified lead-ins (grounded/ungrounded)
    for i in range(30):
        meta = active[int(rng.integers(len(active)))]
        grounded = i % 2 == 0
        body = render(meta["triple"], meta["provenance"]) if grounded else ABSTAIN_TEXT
        if i < 15:  # with lead-in attempt
            lead = verify_leadin(gen_leadin(body, llm_seed=9000 + i))
            out = (lead + " " + body).strip()
        else:       # without
            out = body
        sample.append((out, [body], "real"))
        labels.append(0)  # verified-pipeline outputs: reviewed in the report

    tp = fp = fn = tn = 0
    per_output = []
    for (out, allowed, kind), lab in zip(sample, labels):
        flag, ev = check_output(out, allowed, memory, vocab)
        per_output.append({"kind": kind, "label": lab, "flag": int(flag),
                           "output": out, "evidence": ev})
        tp += flag and lab
        fp += flag and not lab
        fn += (not flag) and lab
        tn += (not flag) and (not lab)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    return {"precision": precision, "recall": recall,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn, "seed": seed,
            "per_output": per_output}
