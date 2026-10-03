# Handover: sourcedrecall (product track)

Last updated 2026-10-03. Branch `product-p2`, repo github.com/synthiumjp/resonance-gate.
Latest release tag: `sourcedrecall-v0.4.4`. Committed after it, not yet run
through the full suite: the read-only memory browser (515c2fa).

## What it is

A local memory for AI agents. A dependency parser (Stanza + the `rgx` rules)
turns what the user says into facts, each kept with the user's exact words and
the date. No language model is called when storing. Retrieval is BM25 +
bge-small embeddings + a MiniLM cross-encoder, all run with ONNX Runtime from
fp16-stored weights (identical results to PyTorch). Stanza still needs torch.

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
| v4 blind (60, changes of state) | not run yet | | |

Blind sets (`cases_v2/v3/v4.jsonl`) are numbers-only for the developer: never
read their case text or outputs. An agent audits new judge flags and reports
only verdicts. Dev sets you may read and tune on:
`cases_dev_paraphrase.jsonl` (`tools/paraphrase_dev.py`, 51/64 with
candidates) and `cases_dev_stale.jsonl` (`tools/stale_dev.py`, old line still
current 21/50, new state found 33/50).

Product harnesses: `tools/dogfood.py --v3` (24/26 rank-1, 12/12 never-mentioned
refused, 8/8 unknown-attribute refused), `tools/scale_test.py` (refusals hold
at 1,526 facts), `tools/refusal_report.py` (all cells pass).

LoCoMo (`bench/locomo`): retrievals done for all three systems on test
conversations 2-9 (sourcedrecall pinned at 3c6b0a7); reader+judge answers
partial (RAG 702/1307, others not started). Conversations 0-1 are dev.

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

Tests:

    cd ~/jpwork/sdr && ../sdr-venv/bin/python -m pytest -q rgx experiments/p2 tools server

The Mac is shared with Chris: never touch processes you did not start, do not
pull models into his Ollama app. Our llama_cpp server (qwen3-14b GGUF) runs on
127.0.0.1:8090 (`bench/locomo/mac_serve.sh`); use it for any LLM reader or judge.

Long jobs: start them detached (`nohup ... &` on the Mac, `setsid nohup` on
WSL) and log to a file; Claude Code sessions here restart often and take their
child processes with them.

## Releasing

Bump `plugins/sourcedrecall/.claude-plugin/plugin.json` version, commit, tag
`sourcedrecall-v<version>`, push the branch and the tag. A fresh install from
the tag: `CLAUDE_PLUGIN_ROOT=plugins/sourcedrecall CLAUDE_PLUGIN_DATA=<scratch>
plugins/sourcedrecall/bin/sourcedrecall-run install`. Scan the diff for secrets
and real-conversation text before pushing (the repo is public).

## Open items, in order

1. Run the full suite on the Mac for 515c2fa (browser) and release 0.4.5.
2. LoCoMo: finish reader+judge on the Mac (`bench/locomo/run_test.sh answer`
   pointed at the Mac's own 127.0.0.1:8090), then `run_test.sh score`.
3. Blind v4 (changes of state): run RAG + sourcedrecall (+ Mem0 later); the
   judge needs an OpenAI-compatible endpoint on the Mac or Ollama.
4. Stale facts remain the main false-memory source (blind v3 stale 6/8).
5. Parser distillation to drop torch (~0.8 GB), only if it matches Stanza on
   every test.
6. Codex CLI importer (format undocumented; stub).

## Rules carried from JP

Local models only for judging; no paid APIs. Subagents on sonnet or haiku.
Plain user-facing text. Commit at stage boundaries; push after each.
Labels must be screened against audited data before they are shown as trust
signals (JP's validity protocol; notebook e288 and later).
