"""A4: adversarial near-miss probes against the H3 ambiguity claims.
AUDIT PROBES ONLY — not registered results.

Part 1 (referential): the registered referential probes are bare shared
first names ("Tom") whose registry family is exactly {"Tom (brother)",
"Tom (colleague)"}. We probe with realistic underspecified/near-miss
phrasings and report m_ref, p_ref, and the controller route.

Part 2 (stored): registered collisions are two records under the IDENTICAL
(subj, rel) key string, so m_l2 = 0 exactly. We plant NEAR-duplicate keys
(confusable surnames, near-synonym relations) in a fresh scratch Memory and
report whether the stored-d signal sees them at all.

Writes audit/a4_output.txt. Frozen dirs untouched (embedding cache patched).
"""

import os

import numpy as np

import _common
_common.patch_cache()

HERE = os.path.dirname(os.path.abspath(__file__))
L = []


def say(s=""):
    print(s)
    L.append(s)


def main():
    from opinion import C_REF, S_REF, sigmoid
    from l2_ambiguity import C_L2, S_L2

    c = _common.build_registered_corpus()
    mem = c.memory

    # families actually present in the registered registry
    fams = [n for n in mem.ent.names if "(" in n][:10]
    say(f"sample qualified-family registry entries: {fams}")
    say()

    say("== Part 1: referential near-miss probes (registered corpus) ==")
    say(f"(C_REF={C_REF}, S_REF={S_REF}; registered ref probes score "
        f"p_ref via m_ref)")
    probes = [
        "Tom",                       # the registered probe style (reference)
        "Tom B.",                    # initial — points at a specific person
        "Tomm",                      # typo of bare first name
        "Anna from work",            # qualifier paraphrase (colleague)
        "my brother",                # role-only reference
        "my brother's workplace",    # indirect reference
        "the Tom who works with me", # explicit disambiguation attempt
        "James (brother)",           # exact qualified entry (should be clean)
        "Jame (brother)",            # typo inside qualified entry
        "Sarah K.",                  # first name + surname initial
        "that colleague of mine",    # bare role, no name
        "Maria",                     # bare first name, family in registry
    ]
    say(f"{'probe':32s} {'top-2 resolve':46s} {'m_ref':>7s} {'p_ref':>6s} route")
    for term in probes:
        res = mem.ent.resolve(term, top=2)
        m_ref = res[0][1] - res[1][1]
        p_ref = float(1.0 - sigmoid((m_ref - C_REF) / S_REF))
        q = mem.query(term, "works at")
        r2 = " | ".join(f"{n} {cs:.3f}" for n, cs in res)
        say(f"{term:32s} {r2:46s} {m_ref:7.3f} {p_ref:6.3f} "
            f"{q.action}/{q.tag}")
    say()

    say("== Part 2: near-duplicate STORED keys (fresh scratch memory) ==")
    say(f"(C_L2={C_L2}, S_L2={S_L2}; registered collisions have m_l2=0 "
        f"exactly — identical key strings)")
    from registry import Registry
    from write_path import Memory
    ent = Registry(["Tom Baker", "Tom Barker", "Tom Becker", "Anna Fischer",
                    "Anna Fisher", "Acme Labs", "Acme Analytics", "Nova Systems",
                    "Berlin", "Boston", "Lisbon", "Sam Chen", "Sam Cheng",
                    "Maria Garcia", "Dana Novak", "Peter Klein", "Julia Park",
                    "Oscar Quinn", "Ella Wong", "Leo Tran"])
    rel = Registry(["works at", "is employed by", "lives in", "resides in",
                    "was born in", "manages"])
    m2 = Memory(ent, rel)
    pairs = [("Tom Baker", "works at", "Acme Labs"),
             ("Tom Barker", "works at", "Nova Systems"),   # near-dup subject
             ("Anna Fischer", "lives in", "Berlin"),
             ("Anna Fisher", "lives in", "Boston"),        # near-dup subject
             ("Sam Chen", "works at", "Acme Analytics"),
             ("Sam Cheng", "is employed by", "Nova Systems"),  # near-dup both
             ("Maria Garcia", "lives in", "Lisbon"),
             ("Maria Garcia", "resides in", "Boston")]     # near-synonym rel
    for s, r, o in pairs:
        wr = m2.write(s, r, o)
        say(f"  write ({s} | {r} | {o}): accepted={wr.accepted} {wr.reason}")
    say()
    say(f"{'query':38s} {'m_l2':>7s} {'p_sto':>6s} {'m_ref':>7s} route/tag  answer")
    queries = [("Tom Baker", "works at"),    # near-dup sibling stored
               ("Tom Barker", "works at"),
               ("Anna Fischer", "lives in"),
               ("Sam Chen", "works at"),
               ("Maria Garcia", "lives in"),  # same subj, synonym rels
               ("Maria Garcia", "resides in")]
    for s, r in queries:
        q = m2.query(s, r)
        p_sto = float(1.0 - sigmoid((q.m_l2 - C_L2) / S_L2))
        ans = q.record[2] if q.record else None
        say(f"{s + ' / ' + r:38s} {q.m_l2:7.3f} {p_sto:6.3f} {q.m_ref:7.3f} "
            f"{q.action}/{q.tag}  {ans}")
    say()
    say("interpretation aid: a collision-grade m_l2 under the frozen constants "
        f"needs m_l2 < ~{C_L2 - 2 * S_L2:.3f} for p_sto>0.88; the registered "
        "eval only ever presents m_l2 = 0.000 (identical keys) vs "
        "m_l2 > 0.55 (singletons).")

    with open(os.path.join(HERE, "a4_output.txt"), "w") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
