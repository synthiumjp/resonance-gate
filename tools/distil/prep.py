"""teacher.jsonl -> mlx-lm completions data (train/valid) with the student's short prompt."""
import json, os, random, sys
SRC, OUT = sys.argv[1], sys.argv[2]
FLAGS = set(sys.argv[3:])
DEIXIS = "deixis" in FLAGS     # pronouns made explicit (notes.explicit_person)
# r3 learnt names as a shortcut ("Melanie" -> NONE, the same chat as "Caroline"
# -> notes): every row gets a fresh owner name and date format.
NAMES = "names" in FLAGS
FIRST = """Aaliyah Abdul Ada Adam Adebayo Aiko Ali Amara Ana Andre Anika Ari Arjun Astrid
Ayesha Bao Beatriz Ben Bianca Bilal Bruno Camila Carlos Chen Chiara Chloe Dana Daniel
Dara Dev Diego Dmitri Elena Eli Emeka Emma Erik Esther Fatima Felix Fiona Gabriel Grace
Hamid Hana Hugo Ibrahim Ines Ingrid Isaac Ivan Jada Jamal James Jana Javier Jia Joao
Jonas Jorge Julia Kai Kamal Karin Kemal Kenji Kofi Lars Layla Leila Leo Lina Lior
Luca Lucia Mai Malik Marco Maria Marta Mateo Maya Mehmet Mia Mika Mohammed Nadia
Nate Nia Nikhil Nina Noor Olu Omar Oscar Pablo Paolo Pedro Priya Rafael Rahul Rania Ravi
Rosa Ruth Sakura Samir Sara Sean Selin Seo-yeon Shira Sofia Tariq Tess Theo Tomas Uma
Valeria Vikram Wei Yara Yusuf Zara Zoe""".split()
LAST = """Abara Adeyemi Alvarez Andersson Bauer Becker Bianchi Chen Costa Dubois Eriksen
Fernandes Fischer Garcia Gupta Haddad Hansen Hughes Ibrahim Ivanova Jensen Kaur Khan
Kim Kowalski Larsen Lee Lopez Martin Mensah Moreau Murphy Nakamura Nguyen Novak Okafor
Ortiz Patel Perez Petrov Rossi Sato Schmidt Silva Singh Smith Suzuki Tanaka Torres
Wang Weber Wilson Yamamoto Yilmaz Zhang""".split()
MONTHS = "January February March April May June July August September October November December".split()
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
import re
if NAMES:
    nr = random.Random(11)
    for r in rows:
        old = r["owner"]
        new = nr.choice(FIRST) + ((" " + nr.choice(LAST)) if nr.random() < 0.4 else "")
        pats = [old] + ([old.split()[0]] if " " in old else [])
        def swap(t):
            for p in pats:
                t = re.sub(r"\b" + re.escape(p) + r"\b", new if p == old else new.split()[0], t)
            return t
        r["conv"] = swap(r["conv"]); r["notes"] = [swap(n) for n in r["notes"]]; r["owner"] = new
        m = re.match(r"(\d{4})/(\d{2})/(\d{2})", r["date"])
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            r["date"] = nr.choice([f"{y}-{mo:02d}-{d:02d}", f"{d} {MONTHS[mo - 1]}, {y}",
                                   f"{nr.randint(1, 12)}:{nr.randint(0, 59):02d} {nr.choice(['am', 'pm'])} on {d} {MONTHS[mo - 1]}, {y}",
                                   r["date"]])
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
