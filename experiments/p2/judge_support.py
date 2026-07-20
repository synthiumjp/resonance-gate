"""p2 Phase 0: run the pinned SUPPORT judge over the labelled set.

Judge: qwen3:14b, ollama digest bdbd181c33f2ed1b31c972991882db3c, blob
sha256-a8cc1361f3145dc01f6d77c6c82c9116b9ffe3c97b34716fe20418455876c40e.
Pinned in docs/p2-instrument-note.md, which also carries the NO JUDGE SHOPPING
rule: if this model fails the 0.85 precision-and-recall bar we report the
failure and repair the protocol or abandon — we do not try models until one
passes.

Loaded through llama-cpp on the GPU rather than the ollama runtime, for the
reason recorded in E5.1: ollama's bundled build has no ROCm runner in this
WSL2 environment and judged on CPU at ~20s/item; the same GGUF blob through
the working hipBLAS build runs ~1.2s/item.

The judge sees ONLY the span and the triple. It never sees the source (A/B),
the hard class, or the human label.

The system prompt below is a faithful encoding of the rubric committed in
docs/p2-instrument-note.md §3 BEFORE any pair was generated. It must not be
edited to improve agreement after seeing results — that would be tuning the
instrument to the answer. Any change gets logged as a protocol deviation.

Run: .venv/bin/python experiments/p2/judge_support.py
"""

import json
import os
import re
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))

GGUF = ("/usr/share/ollama/.ollama/models/blobs/"
        "sha256-a8cc1361f3145dc01f6d77c6c82c9116b9ffe3c97b34716fe20418455876c40e")

SYSTEM = """You audit a memory system's fact extraction. You are given a SPAN of \
conversation and a TRIPLE (subject | relation | object) that was extracted from it.

Answer one question: is the TRIPLE supported by the SPAN?

Answer SUPPORTED only if the span DIRECTLY AND EXPLICITLY asserts the triple as a \
CURRENTLY HELD FACT, in the voice of the speaker whose fact it is.

Answer NOT_SUPPORTED if any of these apply:
- HEDGED: the span hedges it ("I think", "might", "maybe", "not sure").
- HYPOTHETICAL: stated as a condition or supposition ("if I moved to Boston...").
- FUTURE or INTENTIONAL: a plan or intention, not a current fact ("I'm thinking of \
moving", "I plan to start at...").
- NEGATED: the span denies it ("I don't work there any more").
- SUPERSEDED WITHIN THE SPAN: the span itself says it is no longer true ("I used to \
live in Lisbon, but now Madrid" does not support living in Lisbon).
- ATTRIBUTED TO ANOTHER: someone else's claim or suggestion, not the speaker's \
assertion of fact ("my friend says I should join Acme").
- INTERROGATIVE: the span asks about it rather than asserting it.
- ASSISTANT-SOURCED: the assistant offering general information, not a fact about \
the user.
- INFERRED BUT NOT STATED: it follows plausibly but the span does not say it \
("I commute to the Dublin office" does not state that the person lives in Dublin).
- ALTERED ARGUMENT: a name or entity differs from the span ("Tom Fisher" when the \
span says "Tom Fischer").
- OVER-SPECIFIC: the object is more specific than the span supports ("moved up north" \
does not support "lives in Boston").
- NOT A FACT AT ALL: conversational filler turned into a triple ("I | see | what you \
mean").

Fixed judgement rules:
- A PARAPHRASED RELATION is fine. "works at" for "I'm employed at" is SUPPORTED. \
Relation wording need not match the span.
- SUBJECT IDENTITY MUST HOLD. A swapped or merged entity is NOT_SUPPORTED even if \
the rest is correct.
- TENSE: a fact asserted as true at the time of the span is SUPPORTED even if it \
might be superseded later in some other conversation. Only supersession stated \
WITHIN this span counts against it.

Use UNCLEAR only if the span is genuinely ambiguous and neither label is defensible.

Reply with ONLY a JSON object, no other text:
{"label": "SUPPORTED" | "NOT_SUPPORTED" | "UNCLEAR", "reason": "<one short clause>"}"""

_LLM = None


def get_llm():
    global _LLM
    if _LLM is None:
        from llama_cpp import Llama
        _LLM = Llama(GGUF, n_ctx=8192, n_gpu_layers=-1, verbose=False,
                     n_threads=os.cpu_count(), seed=0)
    return _LLM


def judge_pair(span, triple):
    user = (f"SPAN:\n{span}\n\n"
            f"TRIPLE:\n({triple[0]} | {triple[1]} | {triple[2]})")
    out = get_llm().create_chat_completion(
        messages=[{"role": "system", "content": "/no_think " + SYSTEM},
                  {"role": "user", "content": user}],
        max_tokens=256, temperature=0.0)
    txt = out["choices"][0]["message"]["content"]
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.DOTALL).strip()
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if not m:
        return {"label": "PARSE_FAIL", "reason": txt[:120]}
    try:
        j = json.loads(m.group(0))
    except Exception:
        return {"label": "PARSE_FAIL", "reason": txt[:120]}
    lab = str(j.get("label", "")).upper()
    if lab not in ("SUPPORTED", "NOT_SUPPORTED", "UNCLEAR"):
        return {"label": "PARSE_FAIL", "reason": txt[:120]}
    return {"label": lab, "reason": str(j.get("reason", ""))[:200]}


def main():
    src = os.path.join(_HERE, "labelset_blind.jsonl")
    dst = os.path.join(_HERE, "judgements.jsonl")
    pairs = [json.loads(l) for l in open(src)]
    done = {}
    if os.path.exists(dst):
        done = {json.loads(l)["id"]: 1 for l in open(dst)}
        print(f"resuming: {len(done)} already judged")
    t0 = time.time()
    with open(dst, "a") as f:
        for i, p in enumerate(pairs):
            if p["id"] in done:
                continue
            r = judge_pair(p["span"], p["triple"])
            f.write(json.dumps({"id": p["id"], **r}) + "\n")
            f.flush()
            if (i + 1) % 20 == 0:
                print(f"  {i+1}/{len(pairs)}  ({(time.time()-t0)/(i+1):.1f}s/item)",
                      flush=True)
    print(f"done -> {dst}")


if __name__ == "__main__":
    main()
