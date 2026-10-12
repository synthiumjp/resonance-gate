"""Copy a dev20 results dir (sdr-dev13, with msglog.jsonl from RG_MSG_LOG)
with message lines cut by relevance, on fixed retrieval. Lines the parser
routed to (via) and replacement messages (no score, no route) always stay.
A message-search-only line stays if its cross-encoder score >= T.
  via:T      cut only when the block has at least one parser-routed line
  top1:T     cut in every block, but the search's best line always stays
Advice questions (their own ranking) and list questions (k=16) are left alone.
usage: recut.py SRC_RESULTS DST_RESULTS via:-8"""
import json, sys, os, re, shutil
src, dst, spec = sys.argv[1:4]
mode, T = spec.split(":"); T = float(T)
# memory_api._LIST_Q and the "what has/have" form, as in _messages_block
_LIST = re.compile(
    r"^\W*(?:what|which)\s+(?:\w+\s+){0,2}?[a-z]{3,}s\s+(?:do|does|did|has|have|"
    r"had|are|were|is)\b|^\W*what\s+are\s+.*\b[a-z]{3,}(?<!ss)s\W*$|"
    r"\b(?:list|name)\s+(?:all|the|some|every)\b", re.I)
_HAS = re.compile(r"^\W*what\s+(?:has|have)\s", re.I)
os.makedirs(dst, exist_ok=True)
for f in ("answers_sourcedrecall.jsonl",):
    if os.path.exists(os.path.join(src, f)):
        shutil.copy(os.path.join(src, f), dst)
log = [json.loads(l) for l in open(os.path.join(src, "msglog.jsonl"))]
i = changed = dropped = 0
with open(os.path.join(dst, "raw_sourcedrecall.jsonl"), "w") as out:
    for r in map(json.loads, open(os.path.join(src, "raw_sourcedrecall.jsonl"))):
        for p in r.get("probes") or []:
            b = p.get("block") or ""
            if not b or b.startswith("[MEMORY] Nothing stored"):
                continue
            e = log[i]; i += 1
            body, sep, rules = b.partition("\n[MEMORY RULES]")
            head, _, lines = body.partition("\n")
            ls = lines.split("\n")
            assert e["q"] == p["q"] and len(ls) == len(e["msgs"]), (r["id"], p["q"], len(ls), len(e["msgs"]))
            if e.get("advice") or _LIST.search(p["q"]) or _HAS.match(p["q"]) or (mode == "via" and not any(m["via"] is not None for m in e["msgs"])):
                continue
            keep = []
            for l, m in zip(ls, e["msgs"]):
                k = (m["via"] is not None or m["score"] is None or m["score"] >= T
                     or (mode == "top1" and m["rank"] == 0))
                if k:
                    keep.append(l)
            if len(keep) < len(ls):
                changed += 1; dropped += len(ls) - len(keep)
                p["block"] = head + "\n" + "\n".join(keep) + sep + rules
        out.write(json.dumps(r, ensure_ascii=False) + "\n")
assert i == len(log), (i, len(log))
print(f"{spec}: blocks changed {changed}, lines dropped {dropped}")
