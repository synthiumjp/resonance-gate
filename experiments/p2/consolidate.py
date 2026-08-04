"""Consolidation layer (entry 138/139): the second memory system.

Three mechanisms, one per source paper:

  write_gate()   -- Spens & Burgess 2024: prediction error gates encoding.
                    A candidate fact already predicted by the store (high
                    semantic similarity within its attr family) contributes a
                    RECEIPT to the existing node instead of a new node.
                    Restatement sediment stops accumulating; the store's size
                    tracks what is NEW, not what was said.

  consolidate()  -- Maguire 2014: consolidation is REORGANIZATION. An offline
                    pass abstracts clusters of episodes into GIST nodes. Every
                    gist cites >= MIN_SOURCES dated episodes and is stored in
                    its own tier; episodes are never deleted, so a gist can be
                    audited or re-derived at any time. This is what makes
                    generative abstraction safe here and unsafe elsewhere
                    (Spens & Burgess's own results: gist recall DISTORTS --
                    DRM lures, boundary extension, prototype bias).

  reconsolidate()-- Helfer & Shultz: reactivation returns a consolidated trace
                    to a labile state. New evidence contradicting a gist marks
                    it stale; it is re-derived from its episodes plus the new
                    evidence, then re-stabilized.

The abstraction step is the ONLY part that calls a model, it runs offline
(idle-time), and it never touches the answer path.
"""
import json
from collections import defaultdict

MIN_SOURCES = 2          # a gist must cite at least this many episodes
GATE_THR = 0.90          # cosine within attr family = "already predicted"

GIST_PROMPT = (
    "Below are dated facts recorded about one person, all describing the same "
    "aspect of their life.\n\nFACTS:\n{facts}\n\n"
    "Write ONE sentence (max 25 words) stating what these facts collectively "
    "show about this person -- the durable pattern, not a list. Use only what "
    "the facts state; do not add detail. If they show no coherent pattern, "
    "reply exactly: NONE.")


def _emb(texts, model=None):
    from sentence_transformers import SentenceTransformer
    global _BI
    try:
        _BI
    except NameError:
        _BI = None
    if _BI is None:
        _BI = model or SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
    return _BI.encode(texts, batch_size=256, show_progress_bar=False,
                      normalize_embeddings=True)


def write_gate(facts, thr=GATE_THR):
    """Prediction-error gate over a fact list (node dicts).

    Returns (kept, absorbed): kept is the list of surviving node dicts with
    n_mentions/convs merged from their restatements; absorbed maps
    kept-index -> [absorbed node dicts] (kept for audit, never discarded by
    this function -- the caller decides whether to archive them)."""
    if not facts:
        return [], {}
    texts = [f"{d['attr']}: {d['value']}" for d in facts]
    emb = _emb(texts)
    order = sorted(range(len(facts)), key=lambda j: -facts[j].get("n_mentions", 1))
    by_attr = defaultdict(list)
    keep_idx, absorbed = [], defaultdict(list)
    for j in order:
        a = facts[j]["attr"]
        hit = next((k for k in by_attr[a] if float(emb[j] @ emb[k]) >= thr), None)
        if hit is None:
            keep_idx.append(j)
            by_attr[a].append(j)
        else:
            absorbed[hit].append(j)
    kept = []
    for j in keep_idx:
        nd = dict(facts[j])
        nd["convs"] = dict(nd.get("convs", {}))
        variants = []
        for k in absorbed.get(j, []):
            nd["n_mentions"] = nd.get("n_mentions", 1) + facts[k].get("n_mentions", 1)
            nd["convs"].update(facts[k].get("convs", {}))
            variants.append(facts[k]["value"])
        if variants:
            nd["restatements"] = variants        # audit trail, not asserted
        kept.append(nd)
    return kept, {i: [facts[k] for k in absorbed.get(j, [])]
                  for i, j in enumerate(keep_idx) if absorbed.get(j)}


MAX_SOURCES = 12         # a gist over more episodes than this is an average,
                         # not a pattern (measured: single-linkage produced
                         # 189-source "motivation" blobs -- unusable mush)


def episode_clusters(facts, min_size=MIN_SOURCES, thr=0.62, max_size=MAX_SOURCES):
    """Group same-attr episodes into semantic clusters eligible for a gist.

    COMPLETE linkage, not single: every member must be within `thr` of every
    other, so clusters cannot chain A->B->C into one blob (the snowballing
    entry 95 fixed for token clustering, recurring here semantically). Large
    attr families therefore yield SEVERAL specific patterns instead of one
    generic average -- which is the point: Spens & Burgess's latent space has
    structure; a single mean does not."""
    from sklearn.cluster import AgglomerativeClustering
    by_attr = defaultdict(list)
    for i, d in enumerate(facts):
        by_attr[d["attr"]].append(i)
    texts = [f"{d['attr']}: {d['value']}" for d in facts]
    emb = _emb(texts)
    out = []
    for attr, idxs in by_attr.items():
        if len(idxs) < min_size:
            continue
        X = emb[idxs]
        model = AgglomerativeClustering(
            n_clusters=None, distance_threshold=1.0 - thr,
            metric="cosine", linkage="complete").fit(X)
        groups = defaultdict(list)
        for pos, lab in enumerate(model.labels_):
            groups[lab].append(idxs[pos])
        for g in groups.values():
            if len(g) < min_size:
                continue
            g = sorted(g, key=lambda i: -facts[i].get("n_mentions", 1))[:max_size]
            out.append((attr, [facts[i] for i in g]))
    return out


def _dates(nd):
    return sorted(set(nd.get("convs", {}).values()))


