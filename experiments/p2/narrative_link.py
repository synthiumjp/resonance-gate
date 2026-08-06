"""Write-time associative links, so retrieval can reach what it cannot match.

Entry 196 (S4). Our retrieval is entirely lexical -- BM25 plus a bi-encoder plus
a cross-encoder, all scoring a fact against the QUERY. A fact that answers a
multi-hop question but shares no tokens with the query is unreachable in
principle: it is findable only THROUGH another fact. That is the mechanism
behind Multi-hop Inference at 17.6% correct and Generalization at 9.5% (entry
179), the two categories the gate currently declines rather than answers.

The PNAS active-linking result is the direct analogue: narrative-based encoding
selectively enhanced memory for ASSOCIATIONS and supported inference across
INDIRECTLY RELATED items, and the advantage is "not general" -- it appears only
where retrieval demands inference. That is a falsifiable prediction here:
linking should move the inference categories and do nothing for lookups. If it
lifts Basic Fact Recall too, something is wrong with the measurement.

Links are built at WRITE time and cost no model call:

  ENTITY   two facts naming the same proper noun. The strongest link, because
           it is what a multi-hop question actually traverses ("who does X work
           with" -> a person -> that person's attributes).
  SESSION  two facts first recorded in the same session. Weak on its own -- a
           busy session links everything to everything -- so it is capped.

Deliberately NOT included: a "same turn" link, which would be the truest
co-mention signal. The store records receipts at SESSION granularity only
(halumem_run stores (date, "s{si}")), so turn-level co-occurrence is not
available without changing the store format. Recorded here rather than silently
approximated, because session co-occurrence is a much weaker proxy and any
result should be read with that in mind.
"""
import re
from collections import defaultdict

# Capitalised multiword names, and the CamelCase surnames HaluMem uses
# ("AndersonElizabeth"). Lowercased store values lose capitalisation, so the
# value text is matched case-insensitively against a known-entity vocabulary
# built from the store itself rather than by capitalisation alone.
_CAMEL = re.compile(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b")
_PROPER = re.compile(r"\b[A-Z][a-z]{2,}\b")
_STOP = {"the", "and", "for", "with", "her", "his", "their", "user", "self"}


def entity_vocab(facts):
    """Named entities the store knows about.

    The store LOWERCASES every value (halumem_run: value.strip().lower()), so
    capitalisation-based entity detection cannot work here -- the first version
    of this found 17 entities and linked only 45 of 333 facts, because the only
    surviving case information was in subject prefixes. Entities are therefore
    collected structurally instead:
      * subject prefixes ("alex johnson:employer" -> "alex johnson")
      * values of naming/relationship attributes, which is where person names
        live once case is gone
    then matched case-insensitively."""
    NAMEY = ("name", "friend", "colleague", "partner", "spouse", "child",
             "parent", "mentor", "boss", "manager", "sibling", "relative",
             "employer", "company", "team", "project")
    vocab = set()
    for f in facts:
        attr = str(f.get("attr", ""))
        if ":" in attr:
            subj = attr.split(":")[0].strip().lower()
            if subj and subj not in _STOP and len(subj) > 2:
                vocab.add(subj)
        bare = attr.split(":")[-1].lower()
        if any(n in bare for n in NAMEY):
            for part in re.split(r",| and ", str(f.get("value", ""))):
                w = part.strip().lower()
                if 2 < len(w) < 40 and w not in _STOP:
                    vocab.add(w)
        # CamelCase survives lowercasing as a single long token
        for m in _CAMEL.findall(str(f.get("value", ""))):
            vocab.add(m.lower())
    return vocab


def fact_entities(f, vocab):
    """Which known entities this fact mentions."""
    text = f"{f.get('attr','')} {f.get('value','')}".lower()
    toks = set(re.findall(r"[a-z0-9]+", text))
    hit = {v for v in vocab if v in toks}
    # multiword / camel entities will not survive tokenisation; substring-match
    # only those, which is cheap because the vocab is small
    for v in vocab:
        if len(v) > 6 and v not in hit and v in text:
            hit.add(v)
    return hit


def build_links(facts, max_session_degree=12):
    """fact index -> set of linked fact indices.

    max_session_degree caps SESSION links: a session with 40 facts would
    otherwise contribute 780 edges and drown the entity signal, turning
    expansion into "return the whole session"."""
    vocab = entity_vocab(facts)
    ents = [fact_entities(f, vocab) for f in facts]

    by_ent = defaultdict(list)
    for i, e in enumerate(ents):
        for x in e:
            by_ent[x].append(i)

    links = defaultdict(set)
    for x, idxs in by_ent.items():
        if len(idxs) > 60:          # an entity naming most of the store is
            continue                # the profile owner: it links nothing useful
        for a in idxs:
            for b in idxs:
                if a != b:
                    links[a].add(b)

    by_sess = defaultdict(list)
    for i, f in enumerate(facts):
        for rec in (f.get("receipts") or f.get("recs") or []):
            s = rec[1] if isinstance(rec, (list, tuple)) and len(rec) > 1 else None
            if s:
                by_sess[s].append(i)
    for s, idxs in by_sess.items():
        if len(idxs) > max_session_degree:
            continue
        for a in idxs:
            for b in idxs:
                if a != b:
                    links[a].add(b)
    return links, ents


def expand(seed_idx, links, budget=10):
    """One hop out from the retrieved set, nearest-first by link count.

    Facts linked from SEVERAL seeds are returned first: being reachable from
    more of what the query already matched is the only evidence available at
    this stage that a link is relevant rather than incidental."""
    seeds = set(seed_idx)
    counts = defaultdict(int)
    for s in seeds:
        for n in links.get(s, ()):
            if n not in seeds:
                counts[n] += 1
    ranked = sorted(counts, key=lambda i: (-counts[i], i))
    return ranked[:budget]
