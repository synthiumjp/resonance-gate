"""E3.1 task 4d: QUERY GENERALIZATION — do natural-language queries land on
codebook entries at all? First measurement of the assumption Parts 2-4
silently depend on. Hand-built dev set, three families:
  - partial: bare first names -> all matching person entries,
  - alias: nicknames/short forms -> the full-name entry,
  - relation: paraphrased relations -> the matching RELATIONS10 entries.
Score: top-1 / top-2 hit rate of the correct entry (any of the correct set)
in cleanup. The lambda=0 row is the baseline the whitening must not destroy;
the sweep script reuses score_generalization with each lambda's transform.
"""

import numpy as np

from map_ops import Codebook
from entities import RELATIONS10
from e31_common import encode

D = 8192

# --- the entity codebook for the dev set: targets + confusable fillers
PERSON_CODEBOOK = [
    "Tom Baker", "Tom Barker", "Tom (brother)", "Tom (colleague)",
    "Thomas Becker", "Anna Chen", "Anna Cheng", "Anna (cousin)",
    "James Fischer", "James Fisher", "Jim Evans", "Maria Garcia",
    "Maria Gonzalez", "David Hansen", "David Hanson", "Sarah Kim",
    "Sarah Klein", "Michael Chen", "Michael Meyer", "Emma Novak",
    "Emma Nguyen", "John Park", "John Patel", "Sofia Reyes", "Sofia Rios",
    "Robert Fischer", "Robert Schmidt", "Laura Silva", "Laura Sousa",
    "Daniel Kim", "Daniel Diaz", "Alice Weber", "Alice Wong",
    "Peter Yang", "Peter Zhang", "Nina Vogel", "Nina Tran",
    "Chris Wong", "Christopher Olsen", "Julia Quinn", "Julia Lopez",
    "Mark Lowe", "Mark Meier", "Elena Ito", "Elena Evans",
    "Elizabeth Carter", "Elizabeth Klein", "William Weber",
    "Katherine Novak", "Margaret Olsen", "Edward Silva", "Samuel Diaz",
    "Benjamin Lopez", "Nicholas Park", "Alexandra Reyes", "Victoria Tran",
]

