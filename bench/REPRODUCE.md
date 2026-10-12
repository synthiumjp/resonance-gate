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

`bench/false_memory`. The sets:

- development, read and tuned on: `cases.jsonl` (v1) and `cases_dev_*.jsonl`
  (paraphrase, changes, pasted text, own material, advice, preferences,
  coding, projects, decisions);
- `cases_v2/v3/v4.jsonl`, `cases_code_blind.jsonl`,
  `cases_projects_blind.jsonl`: written before any system was run, but run
  many times since and some rules were written from their errors, so now
  regression sets;
- `cases_v5.jsonl` to `cases_v11.jsonl`: held out. Each was pre-registered
  (`docs/PREREG_HELDOUT_V*.md`, committed before the set was written),
  written by an agent barred from the rules and the other sets, run once on
  the frozen commit, and read by the developer as counts only.

The protocol since 2026-10-10 (`FM_READER_SAME=1 FM_SAME_V7=1 FM_STRICT=1
FM_JUDGE_QUESTION=1`): every system's returns go to the same local reader
with the same instruction; the judge sees the question; an expected term
counts only as a whole word that is not in the question; a blinded audit
(`blind_audit.py`, an agent that sees no system names) corrects judge
errors, recorded in `audit_overrides_*.json` and matched by the exact
answer text.

Reproduce a held-out result from the committed retrievals (what each
system returned for each probe is in `results_vN/raw_*.jsonl`, so the
competitors need not be installed). With Qwen3-14B
(`qwen3-14b-a8cc1361.gguf`, llama_cpp.server) on port 8090:

```bash
cd bench/false_memory
mkdir -p results_mine && cp results_v10/raw_*.jsonl results_mine/
export FM_CASES=cases_v10.jsonl FM_RESULTS=$PWD/results_mine FM_OVERRIDES=audit_overrides_v10.json
export FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf
export FM_READER_SAME=1 FM_SAME_V7=1 FM_STRICT=1 FM_JUDGE_QUESTION=1
python answer.py sourcedrecall rag agentmemory ai-memory
python score.py                       # results_mine/results.md
python v10_tests.py                   # the pre-registered hypotheses
```

The reader and judge run at temperature 0 with a fixed seed, so the counts
should match `results_v10/SUMMARY.md`; a different build of llama.cpp or a
different quantisation can move a few answers. A full rerun, retrieval
included, is `vN_run.sh` (it needs agentmemory and ai-memory installed as in
`adapters_h2h.py`). The regression sets under the same protocol:
`fair_run.sh`, or step 4 of `tools/release_measure.sh`.

`score.py` reports, per system and view (`lines`: each returned line judged
on its own; `answer`: the reader's answer judged), the false-memory rate by
class, control recall, abstention on things never said, and whether the new
state was given. `v11_tests.py` also counts how often each answer said the
memory did not hold it.