def make_gist(attr, episodes, llm):
    """One gist node from an episode cluster. Returns None unless the model
    produces a pattern AND >= MIN_SOURCES episodes back it."""
    if len(episodes) < MIN_SOURCES:
        return None
    listing = "\n".join(f"- ({', '.join(_dates(e)) or 'undated'}) {e['value']}"
                        for e in episodes)
    try:
        text = llm(GIST_PROMPT.format(facts=listing)).strip()
    except Exception:
        return None
    if not text or text.upper().startswith("NONE"):
        return None
    convs = {}
    for e in episodes:
        convs.update(e.get("convs", {}))
    return {
        "id": f"gist:{attr}={text[:40]}",
        "attr": attr,
        "value": text,
        "tier": "gist",
        "n_mentions": sum(e.get("n_mentions", 1) for e in episodes),
        "convs": convs,
        "sources": [e["id"] for e in episodes],       # receipts: auditable
        "source_values": [e["value"] for e in episodes],
        "stale": False,
    }


def consolidate(facts, llm, min_size=MIN_SOURCES):
    """Offline pass: episodes -> gist nodes (episodes are NOT removed)."""
    gists = []
    for attr, cluster in episode_clusters(facts, min_size=min_size):
        g = make_gist(attr, cluster, llm)
        if g:
            gists.append(g)
    return gists


RESTATE_THR = 0.75       # >= this to the gist = already predicted by it


def mark_labile(gists, new_fact, thr=RESTATE_THR):
    """Helfer & Shultz + Spens & Burgess, unified: REACTIVATION (a new fact in
    the gist's slot) destabilizes the gist UNLESS the gist already predicts it.
    Prediction error, not contradiction detection -- deliberately: embeddings
    rate antonyms as similar (measured on bge-small: gist vs contradiction
    0.619, gist vs restatement 0.796), so "does this contradict?" is not
    decidable here, while "is this already covered?" is. Anything not covered
    -- novel OR contradictory -- returns the gist to a labile state, and the
    re-derivation decides what the pattern now is."""
    if not gists:
        return []
    texts = [g["value"] for g in gists] + [new_fact["value"]]
    emb = _emb(texts)
    q = emb[-1]
    touched = []
    for i, g in enumerate(gists):
        if g["attr"] != new_fact["attr"]:
            continue
        sim = float(emb[i] @ q)
        if sim < thr:                 # same slot, not predicted by the gist
            g["stale"] = True
            touched.append(g)
    return touched


def reconsolidate(gist, episodes, new_facts, llm):
    """Re-derive a labile gist from its episodes plus the new evidence."""
    g = make_gist(gist["attr"], list(episodes) + list(new_facts), llm)
    if g:
        g["supersedes"] = gist["id"]
    return g


def format_gist(g):
    """Context line: labelled as a pattern, with its receipt count -- never
    presented as a stored fact. Dates are PARSED before sorting (string sort
    puts 'Sep 04, 2025' after 'Aug 21, 2031' -- the entry-114 bug class)."""
    from timeline import _parse_date
    dates = sorted(set(g.get("convs", {}).values()), key=_parse_date)
    span = f"{dates[0]}..{dates[-1]}" if len(dates) > 1 else (dates[0] if dates else "?")
    return (f"[PATTERN from {len(g['sources'])} memories, {span}] "
            f"{g['attr']}: {g['value']}")


if __name__ == "__main__":       # tiny self-check, no model needed
    facts = [
        {"id": "a", "attr": "preference", "value": "black coffee for alertness",
         "n_mentions": 2, "convs": {"s1": "Jan 05, 2025"}},
        {"id": "b", "attr": "preference", "value": "black coffee for focus",
         "n_mentions": 1, "convs": {"s2": "Feb 09, 2025"}},
        {"id": "c", "attr": "preference", "value": "hiking on weekends",
         "n_mentions": 1, "convs": {"s3": "Mar 02, 2025"}},
    ]
    kept, absorbed = write_gate(facts, thr=0.90)
    print(json.dumps([{k: v for k, v in n.items() if k != "convs"}
                      for n in kept], indent=1)[:400])


# ---- validated contradiction primitive (entry 154) --------------------------
# NLI separates a genuine value substitution from a rewording, which neither
# token overlap nor embedding cosine can do (measured: contradiction 1.00 on
# every true substitution, 0.00 on every rewording; cosine gave 0.757 vs 0.769
# -- rewordings scored HIGHER). 70MB, CPU, offline.
_NLI = None
SINGLE_VALUED = {"employer", "job_title", "occupation", "city", "location",
                 "income", "monthly_income", "salary", "age", "birth_date",
                 "health_condition", "relationship_status", "company", "role",
                 "title", "residence", "school", "employment_status",
                 "industry", "marital_status", "name", "email", "phone"}


def _nli():
    """Lazy-load; returns None if transformers is unavailable so callers can
    fall back to the lexical path rather than failing."""
    global _NLI
    if _NLI is None:
        try:
            import warnings
            warnings.filterwarnings("ignore")
            from transformers import pipeline
            _NLI = pipeline("text-classification",
                            model="cross-encoder/nli-deberta-v3-xsmall",
                            device=-1, top_k=None)
        except Exception:
            _NLI = False
    return _NLI or None


def contradicts(attr, value_a, value_b, min_score=0.9):
    """True when two values of the same attribute cannot both hold."""
    nli = _nli()
    if nli is None:
        return None                      # caller decides (no silent guessing)
    label = attr.replace("_", " ")
    try:
        out = nli({"text": f"Their {label} is {value_a}.",
                   "text_pair": f"Their {label} is {value_b}."})
    except Exception:
        return None
    c = next((d["score"] for d in out
              if d["label"].lower().startswith("contra")), 0.0)
    return c >= min_score
