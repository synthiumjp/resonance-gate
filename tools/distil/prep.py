"""teacher.jsonl -> mlx-lm completions data (train/valid) with the student's short prompt."""
import json, os, random, sys
SRC, OUT = sys.argv[1], sys.argv[2]
DEIXIS = len(sys.argv) > 3 and sys.argv[3] == "deixis"   # r4: pronouns made explicit (notes.explicit_person)
STUDENT = ("Write the lasting facts {owner} states about themselves in this conversation "
           "from {date}, one short sentence per line starting with \"{owner}\", or NONE.\n\n{conversation}")
from notes_ref import grounded
rows = [json.loads(l) for l in open(SRC)]
# ground each note in the user's lines the teacher saw (the conversation can be cut at 12,000 chars)
for r in rows:
    seen = " ".join(l.split(": ", 1)[1] for l in r["conv"].split("\n") if l.startswith(r["owner"] + ": "))
    r["notes"] = [n for n in r["notes"] if grounded(n, seen, r["owner"])]
random.Random(3).shuffle(rows)
nval = max(2, len(rows) // 20)
import os; os.makedirs(OUT, exist_ok=True)
if DEIXIS:
    sys.path.insert(0, os.path.expanduser("~/jpwork/sdr-dx/server"))
    from sourcedrecall.notes import explicit_person
    for r in rows:
        r["conv"] = "\n".join(explicit_person(r["conv"].split("\n"), r["owner"]))
for name, part in (("valid", rows[:nval]), ("train", rows[nval:])):
    with open(f"{OUT}/{name}.jsonl", "w") as f:
        for r in part:
            f.write(json.dumps({"prompt": STUDENT.format(owner=r["owner"], date=r["date"], conversation=r["conv"]),
                                "completion": "\n".join(r["notes"]) or "NONE"}) + "\n")
print(len(rows) - nval, "train", nval, "valid")
