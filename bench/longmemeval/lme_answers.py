"""LongMemEval-S answer accuracy by question type (2026-10-12;
docs/PLAN_TO_LAUNCH.md 3.0), for the types that test what the parser is for:
knowledge-update and temporal-reasoning.

Per question: a fresh store with every haystack session, stored with its
date and the real parser (unlike run.py and pref_answers.py, which stub it:
the "no longer true" labels come from it). The reader gets LongMemEval's own
answer prompt (src/generation/run_generation.py, the plain one) with the
system's memory as the history and the question date; the judge gets its
own per-type prompt (src/evaluation/evaluate_qa.py, get_anscheck_prompt) and
the same yes/no parsing. Reader and judge are the local Qwen3-14B, so the
numbers compare the systems run here, not the paper's GPT-4o rows.

Systems:
  sdr    sourcedrecall's block for the question (profile_context)
  plain  the user's messages ranked by bge-small cosine, top 8, dated,
         oldest first

    LME_DATA=... python lme_answers.py --system sdr --types knowledge-update out.jsonl
Resumable: questions already in OUT are skipped.
"""
import argparse
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
sys.path.insert(0, os.path.join(REPO, "experiments", "p2"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("SOURCEDRECALL_NOTES", "off")
os.environ.setdefault("RG_NLI", "0")
DATA = os.environ.get("LME_DATA") or os.path.join(HERE, "longmemeval_s_cleaned.json")
READER = os.environ.get("READER", "http://127.0.0.1:8090/v1")
MODEL = os.environ.get("READER_MODEL", "qwen3-14b")
TOP = 8

# LongMemEval's own prompts, verbatim
ANSWER = ("I will give you several history chats between you and a user. Please answer the "
          "question based on the relevant chat history.\n\n\nHistory Chats:\n\n{}\n\n"
          "Current Date: {}\nQuestion: {}\nAnswer:")
_BASE = ("I will give you a question, a correct answer, and a response from a model. Please "
         "answer yes if the response contains the correct answer. Otherwise, answer no. ")
JUDGE = {
    "temporal-reasoning": _BASE + (
        "If the response is equivalent to the correct answer or contains all the intermediate "
        "steps to get the correct answer, you should also answer yes. If the response only "
        "contains a subset of the information required by the answer, answer no. In addition, "
        "do not penalize off-by-one errors for the number of days. If the question asks for the "
        "number of days/weeks/months, etc., and the model makes off-by-one errors (e.g., "
        "predicting 19 days when the answer is 18), the model's response is still correct. "
        "\n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response "
        "correct? Answer yes or no only."),
    "knowledge-update": _BASE + (
        "If the response contains some previous information along with an updated answer, the "
        "response should be considered as correct as long as the updated answer is the required "
        "answer.\n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model "
        "response correct? Answer yes or no only."),
}
ABSTAIN = ("I will give you an unanswerable question, an explanation, and a response from a "
           "model. Please answer yes if the model correctly identifies the question as "
           "unanswerable. The model could say that the information is incomplete, or some other "
           "information is given but the asked information is not.\n\nQuestion: {}\n\n"
           "Explanation: {}\n\nModel Response: {}\n\nDoes the model correctly identify the "
           "question as unanswerable? Answer yes or no only.")


def chat(prompt, max_tokens):
    body = {"model": MODEL, "temperature": 0, "seed": 0, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt + " /no_think"}]}
    req = urllib.request.Request(READER.rstrip("/") + "/chat/completions",
                                 json.dumps(body).encode(), {"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            out = json.loads(urllib.request.urlopen(req, timeout=600).read())
            break
        except OSError:
            if attempt == 2:
                raise
    return re.sub(r"<think>.*?</think>", "", out["choices"][0]["message"]["content"] or "",
                  flags=re.S).strip()


def _day(d):
    return d.split(" ")[0].replace("/", "-")


def sdr_memory(e):
    from sourcedrecall import profile_memory as pm
    wd = tempfile.mkdtemp(prefix="lmeans-")
    os.environ["RG_MEMORY_DIR"] = wd
    pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                      "uncached_turns": None, "transcripts": None, "msg_index": None})
    try:
        for sid, sess, date in zip(e["haystack_session_ids"], e["haystack_sessions"], e["haystack_dates"]):
            pm.profile_ingest([{"role": t["role"], "content": t["content"]} for t in sess],
                              conversation_id=sid, owner_name="User", date=_day(date))
        return pm.profile_context(e["question"])["block"]
    finally:
        shutil.rmtree(wd, ignore_errors=True)


_ENC = []


def plain_memory(e):
    import ort_models
    if not _ENC:
        _ENC.append(ort_models.Encoder(ort_models.EMBEDDER))
    msgs = [(_day(date), t["content"]) for sess, date in zip(e["haystack_sessions"], e["haystack_dates"])
            for t in sess if t["role"] == "user" and t["content"].strip()]
    v = _ENC[0].encode([m for _, m in msgs], normalize_embeddings=True)
    q = _ENC[0].encode([e["question"]], normalize_embeddings=True)[0]
    top = sorted((msgs[i] for i in (v @ q).argsort()[::-1][:TOP]), key=lambda m: m[0])
    return "\n".join(f'- [{d}] "{" ".join(m.split())}"' for d, m in top)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--system", choices=["sdr", "plain"], required=True)
    ap.add_argument("--types", default="knowledge-update")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    types = a.types.split(",")
    data = [e for e in json.load(open(DATA)) if e["question_type"] in types][:a.limit]
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(l)["question_id"] for l in open(a.out)}
    memory = sdr_memory if a.system == "sdr" else plain_memory
    with open(a.out, "a") as out:
        for e in data:
            if e["question_id"] in done:
                continue
            block = memory(e)
            ans = chat(ANSWER.format(block, e["question_date"], e["question"]), 300)
            abst = "_abs" in e["question_id"]
            jp = (ABSTAIN if abst else JUDGE[e["question_type"]]).format(e["question"], e["answer"], ans)
            verdict = chat(jp, 10)
            row = {"question_id": e["question_id"], "type": e["question_type"], "abstention": abst,
                   "correct": "yes" in verdict.lower(), "answer": ans, "verdict": verdict,
                   "context_chars": len(block)}
            out.write(json.dumps(row) + "\n")
            out.flush()
            print(e["question_id"], row["correct"], flush=True)
    rows = [json.loads(l) for l in open(a.out)]
    for t in types:
        r = [x for x in rows if x["type"] == t]
        print(f"{a.system} {t}: {sum(x['correct'] for x in r)}/{len(r)}")


if __name__ == "__main__":
    main()
