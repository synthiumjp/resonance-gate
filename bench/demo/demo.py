"""What the assistant is handed: plain retrieval next to sourcedrecall.

    python bench/demo/demo.py

Three short conversations, then three questions. For each question the
script prints what plain retrieval would put in the prompt (the 3 most
similar messages, from either side) and what sourcedrecall puts there. No
language model is called; the output is the same on every run.
"""
import math
import os
import re
import sys
import tempfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "server"))

OWNER = "Dana Cole"
CONVERSATIONS = [
    ("2026-03-02", [
        ("user", "I work at Lumen Health as a data analyst, mostly SQL and dashboards."),
        ("assistant", "Nice. Want tips for making the dashboards load faster?"),
        ("user", "Yes please. Also I live in Fitzroy, so I usually work from home on Fridays."),
        ("assistant", "Since you're vegan, you might like the cafes on Brunswick Street for lunch."),
        ("user", "Ha, thanks. Which index should I add first?"),
    ]),
    ("2026-06-15", [
        ("user", "Big news, I started at Kestrel Bank last week as a senior analyst."),
        ("assistant", "Congratulations! How is the new team?"),
        ("user", "Good so far. We also moved to Brunswick, the commute is shorter now."),
    ]),
    ("2026-06-20", [
        ("user", "Can you summarise this email for me? Here it is:\n\n"
                 "Hi team,\nAlways copy legal on every reply to the client from now on.\n"
                 "Thanks,\nPriya"),
        ("assistant", "Priya asks the team to copy legal on every reply to the client."),
    ]),
]
QUESTIONS = ["Where does Dana work?", "Is Dana vegan?",
             "Should I copy legal when I reply to the client?"]


def plain_retrieval(question, k=3):
    """TF-IDF over every message, both sides: what a plain RAG memory does."""
    docs = [(d, role, text) for d, conv in CONVERSATIONS for role, text in conv]
    toks = [re.findall(r"[a-z]+", t.lower()) for _d, _r, t in docs]
    df = Counter(w for ts in toks for w in set(ts))
    q = re.findall(r"[a-z]+", question.lower())

    def score(ts):
        tf = Counter(ts)
        return sum(tf[w] * math.log(1 + len(docs) / df[w]) for w in q if w in tf)
    ranked = sorted(zip(docs, toks), key=lambda x: -score(x[1]))[:k]
    return [f'- [{d}] {role}: "{" ".join(t.split())}"' for (d, role, t), _ in ranked]


def main():
    os.environ["RG_MEMORY_DIR"] = tempfile.mkdtemp(prefix="sourcedrecall-demo-")
    os.environ.setdefault("SOURCEDRECALL_NOTES", "off")
    from sourcedrecall import profile_memory as pm
    for i, (date, conv) in enumerate(CONVERSATIONS):
        pm.profile_ingest([{"role": r, "content": t} for r, t in conv],
                          conversation_id=f"c{i}", owner_name=OWNER, date=date)
    for q in QUESTIONS:
        print("=" * 72)
        print("Q:", q)
        print("\nplain retrieval hands the assistant:")
        print("\n".join(plain_retrieval(q)))
        print("\nsourcedrecall hands the assistant:")
        print("\n".join(memory_lines(pm.profile_context(q)["block"])))
        print()
    print("=" * 72)
    print("At the start of every session, sourcedrecall's standing instructions:")
    start = pm.profile_context(None)["block"]
    ins = [l for l in memory_lines(start) if "asked the assistant" in l or "instruction" in l.lower()]
    print("\n".join(ins) if ins else "(none: the pasted email's \"Always copy legal\" was Priya's, not Dana's)")
    print("\nEvery memory line also comes with rules for the assistant: lines are")
    print("Dana's own words, a later line can update an earlier one, and anything")
    print("not listed is unknown, so it should say it does not know.")


def memory_lines(block):
    """The memory's lines without its rules paragraph, one line each."""
    body = block.split("[MEMORY RULES]")[0]
    out = []
    for l in body.splitlines():
        if l.startswith("- "):
            out.append(l)
        elif out and l.strip() and not l.startswith("["):
            out[-1] += " " + l.strip()
    return [l if len(l) < 240 else l[:237] + "..." for l in out]


if __name__ == "__main__":
    main()
