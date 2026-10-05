# Handover: sourcedrecall (product track)

Last updated 2026-10-05. Branch `product-p2`, pushed to github.com/synthiumjp/resonance-gate (public, research) and as `main` to github.com/synthiumjp/sourcedrecall (PRIVATE until launch; push both: `git push origin product-p2 && git push sr product-p2:main`, tags to both).
Latest release tag: `sourcedrecall-v0.5.0`: messages-first evidence (the user's
own dated messages, chosen and labelled by the parser). Full suite on the
Mac: 1054 passed, 3 skipped.

## What it is

A local memory for AI agents. A dependency parser (Stanza + the `rgx` rules)
turns what the user says into facts, each kept with the user's exact words and
the date. No language model is called when storing. Retrieval is BM25 +
bge-small embeddings + a MiniLM cross-encoder, all run with ONNX Runtime from
fp16-stored weights (identical results to PyTorch). Stanza still needs torch.
Stanza is pinned to 1.14.0 in `server/pyproject.toml`: the rgx rules are tuned
on it, and 1.15 parses some sentences differently (3 parser tests fail on it,
e.g. it tags "due" in "due to" as ADJ). Test any Stanza upgrade with the full
suite before moving the pin.

Delivery: a Claude Code plugin (`plugins/sourcedrecall`), an MCP server for any
MCP client (`docs/CLIENTS.md`), and a command line for everything else
(`sourcedrecall-memory ingest | recall | context | show | view | forget |
confirm`; `sourcedrecall-import gemini <session file>`).

## Where things stand (numbers)

False-memory benchmark, `bench/false_memory` (local judge qwen3:14b, every
flagged line audited):

| set | sourcedrecall | Mem0 2.2.1 | RAG |
|---|---|---|---|
| v1 (72, read, tuned on) false memory | 4/60 | 16/60 | 12/60 |
| v2 blind (48) false memory | 3/37 | 16/37 | 11/37 |
| v3 blind (48) false memory / paraphrase controls | 6/30, 19/23 | 9/30, 23/23 | 8/30, 23/23 |
| v4 blind (60, changes of state) stale-as-current / new state returned | 33/44, 28/44 | not run | 39/44, 44/44 |

Blind sets (`cases_v2/v3/v4.jsonl`) are numbers-only for the developer: never
read their case text or outputs. An agent audits new judge flags and reports
only verdicts. Dev sets you may read and tune on:
`cases_dev_paraphrase.jsonl` (`tools/paraphrase_dev.py`, 51/64 with
candidates) and `cases_dev_stale.jsonl` (`tools/stale_dev.py`, old line still
current 21/50, new state found 33/50).

Mac dev worktree for patches under test: `~/jpwork/sdr-dev` (run with
`PYTHONPATH=$PWD/server`), so benches in `~/jpwork/sdr` keep the committed code.

Product harnesses: `tools/dogfood.py --v3` (24/26 rank-1, 12/12 never-mentioned
refused, 8/8 unknown-attribute refused), `tools/scale_test.py` (refusals hold
at 1,526 facts), `tools/refusal_report.py` (all cells pass).

LoCoMo (`bench/locomo`), test conversations 2-9, 1307 questions, reader and
judge qwen3-14b: sourcedrecall 33.4%, Mem0 64.6%, RAG 56.6% (sourcedrecall
pinned at 3c6b0a7, confirmed facts only). The reader said "don't know" 207
times with our context (RAG 44). Conversations 0-1 are dev
(`results/dev_full`, `~/jpwork/locomo_dev.sh`).

The false-memory bench has an answer view (`answer.py`): a local reader
answers from each system's returned memory and the answer is judged. Blind
v4 answers, new block (7538dcf): old state given 13/44, new state 28/44
(RAG 7/44, 36/44); controls 16/16. Notebook e292.

## How to run things -- ON THE MAC, not WSL

The WSL box (15 GB) was OOM-killed twice on 2026-10-03 (09:58 and 18:46): a
test or bench Python process (6-9 GB) next to Ollama holding qwen3:14b (9 GB).
User systemd was down after a WSL restart, so `bench/false_memory/run_all.sh`
ran without its MemoryMax cap. Run heavy work on the Mac Studio (512 GB):

    ssh chrismarmo@100.126.162.38
    ~/jpwork/sdr          git clone of product-p2 (git pull to update)
    ~/jpwork/sdr-venv     its venv: pip install -e sdr/server pytest; sourcedrecall-setup
    ~/jpwork/sdr_setup.sh re-runs the clone/venv/models setup
    ~/jpwork/rg           an rsync copy used by the HaluMem tools -- leave it

