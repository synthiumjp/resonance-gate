"""p2 FULL-STREAM corroboration test + CHECKABLE report.

Entry 65's sample under-measured CORROBORATION. This runs EVERY prose turn
(realtime replay) so a stable fact climbs to x10+ while a transient stays x1.
Corroboration IS the noise filter (assert only >= N mentions); mentions merge via
full stream + canon_attr + value clustering.

CHECKABILITY (how the user verifies it is really them): writes an UNREDACTED report
with RECEIPTS -- for every corroborated fact, the dates + conversation titles it was
pulled from -- to <quarantine>/profile_report.txt, which the user opens locally. So
each fact is traceable back to the conversations that support it. STDOUT stays
REDACTED (safe for the shared session); the local report file is the ground-truth
check.

Cached/resumable (cache in the quarantine, never git). PRIVACY: quarantined input,
redacted stdout, unredacted report stays local. Generic code only.
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
from run_crosssession import redact
from run_belief import _is_prose
from llm_profile import extract_profile_facts, canon_attr

_STOP = {"the", "a", "an", "my", "of", "and", "in", "at", "to", "for", "with",
         "is", "was", "i", "am", "me", "current", "currently", "new", "some"}

# --- readout hygiene (entry 68), from the registrant's own error taxonomy.
# 1. technical VALUES: file paths, drive letters, host paths, filenames -- never a
#    personal-profile fact value.
_TECH_VALUE = re.compile(
    r"[\\/]"                                     # any slash -> a path
    r"|^[a-z]:$"                                 # bare drive letter  c:  d:
    r"|~/|\.localhost|wsl\."                     # home path / localhost / wsl host
    r"|\.(py|csv|json|txt|md|ipynb|sh|ya?ml|ini|cfg)$",  # a filename
    re.I)
# 2. machine/device tokens are not a LOCATION (studio = the ssh box, pc, nas).
_DEVICE_WORDS = {"pc", "nas", "studio", "server", "host", "localhost", "laptop",
                 "desktop", "machine", "vm", "arc", "node", "box"}
# 3. transient / technical ATTRIBUTES -- not stable profile facts (they recur, so
#    corroboration alone does not drop them).
_EXCLUDE_ATTR = {"current_task", "current_activity", "current_directory",
                 "file_modified", "work_directory", "virtual_environment",
                 "model_path", "model_used", "project_phase", "current_position",
                 "concern", "current_interest", "current_role", "current_value",
                 "researcher_name", "research_field", "current_directory"}


def _reject_value(attr, v):
    """True if this (attr, value) is a technical/path/device artefact, not a fact."""
    v = v.strip().lower()
    if not v or _TECH_VALUE.search(v):
        return True
    if attr == "location" and v in _DEVICE_WORDS:
        return True
    return False


def load_stream_and_titles(path):
    """(stream, uuid->title). One load of conversations.json; stream is human
    turns time-ordered as (step, uuid, date, text)."""
    conv = json.load(open(path))
    conv.sort(key=lambda c: c.get("created_at", ""))
    titles, stream = {}, []
    for i, c in enumerate(conv):
        titles[c.get("uuid", "")] = c.get("name", "") or "(untitled)"
        for m in (c.get("chat_messages") or []):
            if (m.get("sender") or "").lower() != "human":
                continue
            txt = m.get("text") or m.get("content") or ""
            if isinstance(txt, list):
                txt = " ".join(str(x.get("text", "")) if isinstance(x, dict) else str(x)
                               for x in txt)
            if txt.strip():
                stream.append((i, c.get("uuid", ""), c.get("created_at", "")[:10],
                               txt.strip()[:1800]))
    return stream, titles


def _cluster(entries):
    """Merge one slot's values by content-token overlap; sum mentions and receipts.
    entries: {value: {"n": int, "recs": [(date, uuid)]}}. Returns list of dicts."""
    items = sorted(entries.items(), key=lambda kv: -kv[1]["n"])
    clusters = []
    for val, d in items:
        toks = {t for t in re.findall(r"[a-z0-9]+", val.lower())
                if t not in _STOP and len(t) > 1}
        placed = False
        for cl in clusters:
            if toks & cl["toks"]:
                cl["n"] += d["n"]
                cl["toks"] |= toks
                cl["recs"].extend(d["recs"])
                placed = True
                break
        if not placed:
            clusters.append({"label": val, "n": d["n"], "toks": toks,
                             "recs": list(d["recs"])})
    return clusters


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

    stream, titles = load_stream_and_titles(path)
    prose = [s for s in stream if _is_prose(s[3])]
    print(f"full stream: {len(prose)} prose turns (every turn -- realtime replay)\n")

    slots = defaultdict(lambda: defaultdict(lambda: {"n": 0, "recs": []}))
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
            if not v or a in _EXCLUDE_ATTR or _reject_value(a, v):
                continue
            slots[a][v]["n"] += 1
            slots[a][v]["recs"].append((date, uuid))
        if (i + 1) % 500 == 0:
            print(f"  ...{i+1}/{len(prose)} turns")

    if lat:
        lat.sort()
        print(f"\nlatency (fresh extractions): median {lat[len(lat)//2]*1000:.0f} ms, "
              f"p90 {lat[int(len(lat)*0.9)]*1000:.0f} ms, {len(lat)} calls")
    else:
        print("\n(all extractions were cache hits -- instant)")

    # corroborated facts, with receipts
    corr = []
    tail = 0
    for attr, entries in slots.items():
        for cl in _cluster(entries):
            if cl["n"] >= min_mentions:
                corr.append((cl["n"], attr, cl["label"], cl["recs"]))
            else:
                tail += 1
    corr.sort(reverse=True)

    # redacted summary to stdout (safe for the shared session)
    print(f"\n=== CORROBORATED PROFILE (>= {min_mentions} mentions) ===")
    print(f"{len(corr)} corroborated facts; {tail} single-mention (x1) filtered\n")
    for n, attr, label, recs in corr[:60]:
        print(f"  [x{n:3d}] {redact(str(attr))[:20]:20s} : {redact(str(label))[:52]}")

    # UNREDACTED checkable report with receipts -> LOCAL file only
    report = os.path.join(os.path.dirname(path), "profile_report.txt")
    with open(report, "w") as f:
        f.write(f"CHECKABLE PROFILE REPORT  ({len(corr)} corroborated facts, "
                f">= {min_mentions} mentions)\n")
        f.write("For each fact: [xN mentions] attribute : value, then the dates + "
                "conversation titles it was pulled from.\n")
        f.write("Verify by opening those conversations; if a fact is wrong or is "
                "about someone else, the receipts show where it came from.\n\n")
        for n, attr, label, recs in corr:
            f.write(f"[x{n}] {attr} : {label}\n")
            seen, shown = set(), 0
            for date, uuid in sorted(recs, reverse=True):
                if uuid in seen:
                    continue
                seen.add(uuid)
                f.write(f"     {date}  {titles.get(uuid, '')[:70]}\n")
                shown += 1
                if shown >= 6:
                    extra = len(set(u for _, u in recs)) - shown
                    if extra > 0:
                        f.write(f"     (+{extra} more conversations)\n")
                    break
            f.write("\n")
    print(f"\n>>> UNREDACTED checkable report (with receipts) written to:\n    {report}")
    print("    Open it locally to verify each fact against your own conversations.")


if __name__ == "__main__":
    main()
