#!/usr/bin/env python3
"""Entry 251: the update-axis FUNNEL. Where do the 142 points actually die?

WHY THIS BEFORE ANY SUPERSESSION DESIGN. e251 established that supersession
is gated to ~0% of nodes by a 24-name allowlist, and that the store is
predicate-keyed while the machinery is slot-keyed. The tempting next move is
to design a better representation of change. But every representation is
capped by what happens UPSTREAM of it: if the new fact is not in the store at
all, no edge model, no canonicalisation and no renderer can score the point.

So measure the funnel first. Four stages per gold update point:

  (i)   NEW  content present in the store at all?
  (ii)  OLD  content present in the store at all?      (both -> an edge is
                                                        even expressible)
  (iii) search_memories returns a NON-EMPTY list?      (the selection gate --
                                                        empty reroutes the
                                                        point to the lenient
                                                        integrity rubric)
  (iv)  NEW  content present in what was RETURNED?

Read the result like this:
  * dies at (i)      -> this is an EXTRACTION problem. Supersession design is
                        wasted effort; go get the change-bearing turns.
  * (i) ok, (ii) no  -> only the new state is stored; "replaced" is
                        unexpressible, but the judge holds the old memory
                        itself, so the new proposition alone may still score.
  * dies at (iii/iv) -> RETRIEVAL/readout problem; RG_UPDATE_V3 and the
                        selection gate are the levers.
  * survives to (iv) -> genuinely a REPRESENTATION problem, and only then is
                        an edge store the right build.

*** COVERAGE HERE IS A DESCRIPTIVE FUNNEL DIAGNOSTIC, NOT AN ACCURACY
    NUMBER. *** Token containment is barred as an accuracy proxy (it scored
    garbage above correct strings and disagreed with the judge in sign). It is
    used here only to localise where points die, the same way artifact-recall
    descriptors are used -- never to claim a score.

    python3 tools/update_funnel.py --user 0
"""
import argparse
import json
import os
import pathlib
import re
import sys

_P2 = "/home/jp/rg/experiments/p2"
_OFFICIAL = os.path.join(_P2, "halumem_official")
_EVAL = str(pathlib.Path.home() / "rg_private/halumem/official/HaluMem/eval")
DATA = pathlib.Path.home() / "rg_private" / "halumem" / "HaluMem-Medium.jsonl"

_WORD = re.compile(r"[a-z0-9']+")
_STOP = {"the", "a", "an", "is", "are", "was", "were", "his", "her", "their",
         "to", "of", "and", "in", "for", "on", "with", "as", "that", "this",
         "has", "have", "had", "he", "she", "they", "it", "s", "from", "by",
         "at", "be", "been", "or", "but", "not", "its", "also", "which"}


def toks(s):
    return {w for w in _WORD.findall((s or "").lower()) if w not in _STOP}


def contained(gold, cand):
    """Fraction of gold's content tokens present in cand."""
    G = toks(gold)
    return len(G & toks(cand)) / len(G) if G else 0.0


def best(gold, cands):
    return max((contained(gold, c) for c in cands), default=0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", type=int, default=0)
    ap.add_argument("--arm", choices=("rgx", "llm"), default="rgx")
    ap.add_argument("--cover", type=float, default=0.6,
                    help="content-token containment counted as 'present'")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    os.environ["RG_EXTRACT_V5"] = "1"
    os.environ["RG_RETRIEVE_V3"] = "1"
    if args.arm == "rgx":
        os.environ["RG_INGEST_ALL_TURNS"] = "1"
    for p in (_P2, _OFFICIAL, _EVAL):
        if p not in sys.path:
            sys.path.insert(0, p)

    import halumem_run as RG      # noqa: E402
    import eval_rgp2 as EV        # noqa: E402

    cache = str(pathlib.Path.home() /
                f"rg_private/halumem/qa_{args.arm}/cache_u{args.user}_v5.jsonl")
    with DATA.open() as fh:
        for i, line in enumerate(fh):
            if i == args.user:
                user_data = json.loads(line)
                break

    rows = []
    for k, session in enumerate(user_data["sessions"]):
        pts = [mp for mp in session.get("memory_points", [])
               if mp.get("is_update") == "True" and mp.get("original_memories")]
        if not pts:
            continue
        mem, _ = RG.ingest_user({"sessions": user_data["sessions"][:k + 1]},
                                cache, min_mentions=2)
        nodes = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
        store = [nd.get("text") or f"{nd['attr']}: {nd['value']}"
                 for nd in nodes]

        for mp in pts:
            new_c, old_c = mp["memory_content"], " ".join(mp["original_memories"])
            returned = EV.search_memories(mem, new_c)
            rows.append({
                "session": k,
                "new_in_store": best(new_c, store),
                "old_in_store": best(old_c, store),
                "returned_n": len(returned),
                "new_in_returned": best(new_c, returned),
            })
        print(f"  session {k}: {len(rows)} points", file=sys.stderr)

    n = len(rows)
    if not n:
        sys.exit("no update points")
    C = args.cover
    i_ok = sum(r["new_in_store"] >= C for r in rows)
    ii_ok = sum(r["old_in_store"] >= C for r in rows)
    both = sum(r["new_in_store"] >= C and r["old_in_store"] >= C for r in rows)
    iii_ok = sum(r["returned_n"] > 0 for r in rows)
    iv_ok = sum(r["new_in_returned"] >= C for r in rows)

    def line(lbl, v):
        return f"  {lbl:<44s}{v:4d}/{n}  ({100*v/n:5.1f}%)"

    print(f"\n=== update funnel: user {args.user}, arm {args.arm}, "
          f"{n} gold update points ===")
    print(f"    (descriptive containment>={C}, NOT an accuracy number)\n")
    print(line("(i)   NEW content in store", i_ok))
    print(line("(ii)  OLD content in store", ii_ok))
    print(line("      both -> an edge is expressible", both))
    print(line("(iii) search_memories non-empty", iii_ok))
    print(line("(iv)  NEW content in what was returned", iv_ok))
    print(f"\n  DIES AT (i): {n - i_ok} points ({100*(n-i_ok)/n:.1f}%) -- "
          f"extraction, not representation")
    if i_ok:
        print(f"  of those that survive (i): reach (iv) "
              f"{iv_ok}/{i_ok} ({100*iv_ok/i_ok:.1f}%)")
    out = args.out or f"/tmp/update_funnel_u{args.user}_{args.arm}.jsonl"
    with open(out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"\nper-point rows -> {out}")


if __name__ == "__main__":
    main()
