"""Held-out v12: checks the set against docs/PREREG_HELDOUT_V12.md before the
run (format, part sizes, expected terms under strict scoring).

    python v12_validate.py            # every problem, for the set's writer
    python v12_validate.py --counts   # numbers only, for the developer

Expected terms are scored as whole words not already in the question
(score.py, FM_STRICT=1), so each must appear as a whole word in a user turn
of the scenario and must not appear in its question.
"""
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.environ.get("FM_CASES") or os.path.join(HERE, "cases_v12.jsonl")
COUNTS = "--counts" in sys.argv
problems = []
n = collections.Counter()


def bad(cid, msg):
    problems.append(f"{cid}: {msg}")


def word(t, text):
    return re.search(r"(?<![a-z0-9])" + re.escape(t.lower()) + r"(?![a-z0-9])", text.lower())


ids = set()
for ln, line in enumerate(open(PATH, encoding="utf-8"), 1):
    if not line.strip():
        continue
    try:
        c = json.loads(line)
    except ValueError as e:
        bad(f"line {ln}", f"not JSON ({e})")
        continue
    cid = c.get("id", f"line {ln}")
    for k in ("id", "class", "subtype", "split", "owner", "conversations", "probes"):
        if k not in c:
            bad(cid, f"missing {k}")
    if cid in ids:
        bad(cid, "duplicate id")
    ids.add(cid)
    if c.get("split") != "v12":
        bad(cid, "split is not v12")
    part = (c.get("subtype") or "?")[:1]
    convs = c.get("conversations") or []
    dates = [cv.get("date") for cv in convs]
    if any(not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d or "") for d in dates):
        bad(cid, "a conversation without an ISO date")
    elif dates != sorted(dates):
        bad(cid, "conversations not oldest first")
    user = [t.get("content", "") for cv in convs for t in cv.get("turns", []) if t.get("role") == "user"]
    for cv in convs:
        for t in cv.get("turns", []):
            if t.get("role") not in ("user", "assistant") or not isinstance(t.get("content"), str):
                bad(cid, "a turn without role user/assistant and string content")
    probes = c.get("probes") or []
    if len(probes) != 1:
        bad(cid, f"{len(probes)} probes (one per scenario)")
    for p in probes:
        cls = p.get("class") or c.get("class")
        q = p.get("q") or ""
        if not q:
            bad(cid, "probe without q")
        if "forbid" in p and not re.match(r"The user(?:'s|’s)? ", p["forbid"].get("prop", "")):
            bad(cid, "forbid.prop does not start 'The user ' or 'The user\'s '")
        terms = (p.get("expect") or {}).get("terms")
        if "expect" in p:
            if not terms or not all(isinstance(t, str) and t.strip() for t in terms):
                bad(cid, "expect.terms empty")
            else:
                if not any(word(t, u) for t in terms for u in user):
                    bad(cid, f"no expected term {terms} as a whole word in a user turn")
                for t in terms:
                    if word(t, q):
                        bad(cid, f"expected term {t!r} is in the question (it would never count)")
        key = part
        if part == "D":
            if cls == "e":
                key = "D pasted"
                if "forbid" not in p:
                    bad(cid, "pasted item (class e) without forbid")
            elif cls == "f":
                key = "D own"
                if c["subtype"].startswith("D_read_"):
                    n["D own, brought to be read over"] += 1
                if "expect" not in p:
                    bad(cid, "own item (class f) without expect")
                if not 4 <= len(convs) <= 10:
                    bad(cid, f"own item with {len(convs)} conversations (4 to 10)")
            else:
                bad(cid, f"part D with class {cls}")
        elif part == "U":
            sub = c["subtype"]
            key = "U named" if sub.startswith("U_named") else "U unnamed" if sub.startswith("U_unnamed") else "U ?"
            if key == "U ?":
                bad(cid, "U subtype must start U_named or U_unnamed")
            if cls != "f" or "expect" not in p:
                bad(cid, "U item must be class f with expect")
            elif terms:
                long_ = [u for u in user if len(u) > 800 and any(
                    (m := word(t, u)) and m.start() > 600 for t in terms)]
                if long_:
                    n[key + " long"] += 1
        elif part == "B":
            if cls != "b" or "forbid" not in p or "expect" not in p:
                bad(cid, "B item must be class b with forbid and expect")
        elif part == "X":
            if cls != "f" or "expect" not in p:
                bad(cid, "X item must be class f with expect")
        elif part == "R":
            # real emails from the pool; pasted (class e, forbid) or the user's own (class f, expect)
            if cls == "e" and "forbid" in p and c["subtype"].startswith("R_pasted"):
                key = "R pasted"
            elif cls == "f" and "expect" in p and c["subtype"].startswith("R_own"):
                key = "R own"
            else:
                bad(cid, "R item must be R_pasted_ class e with forbid, or R_own_ class f with expect")
        else:
            bad(cid, f"subtype must start D, U, B, X or R (got {c.get('subtype')!r})")
        n[key] += 1

want = {"D pasted": 40, "D own": 30, "U named": 10, "U unnamed": 10, "B": 20, "X": 20,
        "R pasted": 20, "R own": 10}
for k, v in want.items():
    if n[k] != v:
        problems.append(f"set: {n[k]} {k} items (want {v})")
if n["D own, brought to be read over"] < 15:
    problems.append(f"set: {n['D own, brought to be read over']} own items with subtype D_read_ "
                    "(want at least 15)")
if n["U named long"] < 5 or n["U unnamed long"] < 5 or n["U named long"] + n["U unnamed long"] < 10:
    problems.append(f"set: long U pastes (over 800 characters, fact past 600): named "
                    f"{n['U named long']}, not named {n['U unnamed long']} (want 10, at least 5 each)")

print("counts:", {k: n[k] for k in sorted(n)}, "scenarios:", len(ids))
print(f"problems: {len(problems)}")
if not COUNTS:
    for x in problems:
        print("  " + x)
sys.exit(1 if problems else 0)