Tests (the 1.14 Stanza models live in their own directory, because
`~/stanza_resources` is used by other work in that account):

    cd ~/jpwork/sdr && git pull
    STANZA_RESOURCES_DIR=~/jpwork/stanza_resources_114 \
      ../sdr-venv/bin/python -m pytest -q rgx experiments/p2 tools server

Bench runs write result directories into `~/jpwork/sdr`. Copy them back to
WSL and commit them there, then delete them on the Mac before the next `git
pull` -- an untracked copy of a committed file makes the pull abort, and a
script chained after it then runs on the OLD code (happened three times on
2026-10-03/04). Check `git log -1` on the Mac before trusting a run.

The venv also has `openai` and `tenacity`, which only the HaluMem judge-cache
tests need. `~/jpwork/sdr_retest.sh` pulls, reinstalls and runs the suite.

The Mac is shared with Chris: never touch processes you did not start, do not
pull models into his Ollama app. Our llama_cpp server (qwen3-14b GGUF) runs on
127.0.0.1:8090 (`bench/locomo/mac_serve.sh`); use it for any LLM reader or judge.

Long jobs: start them detached (`nohup ... &` on the Mac, `setsid nohup` on
WSL) and log to a file; Claude Code sessions here restart often and take their
child processes with them.

## Releasing

The installer now clones github.com/synthiumjp/sourcedrecall. Do NOT tag a new
release until that repo is public -- a plugin install could not clone it.
Releases up to 0.5.2 install from resonance-gate and keep working.


PyPI wheel: `python tools/build_wheel.py` (needs `pip install build`) writes
`server/dist/sourcedrecall-<version>-py3-none-any.whl`; the version is in
`server/pyproject.toml`. Test it in a fresh venv outside the repo before
uploading (`~/jpwork/wheeltest.sh` on the Mac). Not uploaded yet.


Bump `plugins/sourcedrecall/.claude-plugin/plugin.json` version, commit, tag
`sourcedrecall-v<version>`, push the branch and the tag. A fresh install from
the tag: `CLAUDE_PLUGIN_ROOT=plugins/sourcedrecall CLAUDE_PLUGIN_DATA=<scratch>
plugins/sourcedrecall/bin/sourcedrecall-run install`. Scan the diff for secrets
and real-conversation text before pushing (the repo is public).

## Open items, in order

1. Numbers to beat (notebook e297, e301): LoCoMo test 63.7% for the 0.5.0
   tag (Mem0 64.6, RAG 56.6; multi-hop 48.5 vs 61.9); blind v4 old state 2/44, new 42/44 (14B reader); blind v3 0/30
   false memory, 23/23 controls. The gap to Mem0 is multi-hop (41.8 vs
   61.9%). Next ideas: more parser links (relations other than apposition),
   grouping a list's items in the notes, and an audit of the answer-view
   flags on v3/v4 by an agent (unaudited so far).
2. Changes of state are the main weakness (blind v4: 33/44 stale facts
   returned as current; the new state is missing in 16/44, most likely never
   extracted). Work on a fresh readable dev set, not on v4 (notebook e291).
   v4 was judged on the Mac (`~/jpwork/fm_v4.sh`): the llama_cpp judge
   (`FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1
   FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf`) agrees with the ollama judge
   197/198 on v1 calls and 29/30 on the hand-labelled items. RAG runs from
   `~/jpwork/rg/.venv-judge` (has sentence-transformers). Mem0 on v4 not run
   (it needs ollama; the Mac's ollama is Chris's).
3. Release 0.4.6 with the installer and breed fixes once LoCoMo is done.
4. Parser distillation to drop torch (~0.8 GB), only if it matches Stanza on
   every test.
5. Codex CLI importer (format undocumented; stub).

## Rules carried from JP

Local models only for judging; no paid APIs. Subagents on sonnet or haiku.
Plain user-facing text. Commit at stage boundaries; push after each.
Labels must be screened against audited data before they are shown as trust
signals (JP's validity protocol; notebook e288 and later).
