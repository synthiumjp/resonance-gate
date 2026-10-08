"""LongMemEval single-session-preference, answer level (2026-10-08): with
sourcedrecall's block, does the reader's answer follow the user's preference?
Each question's description of the preferred response ("The user would
prefer responses that suggest resources specifically tailored to Adobe
Premiere Pro...") is the rubric; the local 14B answers and judges. Run with
the advice handling on and off (RG_ADVICE_RULE=0) to confirm it on data it
was not tuned on.

    LME_DATA=... READER=http://127.0.0.1:8090/v1 python pref_answers.py out.jsonl
"""
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("RG_REPO") or os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "server"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("SOURCEDRECALL_NOTES", "off")
DATA = os.environ.get("LME_DATA") or os.path.join(HERE, "longmemeval_s_cleaned.json")
READER = os.environ.get("READER", "http://127.0.0.1:8090/v1")
MODEL = os.environ.get("READER_MODEL", "qwen3-14b")

ANSWER = """You are an assistant with a memory of earlier conversations with the user. Answer the user's request helpfully in three or four sentences, using the memory where it helps.

MEMORY:
{memory}

REQUEST: {q} /no_think"""
JUDGE = """A user asked an assistant: "{q}"
What the user would prefer, according to what they said in earlier conversations:
{rubric}

The assistant answered:
{answer}

Does the answer follow what the user would prefer (tailored to their earlier details as described), rather than being generic? Answer YES or NO. /no_think"""


def chat(prompt, max_tokens=300):
    body = {"model": MODEL, "temperature": 0, "seed": 0, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(READER.rstrip("/") + "/chat/completions",
                                 json.dumps(body).encode(), {"Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=600).read())
    return re.sub(r"<think>.*?</think>", "", out["choices"][0]["message"]["content"] or "",
                  flags=re.S).strip()


class _Stub:
    """The block is built from the stored messages; the parser's facts are
    not needed here (as in run.py), and it makes ingest 50x faster."""
    _world = {}

    def extract_turn(self, *a, **k):
        return []

    def prefetch(self, *a, **k):
        pass


def main(out_path):
    from sourcedrecall import profile_memory as pm
    pm._get_extractor = lambda owner: _Stub()
    data = [e for e in json.load(open(DATA)) if e["question_type"] == "single-session-preference"]
    done = {}
    if os.path.exists(out_path):
        done = {json.loads(l)["question_id"]: json.loads(l) for l in open(out_path)}
    out = open(out_path, "a")
    for e in data:
        if e["question_id"] in done:
            continue
        wd = tempfile.mkdtemp(prefix="lmepref-")
        os.environ["RG_MEMORY_DIR"] = wd
        pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                          "uncached_turns": None, "transcripts": None, "msg_index": None})
        for sid, sess, date in zip(e["haystack_session_ids"], e["haystack_sessions"], e["haystack_dates"]):
            pm.profile_ingest([{"role": t["role"], "content": t["content"]} for t in sess],
                              conversation_id=sid, owner_name="User",
                              date=date.split(" ")[0].replace("/", "-"))
        block = pm.profile_context(e["question"])["block"]
        ans = chat(ANSWER.format(memory=block, q=e["question"]))
        verdict = chat(JUDGE.format(q=e["question"], rubric=e["answer"], answer=ans), 10)
        row = {"question_id": e["question_id"], "follows": verdict.strip().upper().startswith("YES"),
               "answer": ans, "verdict": verdict}
        out.write(json.dumps(row) + "\n")
        out.flush()
        shutil.rmtree(wd, ignore_errors=True)
        print(e["question_id"], row["follows"], flush=True)
    rows = [json.loads(l) for l in open(out_path)]
    print(f"follows the preference: {sum(r['follows'] for r in rows)}/{len(rows)}")


if __name__ == "__main__":
    main(sys.argv[1])
