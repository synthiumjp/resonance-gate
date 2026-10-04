# Reproducing the benchmark numbers

Everything here runs locally. Our runs used a Mac Studio (M3 Ultra); any
machine that can serve a 14B model at a few tokens per second will do, just
slower.

## The models

One local model reads every system's retrieved memory and answers, and the
same model judges the answers:

- Qwen3-14B, Q4_K_M GGUF (the build Ollama ships as `qwen3:14b`), served by
  `llama-cpp-python`'s OpenAI-compatible server, temperature 0, thinking off
  (`/no_think`).
- For the small-reader runs: Qwen3-4B, `Qwen/Qwen3-4B-GGUF`,
  `Qwen3-4B-Q4_K_M.gguf`, as the reader only (the judge stays the 14B).

```bash
python -m llama_cpp.server --model qwen3-14b.gguf --n_gpu_layers -1 \
  --n_ctx 16384 --port 8090 --host 127.0.0.1 --chat_format chatml
```

The judge was checked before use: 29/30 on the hand-labelled items in
`false_memory/judge_items.jsonl` (`judge_validate.py`), and 197/198 agreement
with an Ollama-served copy of the same model on earlier calls.

## The systems

- sourcedrecall: this repository, `pip install -e server` and
  `sourcedrecall-setup`. Stanza is pinned to 1.14.0.
- Mem0 2.2.1, fully local: the same Qwen3-14B for its own extraction calls
  (through Ollama for the false-memory sets; through the llama_cpp server,
  `LOCOMO_MEM0_LLM_BASE`, for LoCoMo), `nomic-embed-text` embeddings through
  Ollama, on-disk Qdrant (`false_memory/adapters.py`, `locomo/retrieve.py`).
- Plain retrieval: every user message embedded with `BAAI/bge-small-en-v1.5`,
  the top results passed with their dates.

## LoCoMo

Data: `locomo10.json` from https://github.com/snap-research/locomo. We use
conversations 0-1 for development and 2-9 as the test set; categories 1-4
(category 5, adversarial, is left out, as in most published comparisons).

```bash
cd bench/locomo
export LOCOMO_DATA=/path/to/locomo10.json
export LOCOMO_LLM_BASE=http://127.0.0.1:8090/v1 LOCOMO_LLM_MODEL=<model name the server reports>
export LOCOMO_TOP_K=5          # sourcedrecall lines per speaker (each speaker has a store)
python retrieve.py rag --convs 2-9 --out results/mine
python retrieve.py sourcedrecall --convs 2-9 --out results/mine
python retrieve.py mem0 --convs 2-9 --out results/mine     # in a venv with mem0ai 2.2.1
python answer.py rag sourcedrecall mem0 --out results/mine
python score.py results/mine
```

Every step is resumable. Time on our machine: sourcedrecall ingest about 30
minutes for conversations 2-9 (two stores per conversation), Mem0 ingest about
six hours (941 model calls), answering and judging about 5 seconds per
question per system.

Published results: `results/test_mf` (messages-first at 01a88f5), and the
release run in `results/test_050`.

## False memory and changes of state

`bench/false_memory`. The sets: `cases.jsonl` (v1, read and tuned on),
`cases_dev_paraphrase.jsonl` and `cases_dev_stale*.jsonl` (development),
`cases_v2/v3/v4.jsonl` (blind: written before any system was run; the
developer reads only the counts, and an agent audits flagged answers).

```bash
cd bench/false_memory
export FM_CASES=cases_v4.jsonl FM_RESULTS=$PWD/results_mine FM_OVERRIDES=audit_overrides_v4.json
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=<model name>
export OURS_PY=<python with sourcedrecall> MEM0_PY=<python with sentence-transformers (and mem0ai)>
bash run_all.sh rag ours          # retrieval for each probe
python answer.py sourcedrecall rag # the reader answers from each system's memory
python score.py                    # results_mine/results.md
```

`score.py` reports, per system and view (`lines`: each returned line judged
on its own; `answer`: the reader's answer judged), the false-memory rate by
class, control recall, abstention on things never said, and whether the new
state was given. `audit_overrides_*.json` holds the judge errors found by the
audits, matched by the exact flagged text.

Published results: `results_v4_ans_mfg0` (and `_r4b` for the 4B reader),
`results_v3_ans_mfg0`.
