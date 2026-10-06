"""Note precision on LoCoMo dev: the local 14B reads one session and the notes
written from it, and labels each note SAID (the person says it about
themselves or their life), OTHER (the other speaker's), or NO (not said /
wrong). One call per session per writer. Usage: note_judge.py STORE..."""
import json, glob, re, sys, urllib.request, collections
C = json.load(open("/Users/chrismarmo/jpwork/locomo10.json"))
URL = "http://127.0.0.1:8090/v1/chat/completions"
ASK = """Below is a conversation between {owner} and {other}, then numbered notes that claim to be facts about {owner}.

For each note, answer with one label:
SAID - {owner} says this (or clearly implies it) about themselves or their own life in the conversation.
OTHER - it is really about {other} or comes from what {other} said, not {owner}.
NO - nobody says it, or it is wrong.

CONVERSATION:
{conv}

NOTES:
{notes}

Answer one line per note, like "1: SAID". /no_think"""

def call(p):
    body = {"model": "qwen3-14b", "temperature": 0, "max_tokens": 800,
            "messages": [{"role": "user", "content": p}]}
    r = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = json.loads(urllib.request.urlopen(r, timeout=900).read())["choices"][0]["message"]["content"]
    return re.sub(r"<think>.*?</think>", "", t, flags=re.S)

for store in sys.argv[1:]:
    tally, rows = collections.Counter(), []
    for f in sorted(glob.glob(store + "/ours_*/notes.jsonl")):
        i, owner = re.search(r"ours_(\d+)_(\w+)", f).groups()
        conv = C[int(i)]["conversation"]
        by = collections.defaultdict(list)
        for l in open(f):
            r = json.loads(l); by[r["conv"]].append(r["text"])
        for sess, notes in by.items():
            turns = conv["session_" + sess[1:]]
            other = next(t["speaker"] for t in turns if t["speaker"] != owner)
            text = "\n".join(f'{t["speaker"]}: {t["text"]}' for t in turns)
            out = call(ASK.format(owner=owner, other=other, conv=text,
                                  notes="\n".join(f"{k + 1}. {n}" for k, n in enumerate(notes))))
            lab = dict(re.findall(r"(\d+)\s*[:.]\s*(SAID|OTHER|NO)\b", out))
            for k, n in enumerate(notes):
                v = lab.get(str(k + 1), "UNPARSED"); tally[v] += 1
                rows.append({"owner": owner, "sess": sess, "note": n, "label": v})
    n = sum(tally.values())
    print(store, n, {k: f"{v} ({v / n:.0%})" for k, v in tally.most_common()}, flush=True)
    json.dump(rows, open(store.rstrip("/") + "_judged.json", "w"))
