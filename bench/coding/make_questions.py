"""Coding recall v1: write the questions (docs/PREREG_CODING_V1.md). From 6
history sessions per repository, spread evenly, Qwen3-14B writes up to 3
questions each (fix / how / why / where) with a gold answer and an evidence
quote. Dropped: evidence not in the condensed transcript; questions answered
right with no memory at all; duplicates.

    python make_questions.py dev OUT.jsonl
"""
import json
import re
import sys

from common import DATA, append, chat, claim, condensed, fitted, jsonl, sessions  # noqa: F401
import os

PER_REPO = 6
WRITE = """Below is a transcript of one coding session in the repository {repo}, condensed: what the user typed (USER), the assistant's replies (ASSISTANT), and each tool call with its command or file and the start of its result (TOOL; "[failed]" marks a command that failed).

Weeks later, the same developer, starting a new session on this project, wants to recall something from it. Write up to 3 such questions, each of a different type:
- "fix": what went wrong with something and what fixed it (or that it was not fixed)
- "how": how something is run, built, tested, deployed or configured in this project
- "why": why something was done or chosen, or what was ruled out
- "where": which file or component was changed to do or fix something (not where a name is defined: a search finds that)

Rules:
- Each question must be answerable only from this session's specifics, not from general knowledge.
- Ask as the developer would, naturally ("What broke the Docker image build when we added the ffmpeg step, and how did we fix it?"). Do not mention "the session", "the transcript" or dates.
- Name the specific thing the question is about: which test, build, command, feature, error or document. Never "the test", "the build", "the article", "the fix" or "last time" without saying which; the project has many.
- The answer must answer exactly that question, and only one answer may fit it.
- The answer: short (at most 25 words), specific (names, commands, files, errors). Give paths relative to the repository, not the developer's own folders.
- Skip a question whose answer is only a generated name (a hash, an ID, a random file name), or a detail nobody would want to recall.
- The evidence: an exact quote from the transcript (at most 200 characters) that shows the answer, copied character for character.
- Skip a type if the session has nothing good for it. Fewer, better questions are fine.

Return JSON: {{"questions": [{{"type": "fix|how|why|where", "question": "...", "answer": "...", "evidence": "..."}}]}}

TRANSCRIPT:
{transcript} /no_think"""

CLOSED = """Answer in one sentence. If you cannot know without the project's own history, say "I don't know".

QUESTION: {q} /no_think"""

JUDGE = """Does the ANSWER state the specific content of the GOLD answer to the QUESTION? Paraphrase is fine; it must not miss or contradict the gold's key point (the command, file, error, cause or reason). "I don't know" or a vague answer is WRONG.

QUESTION: {q}
GOLD: {gold}
ANSWER: {a}

Reply with one word: CORRECT or WRONG. /no_think"""


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def parse(text):
    """The questions from the writer's reply (llama_cpp's JSON mode returned
    {} for this prompt, so the reply is free text with a JSON object in it)."""
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        got = json.loads(m.group(0))["questions"] if m else []
    except (ValueError, KeyError, TypeError):
        return []
    return got if isinstance(got, list) else []


def judge(q, gold, a):
    v = chat(JUDGE.format(q=q, gold=gold, a=a), max_tokens=8)
    return "CORRECT" in v.upper() and "WRONG" not in v.upper()


def main(split, out):
    for repo, ss in sorted(sessions(split).items()):
        lock = out + "." + repo.replace("/", "__")
        if not claim(lock):          # another process (the other Qwen server) has it
            continue
        try:
            # re-read: the other process may have done this repository already
            done = {(r["repo"], r["session"]) for r in jsonl(out + ".log")}
            seen = {_norm(r["question"]) for r in jsonl(out)}
            _repo(repo, ss, out, done, seen)
        finally:
            os.remove(lock + ".lock")


def _repo(repo, ss, out, done, seen):
    picks = [ss[round(i * (len(ss) - 1) / max(1, PER_REPO - 1))] for i in range(min(PER_REPO, len(ss)))]
    for sid, ts, path in dict.fromkeys(picks):
        if (repo, sid) in done:
            continue
        shown = {}

        def build(t):
            shown["t"] = t
            return WRITE.format(repo=repo, transcript=t)
        reply, size = fitted(build, path)
        tr = shown["t"]
        got = parse(reply)
        kept = 0
        reasons = []
        for q in got[:3]:
            if not isinstance(q, dict) or q.get("type") not in ("fix", "how", "why", "where") \
                    or not q.get("question") or not q.get("answer"):
                reasons.append("malformed")
                continue
            if _norm(q.get("evidence")) not in _norm(tr) or len(_norm(q.get("evidence"))) < 12:
                reasons.append("evidence not found")
                continue
            if _norm(q["question"]) in seen:
                reasons.append("duplicate")
                continue
            cb = chat(CLOSED.format(q=q["question"]), max_tokens=80)
            if judge(q["question"], q["answer"], cb):
                reasons.append("answered without memory")
                continue
            seen.add(_norm(q["question"]))
            append(out, {"repo": repo, "session": sid, "session_at": ts, "type": q["type"],
                         "question": q["question"].strip(), "answer": q["answer"].strip(),
                         "evidence": q["evidence"].strip()})
            kept += 1
        append(out + ".log", {"repo": repo, "session": sid, "written": len(got), "kept": kept,
                              "dropped": reasons, "transcript_chars": size})
        print(repo, sid[:8], len(got), "written", kept, "kept", reasons, flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
