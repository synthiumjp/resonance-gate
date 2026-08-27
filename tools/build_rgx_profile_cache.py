#!/usr/bin/env python3
"""Run the deterministic extractor (rgx) over the REAL conversation corpus.

WHY. Every profile_cache on disk (v0/v2/v3) is LLM-extracted: its records
carry only {attribute, value}. The rgx parser -- the thing this project
actually ships -- has NEVER been run end-to-end over real conversations. So
we do not know what the deterministic extractor produces for a real person,
only what it scores on a synthetic benchmark whose gold is 80% written by the
assistant.

That is the wrong evidence for a product claim. This closes it: same parser,
same cache format the product path already reads (profile_cache_v5.jsonl,
picked up by RG_EXTRACT_V5=1), over the user's own conversations.

Both roles are extracted. The human turns are the user's own words; the
assistant turns exist ONLY so run_wire's hearsay pass can find
evidential=="report" clauses (it drops every other assistant clause). Getting
both into one cache keeps the product path's two-pass design intact.

    python3 tools/build_rgx_profile_cache.py --corpus ~/rg_private/conversations.json
    python3 tools/build_rgx_profile_cache.py --corpus ... --limit 200   # smoke
"""
import argparse
import hashlib
import json
import os
import pathlib
import sys
import time

sys.path.insert(0, "/home/jp/rg")
sys.path.insert(0, "/home/jp/rg/experiments/p2")
TRUNC = 1800          # must match the product path's truncation


def stream_both_roles(path, limit=None):
    """(role, text) for every prose turn, both roles, time-ordered.

    Mirrors run_profile_full.load_stream_and_titles and
    run_wire._load_assistant_stream, but in ONE pass -- loading a 546MB
    json twice to get the same turns is pure waste.
    """
    conv = json.load(open(path))
    conv.sort(key=lambda c: c.get("created_at", ""))
    if limit:
        conv = conv[:limit]
    for c in conv:
        for m in (c.get("chat_messages") or []):
            sender = (m.get("sender") or "").lower()
            if sender not in ("human", "assistant"):
                continue
            txt = m.get("text") or m.get("content") or ""
            if isinstance(txt, list):
                txt = " ".join(
                    str(x.get("text", "")) if isinstance(x, dict) else str(x)
                    for x in txt)
            txt = txt.strip()
            if txt:
                yield ("user" if sender == "human" else "assistant",
                       txt[:TRUNC])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus",
                    default=os.path.expanduser("~/rg_private/conversations.json"))
    ap.add_argument("--out", default=None,
                    help="default: profile_cache_v5.jsonl next to the corpus")
    ap.add_argument("--owner", default=None,
                    help="owner name for the person shift; omit and rgx "
                         "renders 'The user'")
    ap.add_argument("--limit", type=int, default=None,
                    help="first N conversations only (smoke test)")
    ap.add_argument("--resume", action="store_true",
                    help="skip turns already present in the output file")
    args = ap.parse_args()

    from rgx import Extractor

    out = pathlib.Path(args.out or (pathlib.Path(args.corpus).parent /
                                    "profile_cache_v5.jsonl"))
    done = set()
    if args.resume and out.exists():
        for line in out.open():
            try:
                done.add(json.loads(line)["h"])
            except Exception:
                pass
        print(f"resuming: {len(done)} turns already cached", file=sys.stderr)

    ex = Extractor(owner_name=args.owner)
    print(f"corpus: {args.corpus}\nout   : {out}\nowner : {args.owner!r}",
          file=sys.stderr)

    seen, n, wrote = set(done), 0, 0
    t0 = time.time()
    with out.open("a" if args.resume else "w") as fh:
        for role, text in stream_both_roles(args.corpus, args.limit):
            n += 1
            h = hashlib.sha1(text.encode("utf-8")).hexdigest()
            if h in seen:
                continue
            seen.add(h)
            recs = []
            try:
                for r in ex.extract_turn(text, role, 0, 0):
                    recs.append({"attribute": r.predicate, "value": r.value,
                                 "text": r.text, "kind": r.kind,
                                 "turn": r.turn, "role": r.role,
                                 "evidential": r.evidential})
            except Exception as exc:      # never lose the whole run to one turn
                print(f"  WARN turn {n} failed: {type(exc).__name__}: {exc}",
                      file=sys.stderr)
            fh.write(json.dumps({"h": h, "f": recs}) + "\n")
            fh.flush()
            wrote += 1
            if wrote % 250 == 0:
                el = time.time() - t0
                print(f"  {wrote} turns extracted / {n} seen, {el:.0f}s "
                      f"({el/wrote:.3f}s/turn)", file=sys.stderr)

    el = time.time() - t0
    print(f"\ndone: {wrote} turns extracted of {n} seen "
          f"({len(seen)-len(done)} unique), {el:.0f}s", file=sys.stderr)
    print(f"wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
