# Handover: sourcedrecall (product track)

Last updated 2026-10-05. Branch `product-p2`, pushed to github.com/synthiumjp/resonance-gate (public, research) and as `main` to github.com/synthiumjp/sourcedrecall (PRIVATE until launch; push both: `git push origin product-p2 && git push sr product-p2:main`, tags to both).
Latest release tag: `sourcedrecall-v0.5.2` (installs from resonance-gate).
Since then (unreleased, on the branch): list questions read 16 messages,
preferences across projects, wider standing instructions, the opt-in notes
mode, notes in MEMORY.md and the browser, native Windows paths (untested),
CHANGELOG. Full suite on the Mac: 1081 passed, 3 skipped.

## What it is

A local memory for AI agents that never calls a language model to store
anything (unless the user turns on notes mode, below). It keeps the user's
messages as written, with dates, and a deterministic parser (Stanza 1.14.0,
pinned, + the `rgx` rules) reads them for facts. For a question the block an
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

Mac worktrees: ~/jpwork/sdr (committed code, benches), sdr-dev, sdr-wheel
(patches under test), sdr-notes, sdr-notes2 (notes-mode runs). Before a
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

## Open items, in order

1. Notes mode after its fixes (grounding, change marking): blind v3/v4 and
   LoCoMo dev queued on the Mac (~/jpwork/notes2.sh); the notes-mode LoCoMo
   test (before the fixes) is running (~/jpwork/notes_blind.sh). Then the
   test once more with the fixes, and audits.
2. Launch (JP): the repo goes public, then tag the next release (the
   installer clones synthiumjp/sourcedrecall); PyPI upload needs JP's
   account; JP reads docs/launch/WRITEUP_DRAFT.md; a week of real use.
3. Multi-hop (53.6% vs Mem0 61.9% default; notes mode closes much of it on
   dev). Deterministic tricks tried and measured (e300, e306): only breadth
   helped.
4. Install weight (~1.6 GB, PyTorch for the parser): a lighter parser
   runtime, only if it matches Stanza on every test.
5. Native Windows: test the installer on a real Windows machine.
6. Codex CLI importer (format undocumented; stub).

## Rules carried from JP

Local models only for judging; no paid APIs. Subagents on sonnet or haiku.
Plain user-facing text. Commit at stage boundaries; push after each.
Labels must be screened against audited data before they are shown as trust
signals (JP's validity protocol; notebook e288 and later).
