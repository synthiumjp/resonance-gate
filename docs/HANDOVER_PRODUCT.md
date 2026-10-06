# Handover: sourcedrecall (product track)

Last updated 2026-10-06. Branch `product-p2`, pushed to github.com/synthiumjp/resonance-gate (public, research) and as `main` to github.com/synthiumjp/sourcedrecall (PRIVATE until launch; push both: `git push origin product-p2 && git push sr product-p2:main`, tags to both).
Latest release tag: `sourcedrecall-v0.5.2` (installs from resonance-gate).
Since then (unreleased, on the branch; docs/CHANGELOG.md): no PyTorch
(stanza_ort), list questions read 16 messages, preferences across projects,
wider standing instructions, opt-in notes mode, pasted-text guard, ChatGPT /
Claude.ai importers, Codex / Gemini CLI / Cursor capture, parser batching.
Full suite on the Mac: 1118 passed (Stanza backend), 1120 (stanza_ort).
Notebook up to e312. Rules and their evidence: docs/HOW_IT_READS.md. JP's goal (2026-10-05): a usable, credible open-source
system -- every claim reproducible, local models only (GPT-4o-mini declined
twice).

## What it is

A local memory for AI agents that never calls a language model to store
anything (unless the user turns on notes mode, below). It keeps the user's
messages as written, with dates, and a deterministic parser (Stanza 1.14.0's
English models + the `rgx` rules) reads them for facts. The models run on
ONNX Runtime through `stanza_ort` (repo root; tools/stanza_ort: convert,
parity, MODEL_CARD), identical parses to Stanza on PyTorch on 7,755 texts;
setup downloads them from huggingface.co/synthiumjp/sourcedrecall-parser-en
(sha256 in setup_models.py). `RGX_PARSER=stanza` + the `[stanza]` extra uses
Stanza itself. Install ~0.9 GB, ~1 minute. For a question the block an
agent gets is the user's own dated messages, oldest first, with the question
each answered: found through the parser's facts and a search over the
messages (BM25 + bge-small + MiniLM cross-encoder, ONNX Runtime). The parser
decides what is known, routes to messages, pulls in the message that replaced
an ended fact, and adds notes only where they matter ("no longer true", "said
in passing", "may have changed since", "home country: Sweden"). Facts about a
project stay in it; sentences about the person (preferences, "I always use
tabs") travel; standing instructions ("never add comments to my code") lead
every session's summary. Embeddings are kept on disk. The summary at session
start (no question) still lists the parser's facts.

Notes mode (opt-in, `SOURCEDRECALL_NOTES_URL`/`_MODEL`, server/sourcedrecall/
notes.py): the user's own local model writes short notes once per stored
conversation; each must be grounded in the user's own words; shown labelled.

Delivery: a Claude Code plugin (`plugins/sourcedrecall`), an MCP server (12
profile_* tools; the four rg-1.1 triple tools only with
SOURCEDRECALL_LEGACY_TOOLS=1), a command line (`sourcedrecall-memory`), a
self-contained wheel (`tools/build_wheel.py`, not uploaded).

## Where things stand (numbers; same local reader and judge, qwen3-14b, for every system)

LongMemEval-S retrieval (no LLM; bench/longmemeval): session recall_any@5
98.4% over all 500 (bge-small 96.8, BM25 93.4; agentmemory publishes 95.2,
MemPalace 96.6). Weakest type: single-session-preference 90.0 (bge 96.7).

Head-to-head with agentmemory 0.9.29 and ai-memory 2.5.2
(bench/false_memory/HEAD_TO_HEAD.md, audited, one rule): v4 old-as-current
2 / 5 / 7 (RAG 7) of 44; coding false memories 0 / 2 / 6 (3) of 51;
projects 0 / 9 / 4 (3) of 32. Tools in ~/jpwork/h2h on the Mac.

Notes mode on the LoCoMo TEST (held out), notes before the grounding fix:
72.1% (Mem0 64.6%), multi-hop 60.3 (61.9), 468 calls, 1234 context tokens.
With the fix: dev 69.5% (v1 73.8% -- mostly reader/judge noise, the notes
are near-identical; ~/jpwork/noise.sh measures it), blind v4 2/44, v3
0/30. Test with the fix and at Mem0's context size: ~/jpwork/notes3.sh.

LoCoMo test (convs 2-9, 1307 q), default mode at f078bf4: 64.7% (Mem0 2.2.1
64.6%, RAG 56.6%); multi-hop 53.6 (61.9, 39.3), temporal 56.2 (37.2, 49.6);
845 context tokens; 0 model calls at ingest (Mem0 941). LoCoMo dev (convs
0-1, 233 q): default 67.8% (RAG 62.2%); notes mode 73.8% (76 model calls).

Blind false-memory sets, answer view (a reader answers from each system's
memory; the answer is judged), audited:
  v4 changes of state: old state given 2/44 (RAG 7/44), new 42/44 (36/44),
     4B reader 2/44 (5/44); notes mode (before its fixes) 3/44.
  v3: false memory 0/30 (RAG 0, Mem0 2), controls 23/23; notes mode (before
     its fixes) 2/30, both assistant claims -- fixed by grounding (49561c4).
Coding sets with a background of 120 debugging sessions (held out, audited):
  out-of-date or never-confirmed setups 0/51 (RAG 3/51); new setup 14/14
  (11/14); another project's fact offered 0/13 (RAG 2/13); preferences from
  another project 4/8 (RAG 4/8) before the personal-sentence change, which
  took held-out controls 8 -> 10/13 (unaudited).

Sets: blind (numbers only, agent audits): cases_v2/v3/v4, cases_code_blind,
cases_projects_blind. Readable (tune on): cases.jsonl (v1),
cases_dev_paraphrase, cases_dev_stale, cases_dev_stale2, cases_dev_code,
cases_dev_projects, cases_dev_prefs. Background noise: distractors_code.jsonl
(FM_DISTRACTORS, FM_DISTRACTOR_COPIES=2). Rerunning: bench/REPRODUCE.md.

Mac worktrees: ~/jpwork/sdr (committed code, benches), sdr-dev, sdr-wheel,
sdr-test, sdr-ort, sdr-lab (patches under test), sdr-fuse (LongMemEval ran
from it), sdr-notes, sdr-notes2 (notes-mode runs), sdr-screen (label
screening baseline). Other Mac dirs: h2h (agentmemory, ai-memory, standalone
Node), h2h_audit (blind audit dumps: never read), lme (LongMemEval data),
stanza_ort (the build and parity corpus), rerank (reranker comparison),
hfparser (the uploaded model archive). Before a
checkout or pull, delete result directories that are now committed.

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

## Open items, in order (2026-10-06)

1. A small notes model that needs no server (JP: "we need something we
   don't have to actually serve"; "surely a specialised model"). Qwen3-0.6B
   fine-tuned on Qwen3-14B's grounded notes over LongMemEval sessions, int4
   ONNX (~0.5 GB), run in-process by notes.py on onnxruntime-genai. Work in
   ~/jpwork/distil on the Mac (notebook e312). Bar on LoCoMo dev: 1.7B 70.0%,
   multi-hop 26/43; no notes 68.2% (23). Then: blind v3/v4 false memory,
   the held-out LoCoMo test, publish to HF (synthiumjp/sourcedrecall-notes-en)
   and set NOTES_ARCHIVE/NOTES_SHA256 in setup_models.py. Default on or off
   is JP's decision.
2. The held-out LoCoMo test with 1.7B notes (~/jpwork/test_1p7b.sh).
3. JP reviews docs/PREREG_HELDOUT_V5.md; an agent builds held-out set v5
   (numbers only to the developer); one confirmatory run.
4. One clean re-measurement of every headline number on the release commit.
5. Launch (JP): a week of real use; Codex / Gemini / Cursor capture in the
   real apps; native Windows; the repo goes public, then tag and PyPI; the
   write-up rewrite (WRITEUP_DRAFT is out of date) and a demo.
6. JP's confidence work: re-screen labels each change; a validity screen of
   the notes model is the natural research piece.

## Rules carried from JP

Local models only for judging; no paid APIs. Subagents on sonnet or haiku.
Plain user-facing text. Commit at stage boundaries; push after each.
Labels must be screened against audited data before they are shown as trust
signals (JP's validity protocol; notebook e288 and later).
