"""Teacher notes for distillation: Qwen3-14B (MLX 4-bit) writes notes over
LongMemEval sessions (MIT) with the product prompt; the product's grounding
filter keeps only lines whose words the user wrote. Output: teacher.jsonl."""
import json, random, re, sys, time
from mlx_lm import load, batch_generate
from notes_ref import grounded

# v2 (2026-10-06, after the first student): keep the user's time words, leave
# out the other side's news, no example sentence (the 14B copied it 8%).
PROMPT = """Below is one conversation from {date}. "{owner}" is the person this memory is about; the other side is someone they talked to.

Write the lasting facts {owner} states in it about themselves and their life: what they do, have, like, prefer, plan, did, and facts about the people, places and things in their life. One short sentence per line, in the third person, starting with "{owner}". Put items that belong together in one sentence. Keep when something happened in {owner}'s own words ("yesterday", "last year", "in 2022"). Use only what {owner} says about their own life: the other side's news, plans and family are not facts about {owner}, so leave them out unless {owner} took part. No guesses. If there is nothing lasting, write NONE.

CONVERSATION:
{conversation}
/no_think"""

N, BATCH, SRC = int(sys.argv[1]), int(sys.argv[2]), (sys.argv[3] if len(sys.argv) > 3 else "lme")
NAMES = ("Alex Morgan,Priya Shah,Tom Becker,Mei Lin,Jordan Lee,Sam Okafor,Lucia Romero,"
         "Ben Carter,Aisha Khan,Noah Fischer,Hannah Kim,Diego Alvarez,Grace Murphy,"
         "Ravi Patel,Emma Novak,Kenji Sato,Olivia Brown,Yusuf Demir,Clara Jensen,Leo Rossi").split(",")
rng = random.Random(7)
sess = {}
if SRC == "lme":
    d = json.load(open("/Users/chrismarmo/jpwork/lme/longmemeval_s_cleaned.json"))
    for q in d:
        for sid, date, s in zip(q["haystack_session_ids"], q["haystack_dates"], q["haystack_sessions"]):
            sess[sid] = (date, s)
else:
    # SODA (CC BY 4.0): two named people; the owner is one of them, the other is "Other"
    import pyarrow.parquet as pq
    soda = pq.read_table("soda/valid.parquet", columns=["dialogue", "speakers", "original_index"]).to_pylist()
    years = ["2021", "2022", "2023", "2024", "2025"]
    for r in soda:
        sp = r["speakers"]
        if len(r["dialogue"]) < 8 or len(set(sp)) != 2:
            continue
        me = sp[rng.randrange(2)]
        if SRC == "soda_flip":        # the same chat from the other speaker's side
            me = next(x for x in sp if x != me)
        date = f"{rng.choice(years)}/{rng.randrange(1, 13):02d}/{rng.randrange(1, 29):02d}"
        turns = [{"role": "user" if who == me else "assistant", "content": t, "name": who}
                 for who, t in zip(sp, r["dialogue"])]
        sess[f"soda_{r['original_index']}" + ("_flip" if SRC == "soda_flip" else "")] = (date, turns, me)
FP = re.compile(r"\b(I|I'm|I've|my|My|we|our)\b")
def personal(s):
    return sum(len(FP.findall(t["content"])) for t in s if t["role"] == "user")
ids = sorted(sess)
rng.shuffle(ids)
rich = [i for i in ids if personal(sess[i][1]) >= 4]
rest = [i for i in ids if i not in set(rich)]
pick = rich[:int(N * 0.8)] + rest[:N - int(N * 0.8)]
if SRC == "soda":
    pick = rich[:N]
elif SRC == "soda_flip":        # exactly the dialogues done from the first side
    have = {json.loads(l)["sid"] + "_flip" for l in open("teacher.jsonl") if '"src": "soda"' in l}
    pick = [i for i in ids if i in have][:N]
done = set()
try:
    done = {json.loads(l)["sid"] for l in open("teacher.jsonl")}
except FileNotFoundError:
    pass
items = []
for sid in pick:
    if sid in done:
        continue
    date, s = sess[sid][:2]
    owner = sess[sid][2] if SRC != "lme" else rng.choice(NAMES)
    lines = []
    for t in s:
        who = owner if t["role"] == "user" else "Other"
        txt = " ".join(str(t["content"]).split())
        if txt:
            lines.append(f"{who}: {txt[:1500]}")
    conv = "\n".join(lines)[:12000]
    said = " ".join(str(t["content"]) for t in s if t["role"] == "user")
    items.append(dict(sid=sid, owner=owner, date=date, conv=conv, said=said))
model, tok = load("mlx-community/Qwen3-14B-4bit")
def ids_of(it):
    p = PROMPT.format(owner=it["owner"], date=it["date"], conversation=it["conv"])
    return tok.apply_chat_template([{"role": "user", "content": p}], add_generation_prompt=True,
                                   enable_thinking=False)
items.sort(key=lambda it: len(it["conv"]))
out = open("teacher.jsonl", "a")
t0 = time.time()
for b in range(0, len(items), BATCH):
    chunk = items[b:b + BATCH]
    r = batch_generate(model, tok, [ids_of(it) for it in chunk], max_tokens=400)
    for it, raw in zip(chunk, r.texts):
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()
        kept, dropped = [], []
        for ln in raw.splitlines():
            ln = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", ln).strip()
            if not ln or ln.upper().startswith("NONE"):
                continue
            ok = it["owner"].split()[0].lower() in ln.lower() and grounded(ln, it["said"], it["owner"])
            (kept if ok else dropped).append(ln)
        out.write(json.dumps(dict(sid=it["sid"], owner=it["owner"], date=it["date"], conv=it["conv"],
                                  raw=raw, notes=kept[:20], dropped=dropped, pv=2, src=SRC)) + "\n")
    out.flush()
    print(f"{b + len(chunk)}/{len(items)} {time.time() - t0:.0f}s", flush=True)
print("teacher done", flush=True)
