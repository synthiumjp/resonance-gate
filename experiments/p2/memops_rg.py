"""RG method for the MemOps benchmark (entry 157).

MemOps scores LIFECYCLE OPERATIONS -- remember / forget / update / reflect --
and asks a system for `predicted_operations`, `answer` and `provenance`.
Every baseline in the harness must INFER those operations from retrieved
text at question time. RG does not have to: it records them at ingest, so it
can REPORT them from its operation log (oplog.py).

That is the whole hypothesis of this run, and it is falsifiable: if reporting
a recorded log beats inferring from text, the trace-keeping architecture pays
on a benchmark built to measure it. If not, the log is product furniture.

Pipeline per conversation:
  turns -> extraction (local, cached) -> corroborated store + operation log
  probe -> RG evidence lines + the operation log -> composer -> contract JSON

Writes rows in the harness's own shape (`hypothesis` carries the output), so
5.5-evaluate_operation_metrics.py scores it beside their baselines.
"""
import hashlib
import json
import os
import re
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import oplog
import run_profile_full as PF
from halumem_run import canon_attr
from wire import WireGraph

CACHE = os.path.expanduser("~/rg_private/memops/extract_cache.jsonl")

CONTRACT = (
    "/no_think You are a memory system reporting on a user's history.\n\n"
    "STORED MEMORY (each line is a fact with how many times it was confirmed "
    "and when):\n{facts}\n\n"
    "MEMORY OPERATION LOG (what happened to memory, in order -- this is "
    "recorded, not inferred):\n{ops}\n\n"
    "Answer using ONLY the stored memory and the log above. If a value was "
    "forgotten, do not reveal it: use \"[FORGOTTEN]\". If the memory does not "
    "cover the question, say you do not know.\n\n"
    "Return ONLY compact JSON with exactly these fields:\n"
    '{{"predicted_operations": [{{"type": "remember|forget|update|reflect", '
    '"target": "...", "old_value": "... or [FORGOTTEN] or null", '
    '"new_value": "...", "state_after": "active|forgotten|updated|'
    'insufficient|inferred", "provenance": ["short quote"]}}], '
    '"answer": "...", "provenance": ["short quote"]}}\n\n'
    "Question: {question}\n"
)


def _cache():
    c = {}
    if os.path.exists(CACHE):
        for line in open(CACHE):
            try:
                d = json.loads(line)
                c[d["h"]] = d["f"]
            except Exception:
                pass
    return c


def ingest(conversations, extract_fn, cache, cf):
    """MemOps conversation segments -> (store nodes, operation log).

    Operations are recorded AS THEY HAPPEN, which is the point: a supersede is
    observed here (slot held A, this turn supplies B) rather than reconstructed
    later, which entry 154 showed is not possible."""
    slots = defaultdict(lambda: defaultdict(lambda: {"n": 0, "recs": []}))
    log = oplog.OperationLog()
    seen_value = {}                      # attr -> last value written
    for seg in conversations:
        si = seg.get("segment_index")
        for ti, turn in enumerate(seg.get("dialogue", [])):
            if turn.get("role") != "user":
                continue
            text = str(turn.get("content", "")).strip()[:1800]
            if not text:
                continue
            h = hashlib.sha1(text.encode()).hexdigest()
            if h in cache:
                facts = cache[h]
            else:
                facts = extract_fn(text)
                cache[h] = facts
                cf.write(json.dumps({"h": h, "f": facts}) + "\n")
                cf.flush()
            conv = f"s{si}t{ti}"
            for f in facts or []:
                a = canon_attr(f.get("attribute", ""))
                v = re.sub(r"\s+", " ", str(f.get("value", "")).strip().lower())
                if (not v or a in PF._EXCLUDE_ATTR
                        or PF._EXCLUDE_ATTR_RX.search(a) or PF._reject_value(a, v)):
                    continue
                prior = seen_value.get(a)
                slots[a][v]["n"] += 1
                slots[a][v]["recs"].append((f"seg{si}", conv))
                tgt = f"{a}={v}"
                if prior is None:
                    log.record("CREATE", tgt, conv=conv, attr=a, after=v,
                               evidence=[text[:120]])
                elif prior != v:
                    log.record("SUPERSEDE", tgt, conv=conv, attr=a,
                               before=prior, after=v, evidence=[text[:120]])
                else:
                    log.record("STRENGTHEN", tgt, conv=conv, attr=a, after=v,
                               evidence=[text[:120]])
                seen_value[a] = v
    facts, prov = [], []
    for a, entries in slots.items():
        for cl in PF._cluster(entries):
            row = (cl["n"], a, cl["label"], cl["recs"], cl.get("toks"))
            (facts if cl["n"] >= 2 else prov).append(row)
    g = WireGraph.from_facts(facts, n_convs=max(len(conversations), 1),
                             provisional=prov)
    return g, log


def render(g, log, max_facts=40, max_ops=30):
    nodes = list(g.nodes.values()) + list(g.provisional.values())
    nodes.sort(key=lambda n: -n.get("n_mentions", 1))
    fl = [f"[confirmed x{n['n_mentions']}] {n['attr']}: {n['value']}"
          for n in nodes[:max_facts]] or ["(nothing stored)"]
    ol = [f"{e['op']} {e['attr']}: "
          f"{(str(e['transition']['before'])+' -> ') if e['transition']['before'] else ''}"
          f"{e['transition']['after']}  (turn {e['trigger']['conversation']})"
          for e in log.entries[-max_ops:]] or ["(no operations)"]
    return "\n".join(fl), "\n".join(ol)
