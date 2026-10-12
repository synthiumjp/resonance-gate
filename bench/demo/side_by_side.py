"""Side by side (2026-10-12, the launch review's demo): the same three
conversations stored by Mem0 2.2.1, plain retrieval and sourcedrecall, the
same questions, the same local reader and instruction. What each memory
hands the reader is printed with the answer, so anyone can see why.

The person (made up) says where they live, pastes a friend's email that
says "I'm allergic to nuts" and asks the assistant to always copy legal,
then moves. Mem0 runs fully local: its extraction calls go to the same
Qwen3-14B server, its embedder is bge-small (sentence-transformers).

    # in a venv with mem0ai==2.2.1 and sentence-transformers:
    python side_by_side.py mem0 out_mem0.json
    # in a venv with sourcedrecall:
    python side_by_side.py ours out_ours.json
    # anywhere (the reader):
    python side_by_side.py answer out_mem0.json out_ours.json > OUTPUT_side_by_side.txt
"""
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request

READER = os.environ.get("READER", "http://127.0.0.1:8090/v1")
MODEL = os.environ.get("READER_MODEL", "qwen3-14b")
OWNER = "Dana Cole"
CONVS = [
    ("2026-03-01", [
        ("user", "I'm vegetarian and I live in Leeds with my partner."),
        ("assistant", "Noted! Leeds has some great vegetarian spots."),
    ]),
    ("2026-04-10", [
        ("user", "can you help me reply to this one from Marcus?\n\n"
                 "Hi Dana,\nThanks for the invite to Saturday's dinner, count me in. "
                 "Just so you know, I'm allergic to nuts and I don't drink alcohol. "
                 "Also, please always copy legal on anything about the lease.\n"
                 "Best,\nMarcus"),
        ("assistant", "Sure: 'Hi Marcus, great, see you Saturday! I'll keep the menu nut-free.'"),
    ]),
    ("2026-05-02", [
        ("user", "Big news, we moved to Manchester last month."),
        ("assistant", "Congratulations on the move!"),
    ]),
]
QUESTIONS = ["What am I allergic to?", "Where do I live?",
             "Should you copy legal on emails about my lease?"]
# the instruction every system's memory is read with (v7's shared one)
RULES = ("Each memory line is something from earlier conversations, with its date where known. "
         "A later line can update an earlier one. If a question about the user is not answered "
         "by the memory, say you don't know.\n\n")


def chat(prompt, max_tokens=150):
    body = {"model": MODEL, "temperature": 0, "seed": 0, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt + " /no_think"}]}
    req = urllib.request.Request(READER.rstrip("/") + "/chat/completions",
                                 json.dumps(body).encode(), {"Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=600).read())
    return re.sub(r"<think>.*?</think>", "", out["choices"][0]["message"]["content"] or "",
                  flags=re.S).strip()


def run_mem0(out_path):
    from mem0 import Memory
    d = tempfile.mkdtemp(prefix="demo-mem0-")
    m = Memory.from_config({
        "llm": {"provider": "openai", "config": {"model": MODEL, "temperature": 0.0,
                                                 "max_tokens": 2000, "openai_base_url": READER,
                                                 "api_key": "none"}},
        "embedder": {"provider": "huggingface", "config": {"model": "BAAI/bge-small-en-v1.5",
                                                           "embedding_dims": 384}},
        "vector_store": {"provider": "qdrant", "config": {"collection_name": "demo",
                                                          "path": os.path.join(d, "q"),
                                                          "embedding_model_dims": 384,
                                                          "on_disk": True}},
        "history_db_path": os.path.join(d, "h.db")})
    # as in bench/locomo/retrieve.py: Qwen3 thinking off and no JSON grammar
    # (llama_cpp's grammar forbids the empty think block, and every answer
    # came back "{}"); no Mem0 prompt text changed
    client = m.llm.client
    create = client.chat.completions.create

    def nothink(*a, **k):
        ms = [dict(x) for x in k.get("messages", [])]
        if ms and ms[0].get("role") == "system":
            ms[0]["content"] = "/no_think\n" + ms[0]["content"]
        k["messages"] = ms
        k.pop("response_format", None)
        r = create(*a, **k)
        for c in r.choices:
            if c.message.content:
                c.message.content = re.sub(r"<think>.*?</think>", "", c.message.content,
                                           flags=re.S).strip()
        return r
    client.chat.completions.create = nothink
    for date, turns in CONVS:
        m.add([{"role": r, "content": t} for r, t in turns], user_id="dana",
              metadata={"date": date})
    stored = [x["memory"] for x in m.get_all(user_id="dana")["results"]]
    out = {"system": "Mem0 2.2.1", "stored": stored, "memory": {}}
    for q in QUESTIONS:
        hits = m.search(q, user_id="dana", limit=5)["results"]
        out["memory"][q] = "\n".join(f"- {h['memory']}" for h in hits)
    json.dump(out, open(out_path, "w"), indent=1)
    shutil.rmtree(d, ignore_errors=True)


def run_ours(out_path):
    d = tempfile.mkdtemp(prefix="demo-sdr-")
    os.environ["RG_MEMORY_DIR"] = d
    os.environ.setdefault("RG_NLI", "0")
    from sourcedrecall import profile_memory as pm
    import ort_models
    for i, (date, turns) in enumerate(CONVS):
        pm.profile_ingest([{"role": r, "content": t} for r, t in turns],
                          conversation_id=f"c{i}", owner_name=OWNER, date=date)
    ours = {"system": "sourcedrecall", "memory": {}}
    for q in QUESTIONS:
        ours["memory"][q] = pm.profile_context(q)["block"]
    # plain retrieval: the person's messages, top 3 by bge-small cosine, dated
    enc = ort_models.Encoder(ort_models.EMBEDDER)
    msgs = [(date, " ".join(t.split())) for date, turns in CONVS for r, t in turns if r == "user"]
    v = enc.encode([t for _, t in msgs], normalize_embeddings=True)
    plain = {"system": "plain retrieval", "memory": {}}
    for q in QUESTIONS:
        qv = enc.encode([q], normalize_embeddings=True)[0]
        top = sorted((msgs[i] for i in (v @ qv).argsort()[::-1][:3]), key=lambda m: m[0])
        plain["memory"][q] = "\n".join(f'- [{d_}] "{t}"' for d_, t in top)
    json.dump([plain, ours], open(out_path, "w"), indent=1)
    shutil.rmtree(d, ignore_errors=True)


def answer(paths):
    systems = []
    for p in paths:
        x = json.load(open(p))
        systems += x if isinstance(x, list) else [x]
    for q in QUESTIONS:
        print("=" * 72)
        print("QUESTION:", q)
        for s in systems:
            mem = s["memory"][q]
            ans = chat(RULES + "MEMORY:\n" + mem + "\n\nQUESTION: " + q)
            print(f"\n--- {s['system']}: what the reader was given")
            print(mem.split("[MEMORY RULES]")[0].strip() or "(nothing)")
            print(f"--- {s['system']}: answer\n{ans}")
    for s in systems:
        if s.get("stored"):
            print("=" * 72)
            print(f"{s['system']} stored:")
            print("\n".join("- " + x for x in s["stored"]))


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "mem0":
        run_mem0(sys.argv[2])
    elif mode == "ours":
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "server"))
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                        "experiments", "p2"))
        run_ours(sys.argv[2])
    else:
        answer(sys.argv[2:])
