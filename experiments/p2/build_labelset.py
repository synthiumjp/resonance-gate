"""p2 Phase 0: build the SUPPORT labelled set.

Generates triple/span pairs for judge characterisation, per docs/
p2-instrument-note.md (rubric committed BEFORE this ran; git history is the
evidence).

SOURCE A — realistic distribution. Real user turns sampled from LongMemEval
oracle, run through the pinned extractor (SmolLM3-3B Q4_K_M). These carry the
extractor's true error profile, whatever it is.

SOURCE B — guaranteed hard-class coverage. Spans written to instantiate every
row of the instrument note's hard-class table, because those classes may be
too rare in Source A to estimate per-class recall. The SPAN is constructed;
the TRIPLE is whatever the real extractor produces from it. Only where the
extractor correctly emits nothing (so there is no pair to judge) is a
plausible-wrong triple supplied by hand, and those are flagged
`triple_origin="constructed"` and reported separately.

Output:
  labelset_blind.jsonl  — id, span, triple. What gets labelled. No source marker.
  labelset_key.jsonl    — id -> source, class, triple_origin. NOT consulted
                          while labelling.

Blinding is PARTIAL and that is stated in the instrument note: a single rater
who generated the set cannot be truly blind to it. Order randomisation under a
logged seed and withholding the key file are what is actually achieved.
"""

import json
import os
import random
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_R = os.path.dirname(os.path.dirname(_HERE))
for _p in (_R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from write_path import extract_triples

SEED = 20260724
N_TURNS = 260   # raised from 150 BEFORE any pair was labelled: the 150-turn
                # run yielded 107 pairs and docs/p2-instrument-note.md
                # pre-commits n >= 120. Same seed; the sample is redrawn, not
                # extended, so the set differs from the 150-run -- which is
                # harmless because nothing had been labelled and so nothing
                # could be cherry-picked. Logged rather than quietly changed.
ORACLE = os.path.join(_R, "data", "longmemeval_oracle")

# Source B: one or more spans per hard class from the instrument note table,
# plus genuinely-supported controls so both precision and recall are estimable.
HARD_SPANS = [
    ("hedged", "I think Bob might work at Zenith Labs, but I'm not certain."),
    ("hedged", "Maybe Clara studied at Meridian College? I can't remember."),
    ("hypothetical", "If I moved to Boston I'd need to buy a car straight away."),
    ("hypothetical", "Suppose Anna worked at Orion Foods — would that change the advice?"),
    ("future_intentional", "I'm thinking of moving to Boston next year."),
    ("future_intentional", "I plan to start at Nova Systems once my notice period ends."),
    ("negated", "I don't work at Acme Analytics any more."),
    ("negated", "Peter isn't married to Laura; they separated years ago."),
    ("superseded_in_span", "I used to live in Lisbon, but now I'm in Madrid."),
    ("superseded_in_span", "Sarah managed Daniel until the reorg, now she reports to him."),
    ("attributed", "My friend says I should join Orion Foods."),
    ("attributed", "According to my brother, Nina was born in Verona."),
    ("interrogative", "Do you know where Anna lives these days?"),
    ("interrogative", "Is it true that Felix works at Summit Robotics?"),
    ("inferred_not_stated", "I commute to the Dublin office every single day."),
    ("inferred_not_stated", "My rent in Ashford went up again this year."),
    ("altered_argument", "Tom Fischer just started at Nova Systems last Monday."),
    ("altered_argument", "Elena Ziegler transferred to the Genoa office in March."),
    ("over_specific", "I moved somewhere up north last spring."),
    ("over_specific", "She joined one of the big consultancies after graduating."),
    # genuinely supported controls
    ("supported_control", "Maria Garcia lives in Lisbon."),
    ("supported_control", "I work at Acme Labs as a data engineer."),
    ("supported_control", "Sarah Kim manages Daniel Diaz."),
    ("supported_control", "Nina Vogel was born in Verona."),
    ("supported_control", "My colleague Dana works at Orion Foods."),
    ("supported_control", "Victor Weber studied at Meridian College."),
    ("supported_control", "Leo Tran reports to Sofia Klein."),
    ("supported_control", "Iris Novak is married to Hugo Silva."),
]

# Used ONLY where the real extractor emits nothing for a hard-class span, so
# that the class still contributes a judgeable item. Flagged as constructed.
FALLBACK_TRIPLE = {
    "hedged": ("Bob", "works at", "Zenith Labs"),
    "hypothetical": ("I", "lives in", "Boston"),
    "future_intentional": ("I", "lives in", "Boston"),
    "negated": ("I", "works at", "Acme Analytics"),
    "superseded_in_span": ("I", "lives in", "Lisbon"),
    "attributed": ("I", "works at", "Orion Foods"),
    "interrogative": ("Anna", "lives in", "Dublin"),
    "inferred_not_stated": ("I", "lives in", "Dublin"),
    "altered_argument": ("Tom Fisher", "works at", "Nova Systems"),
    "over_specific": ("I", "lives in", "Boston"),
    "supported_control": None,
}


def main():
    rng = random.Random(SEED)
    d = json.load(open(ORACLE))
    turns = [t["content"] for x in d for s in x["haystack_sessions"]
             for t in s if t.get("role") == "user"]
    print(f"user turns available: {len(turns)}; sampling {N_TURNS} (seed {SEED})",
          flush=True)
    sample = rng.sample(turns, N_TURNS)

    pairs, t0 = [], time.time()
    for i, span in enumerate(sample):
        for tr in extract_triples(span):
            pairs.append({"span": span, "triple": list(tr), "source": "A",
                          "hard_class": None, "triple_origin": "extractor"})
        if (i + 1) % 25 == 0:
            print(f"  A: {i+1}/{N_TURNS} turns -> {len(pairs)} pairs "
                  f"({(time.time()-t0)/(i+1):.1f}s/turn)", flush=True)

    n_a = len(pairs)
    print(f"Source A complete: {n_a} pairs from {N_TURNS} turns", flush=True)

    for cls, span in HARD_SPANS:
        got = extract_triples(span)
        if got:
            for tr in got:
                pairs.append({"span": span, "triple": list(tr), "source": "B",
                              "hard_class": cls, "triple_origin": "extractor"})
        elif FALLBACK_TRIPLE.get(cls):
            pairs.append({"span": span, "triple": list(FALLBACK_TRIPLE[cls]),
                          "source": "B", "hard_class": cls,
                          "triple_origin": "constructed"})
    print(f"Source B complete: {len(pairs)-n_a} pairs from {len(HARD_SPANS)} spans",
          flush=True)

    rng.shuffle(pairs)
    for n, p in enumerate(pairs):
        p["id"] = f"p2-{n:04d}"

    with open(os.path.join(_HERE, "labelset_blind.jsonl"), "w") as f:
        for p in pairs:
            f.write(json.dumps({"id": p["id"], "span": p["span"],
                                "triple": p["triple"]}) + "\n")
    with open(os.path.join(_HERE, "labelset_key.jsonl"), "w") as f:
        for p in pairs:
            f.write(json.dumps({"id": p["id"], "source": p["source"],
                                "hard_class": p["hard_class"],
                                "triple_origin": p["triple_origin"]}) + "\n")

    from collections import Counter
    print(f"\nTOTAL {len(pairs)} pairs")
    print("  by source:", dict(Counter(p["source"] for p in pairs)))
    print("  by origin:", dict(Counter(p["triple_origin"] for p in pairs)))
    print("  extractor emitted nothing for hard classes:",
          sum(1 for p in pairs if p["triple_origin"] == "constructed"))


if __name__ == "__main__":
    main()