# (query, [correct entries], family)
DEV_SET = [
    # partial names: bare first name -> every entry with that first name (20)
    ("Tom", ["Tom Baker", "Tom Barker", "Tom (brother)", "Tom (colleague)"], "partial"),
    ("Anna", ["Anna Chen", "Anna Cheng", "Anna (cousin)"], "partial"),
    ("James", ["James Fischer", "James Fisher"], "partial"),
    ("Maria", ["Maria Garcia", "Maria Gonzalez"], "partial"),
    ("David", ["David Hansen", "David Hanson"], "partial"),
    ("Sarah", ["Sarah Kim", "Sarah Klein"], "partial"),
    ("Michael", ["Michael Chen", "Michael Meyer"], "partial"),
    ("Emma", ["Emma Novak", "Emma Nguyen"], "partial"),
    ("John", ["John Park", "John Patel"], "partial"),
    ("Sofia", ["Sofia Reyes", "Sofia Rios"], "partial"),
    ("Robert", ["Robert Fischer", "Robert Schmidt"], "partial"),
    ("Laura", ["Laura Silva", "Laura Sousa"], "partial"),
    ("Daniel", ["Daniel Kim", "Daniel Diaz"], "partial"),
    ("Alice", ["Alice Weber", "Alice Wong"], "partial"),
    ("Peter", ["Peter Yang", "Peter Zhang"], "partial"),
    ("Nina", ["Nina Vogel", "Nina Tran"], "partial"),
    ("Julia", ["Julia Quinn", "Julia Lopez"], "partial"),
    ("Mark", ["Mark Lowe", "Mark Meier"], "partial"),
    ("Elena", ["Elena Ito", "Elena Evans"], "partial"),
    ("Elizabeth", ["Elizabeth Carter", "Elizabeth Klein"], "partial"),
    # aliases / nicknames -> full-name entry (15)
    ("Liz Carter", ["Elizabeth Carter"], "alias"),
    ("Beth Klein", ["Elizabeth Klein"], "alias"),
    ("Bob Fischer", ["Robert Fischer"], "alias"),
    ("Bobby Schmidt", ["Robert Schmidt"], "alias"),
    ("Mike Chen", ["Michael Chen"], "alias"),
    ("Tommy Baker", ["Tom Baker"], "alias"),
    ("Jimmy Evans", ["Jim Evans"], "alias"),
    ("Bill Weber", ["William Weber"], "alias"),
    ("Kate Novak", ["Katherine Novak"], "alias"),
    ("Dan Kim", ["Daniel Kim"], "alias"),
    ("Chris Olsen", ["Christopher Olsen"], "alias"),
    ("Meg Olsen", ["Margaret Olsen"], "alias"),
    ("Ed Silva", ["Edward Silva"], "alias"),
    ("Sam Diaz", ["Samuel Diaz"], "alias"),
    ("Ben Lopez", ["Benjamin Lopez"], "alias"),
    # paraphrased relations -> RELATIONS10 entries (20)
    ("has a job at", ["works at", "is employed by"], "relation"),
    ("gets paid by", ["works at", "is employed by"], "relation"),
    ("is on the payroll of", ["works at", "is employed by"], "relation"),
    ("holds a position at", ["works at", "is employed by"], "relation"),
    ("makes her home in", ["lives in", "resides in"], "relation"),
    ("is based in", ["lives in", "resides in"], "relation"),
    ("has an apartment in", ["lives in", "resides in"], "relation"),
    ("settled down in", ["lives in", "resides in"], "relation"),
    ("came into the world in", ["was born in"], "relation"),
    ("is a native of", ["was born in"], "relation"),
    ("is the boss of", ["manages"], "relation"),
    ("supervises", ["manages"], "relation"),
    ("answers to", ["reports to"], "relation"),
    ("works under", ["reports to"], "relation"),
    ("is the spouse of", ["is married to"], "relation"),
    ("is wedded to", ["is married to"], "relation"),
    ("is the brother of", ["is a sibling of"], "relation"),
    ("shares parents with", ["is a sibling of"], "relation"),
    ("got a degree from", ["studied at"], "relation"),
    ("is an alum of", ["studied at"], "relation"),
]


def score_generalization(transform=None, d=D):
    """Top-1/top-2 hit rates per family and overall for the dev set under an
    optional embedding transform (the whitening blend)."""
    books = {
        "entity": (Codebook.from_matrix(PERSON_CODEBOOK,
                                        encode(PERSON_CODEBOOK, d, transform))),
        "relation": (Codebook.from_matrix(RELATIONS10,
                                          encode(RELATIONS10, d, transform))),
    }
    queries = [q for q, _, _ in DEV_SET]
    qv = encode(queries, d, transform)
    out = {}
    for i, (q, correct, fam) in enumerate(DEV_SET):
        book = books["relation"] if fam == "relation" else books["entity"]
        top = book.cleanup(qv[i], top_k=2)
        r = out.setdefault(fam, {"n": 0, "top1": 0, "top2": 0})
        r["n"] += 1
        r["top1"] += top[0][0] in correct
        r["top2"] += (top[0][0] in correct) or (top[1][0] in correct)
    tot = {"n": sum(r["n"] for r in out.values()),
           "top1": sum(r["top1"] for r in out.values()),
           "top2": sum(r["top2"] for r in out.values())}
    out["overall"] = tot
    return {fam: {"n": r["n"], "top1": r["top1"] / r["n"], "top2": r["top2"] / r["n"]}
            for fam, r in out.items()}


def test_generalization_baseline_lambda0():
    """The lambda=0 baseline: whether NL queries land on codebook entries at
    all — measured before any whitening question (notebook entry 6)."""
    res = score_generalization(transform=None)
    print(f"\n[generalization] lambda=0 baseline, {res['overall']['n']} queries")
    for fam in ["partial", "alias", "relation", "overall"]:
        r = res[fam]
        print(f"[generalization] {fam:>8}: top1={r['top1']:.3f} top2={r['top2']:.3f} (n={r['n']})")
    # measurement sanity only — the numbers themselves go to the fork decision
    assert res["overall"]["n"] == len(DEV_SET)
    assert res["overall"]["top2"] > 0.2, "queries do not land on entries at all"
