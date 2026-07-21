"""p2 FULL-STREAM corroboration test: the real trust test for LLM-extracted profile.

Entry 65's sample under-measured the one thing that matters -- CORROBORATION -- by
sampling every ~55th turn, so nothing was seen twice. This runs EVERY prose turn
(what realtime would do incrementally), so a stable fact climbs to x10+ while a
transient stays x1. Corroboration IS the noise filter: no hard transient rule, just
a mention threshold.

Three mechanisms make corroboration accumulate:
  1. FULL STREAM  -- every turn, not a sample.
  2. canon_attr   -- attribute synonyms merge into one slot (residence/location/city).
  3. value CLUSTERING at readout -- "melbourne" / "melbourne australia" count as one.

Cached + resumable (extraction is the cost); cache lives in the quarantine, never
git. Reports the corroborated profile (>=2 mentions = the trust surface) vs the x1
tail (filtered), plus latency.

PRIVACY: quarantined input, redacted output, cache in scratchpad. Generic code only.
Usage: run_profile_full.py <conversations.json> [min_mentions=2]
"""

import json
import os
import re
import sys
import time
import hashlib
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import run_crosssession as RC
from run_crosssession import load_stream, redact
from run_belief import _is_prose
from llm_profile import extract_profile_facts, canon_attr

_STOP = {"the", "a", "an", "my", "of", "and", "in", "at", "to", "for", "with",
         "is", "was", "i", "am", "me", "current", "currently", "new", "some"}


def _cluster(value_counts):
    """Merge values in one slot by content-token overlap; sum their mentions.
    Returns [(label, total_mentions)] with the most-mentioned surface as label."""
    items = sorted(value_counts.items(), key=lambda kv: -kv[1])
    clusters = []
    for val, n in items:
        toks = {t for t in re.findall(r"[a-z0-9]+", val.lower())
                if t not in _STOP and len(t) > 1}
        placed = False
        for cl in clusters:
            if toks & cl["toks"]:
                cl["n"] += n
                cl["toks"] |= toks
                placed = True
                break
        if not placed:
            clusters.append({"label": val, "n": n, "toks": toks})
    return [(c["label"], c["n"]) for c in clusters]


def main():
    path = sys.argv[1]
    min_mentions = int(sys.argv[2]) if len(sys.argv) > 2 else 2

    try:
        u = json.load(open(os.path.join(os.path.dirname(path), "users.json")))[0]
        for tok in re.findall(r"[A-Za-z]{3,}", u.get("full_name", "")):
            RC._EXTRA_REDACT.append(tok)
    except Exception:
        pass

    cache_path = os.path.join(os.path.dirname(path), "profile_cache.jsonl")
    cache = {}
    if os.path.exists(cache_path):
        for line in open(cache_path):
            try:
                d = json.loads(line)
                cache[d["h"]] = d["f"]
            except Exception:
                pass
    cf = open(cache_path, "a")

    stream = load_stream(path)
    prose = [s for s in stream if _is_prose(s[3])]
    print(f"full stream: {len(prose)} prose turns (every turn -- realtime replay)\n")

    # slot -> {value: mentions}, over ALL turns (corroboration is a raw count,
    # not decayed -- a stable fact stays true even if last said a while ago)
    slots = defaultdict(lambda: defaultdict(int))
    lat = []
    for i, (step, uuid, date, text) in enumerate(prose):
        h = hashlib.sha1(text.encode("utf-8")).hexdigest()
        if h in cache:
            facts = cache[h]
        else:
            t0 = time.time()
            facts = extract_profile_facts(text)
            lat.append(time.time() - t0)
            cf.write(json.dumps({"h": h, "f": facts}) + "\n")
            cf.flush()
        for fct in facts:
            a = canon_attr(fct["attribute"])
            v = re.sub(r"\s+", " ", str(fct["value"]).strip().lower())
            if v:
                slots[a][v] += 1
        if (i + 1) % 500 == 0:
            print(f"  ...{i+1}/{len(prose)} turns")

    if lat:
        lat.sort()
        print(f"\nlatency (fresh extractions): median {lat[len(lat)//2]*1000:.0f} ms, "
              f"p90 {lat[int(len(lat)*0.9)]*1000:.0f} ms, {len(lat)} calls")
    else:
        print("\n(all extractions cache hits)")

    # corroborated profile: cluster values per slot, keep clusters >= min_mentions
    corroborated, tail = [], 0
    for attr, vc in slots.items():
        for label, n in _cluster(vc):
            if n >= min_mentions:
                corroborated.append((n, attr, label))
            else:
                tail += 1
    corroborated.sort(reverse=True)

    print(f"\n=== CORROBORATED PROFILE (>= {min_mentions} mentions = trust surface) ===")
    print(f"{len(corroborated)} corroborated facts; {tail} single-mention (x1) filtered out\n")
    for n, attr, label in corroborated[:70]:
        print(f"  [x{n:3d}] {redact(str(attr))[:20]:20s} : {redact(str(label))[:56]}")


if __name__ == "__main__":
    main()
