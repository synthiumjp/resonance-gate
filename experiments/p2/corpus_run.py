"""p2 REAL-CORPUS scoring: run the full pipeline over the anonymized real-chat
corpus and package detections for blind independent adjudication.

This is the honest real-data test the session kept deferring, at n>1. It runs the
working spine -- numeric belief (noise-gated) + scoped categorical audit -- on
each real conversation, then emits:
  1. a per-conversation result table (did it fire, on what),
  2. an aggregate the way the PRODUCT is judged: false-alarm rate on the no-change
     conversations (the number that decides "memory you can trust"), and raw
     recall on the change-flagged ones,
  3. a blind validation packet (validation_packet_real.json) -- every detection
     with the statements needed to judge it, arm-blinded -- for two independent
     judges, because this session's rule is that only independently-adjudicated
     numbers are trustworthy.

The scraper's has_change flags are WEAK labels (the agent's own judgement); they
seed candidate ground truth but are themselves re-verified by the judges, never
trusted as final -- same discipline that caught the B-semantic inflation.

Usage: .venv/bin/python experiments/p2/corpus_run.py <corpus_dir>
"""

import json
import os
import sys
import glob

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from run_real import load_user_turns, build_memory
from run_belief import changes
from scope_audit import audit_scoped


def load_meta(corpus_dir):
    """Merge the per-agent *_meta.jsonl weak labels, keyed by filename."""
    meta = {}
    for mf in glob.glob(os.path.join(corpus_dir, "*_meta.jsonl")):
        for line in open(mf):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                meta[d["file"]] = d
            except Exception:
                pass
    return meta


def run_conversation(turns):
    """Return (belief_changes, audit_changes) for one conversation."""
    mem = build_memory(turns)
    bc = changes(mem)
    try:
        ac, _info = audit_scoped(turns)
    except Exception:
        ac = []
    return bc, ac


def main():
    corpus_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        _HERE, "..", "..", "scratchpad", "real", "corpus")
    files = sorted(f for f in glob.glob(os.path.join(corpus_dir, "*.json")))
    meta = load_meta(corpus_dir)

    packet = []            # blind detections for judges
    rows = []              # per-conversation summary
    for path in files:
        fn = os.path.basename(path)
        turns = load_user_turns(path)
        if len(turns) < 2:
            continue
        bc, ac = run_conversation(turns)
        m = meta.get(fn, {})
        flagged = bool(m.get("has_change"))
        fired = bool(bc or ac)
        rows.append({"file": fn, "n_turns": len(turns), "flagged_change": flagged,
                     "belief_changes": len(bc), "audit_changes": len(ac),
                     "fired": fired})
        # package each detection for blind judging
        for c in ac:
            packet.append({"id": len(packet), "file": fn, "kind": "categorical",
                           "detection": {"attribute": c.get("attribute"),
                                         "old": c.get("old"), "new": c.get("new")},
                           "statements": turns})
        for c in bc:
            packet.append({"id": len(packet), "file": fn, "kind": "numeric",
                           "detection": {"slot": str(c["slot"]),
                                         "history": [(str(v), round(p, 2)) for v, p in c["history"]]},
                           "statements": turns})

    # aggregate the way the product is judged
    n = len(rows)
    change_convos = [r for r in rows if r["flagged_change"]]
    nochange_convos = [r for r in rows if not r["flagged_change"]]
    recall_fired = sum(1 for r in change_convos if r["fired"])
    fa_fired = sum(1 for r in nochange_convos if r["fired"])

    print(f"=== REAL CORPUS: {n} conversations ===")
    print(f"  flagged-change: {len(change_convos)} | no-change: {len(nochange_convos)}")
    print(f"  RAW recall (fired on a change-flagged convo): "
          f"{recall_fired}/{len(change_convos) or '-'}")
    print(f"  RAW false-alarm (fired on a NO-change convo): "
          f"{fa_fired}/{len(nochange_convos) or '-'}   <-- the product number")
    print(f"  total detections to adjudicate: {len(packet)}")
    print("  NOTE: these are RAW (pipeline vs weak scraper labels). The trustworthy")
    print("  numbers come from the blind two-judge adjudication of the packet.\n")
    for r in rows:
        mark = "FIRED" if r["fired"] else "  -  "
        flag = "chg" if r["flagged_change"] else "   "
        print(f"   [{mark}] [{flag}] {r['file']:12s} turns={r['n_turns']:3d} "
              f"belief={r['belief_changes']} audit={r['audit_changes']}")

    out = os.path.join(corpus_dir, "validation_packet_real.json")
    json.dump(packet, open(out, "w"), indent=1)
    print(f"\nblind validation packet -> {out}")


if __name__ == "__main__":
    main()
