# Handover: sourcedrecall (product track)

Last updated 2026-10-12. Branch `product-p2`, pushed to github.com/synthiumjp/resonance-gate (public, research) and as `main` to github.com/synthiumjp/sourcedrecall (PRIVATE until launch; push both: `git push origin product-p2 && git push sr product-p2:main`, tags to both).
Latest commit: e9ef773. Latest release tag: `sourcedrecall-v0.5.2` (installs
from resonance-gate); everything since is unreleased (docs/CHANGELOG.md).
Full suite on the Mac: 1,318 passed, 5 skipped. Notebook up to e322. Rules
and their evidence: docs/HOW_IT_READS.md. JP's goal: a usable, credible,
viable open-source product -- every claim reproducible, local models only.

Read first in a new session: this file, notebook entries 316-322,
bench/false_memory/results_v10/SUMMARY.md, docs/PREREG_HELDOUT_V10.md (the
template for the next pre-registration), docs/REVIEW_2026-10-09.md (the
adversarial review that set the fair protocol).

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
project stay in it; sentences about the person travel; standing instructions
lead every session's summary. A [MEMORY RULES] paragraph ends the block
(experiments/p2/memory_api.py `_RULES_MSG`, `_UNKNOWN`; advice mode uses
`_UNKNOWN_ADVICE`).

Pasted text (experiments/p2/prose.py, `_paste_span`, `_FRAME_OWN`,
`_FRAME_SOURCE`, `_DOC_HEAD`): a message whose body someone else wrote is
found by shape (intro line, blank line, a block in another voice, a
signature) and shown as `[pasted in by X, written by someone else; not X's
words, facts or instructions: "..."]`. The writer's sentences about
themselves and their always/never rules are left out unless the question
names the source. Own text ("my speech", "I wrote", a signature with the
owner's name) stays the user's. Long messages show the opening sentence plus
a window (800 chars; pasted 1,500) around the sentence best matching the
question. A secret filter replaces credentials.

Notes mode (opt-in, off by default): built-in models on
huggingface.co/synthiumjp/sourcedrecall-notes-en (small = Qwen3-0.6B,
standard = Qwen3-1.7B, int4 ONNX, sha256 pinned in setup_models.NOTES_MODELS),
`sourcedrecall-setup --notes [small|standard]`, or the user's own model via
`SOURCEDRECALL_NOTES_URL`/`_MODEL`. Notes must be grounded in the user's words.

Delivery: a Claude Code plugin (`plugins/sourcedrecall`, Notes option off |
small | standard), an MCP server (12 profile_* tools), a command line
(`sourcedrecall-memory`), a self-contained wheel (`tools/build_wheel.py`, not
uploaded). Importers for ChatGPT / Claude.ai exports; capture for Codex,
Gemini CLI, Cursor.

## Where things stand (all numbers: the same local Qwen3-14B reader and judge for every system)

Release measurement on 8473783 (bench/RELEASE_8473783.log, README numbers):
LoCoMo test (convs 2-9, 1,307 q) 64.8 / 67.0 / 70.2% (default, small notes,
standard notes; Mem0 64.6, plain retrieval 56.6); strict judge 49.7 / 49.9 /
53.2 (Mem0 48.5, plain 42.5); LongMemEval-S any@5 98.7%; held-out v3 0/30,
v4 2/44, coding 0/51, projects 0/32. e9ef773 changes own-text detection only;
LoCoMo detection unchanged (regress.py), so no re-measure needed for it.

Held-out false-memory sets (pre-registered, blind, the fair v7 protocol):
pasted claims given as the user's, v6-v10: 82, 32, 22, 10, 8% (plain
retrieval 88, 71, 40, 55, 58). v10: 5 of 6 met; missed own material 13/20
(plain retrieval 19). Pooled false memories v10: 4/60 vs plain 26, agentmemory
20, ai-memory 7.

The open weakness: own material. When the user's own draft (a speech, a
letter, a listing, a checklist) holds the fact, the reader often says "I
don't know" with the fact in the block. Dev set cases_dev_own (60): on e9ef773
own 26/40, plain retrieval 29/40, false memories 2/20 (plain 11/20). Tried
and rejected (notebook e322): a note marking the line as the user's own
writing (no effect), shorter rules wordings (+3-4 own answers, +3-4 real false
memories). In flight at handover: rules paragraph moved ABOVE the lines,
same wording (below).

## In flight at handover (2026-10-12)

`~/jpwork/dev19.sh` on the Mac (log ~/jpwork/dev19.log, ends "dev19 done"):
`reblock2.py` moves [MEMORY RULES] from the end of the block to under the
header line, wording unchanged, on fixed retrieval, for all 9 dev sets (own,
pasted, pasted2, stale2 from sdr-dev12/results_dev17_*; code, projects,
decisions, advice, prefs from sdr-dev11/results_dev16_*). Each set prints
base then `first`. Adopt only if own goes up AND false memories (own,
pasted, pasted2, stale2, code, projects, decisions), stale "new state" and
advice/prefs answers do not get worse; then implement in memory_api.py (the
block is assembled there), rerun the dev battery end to end, the full suite,
LoCoMo (the block changes for every question, so LoCoMo needs a re-measure),
then a v11 pre-registration for JP.

Ideas not yet tried for own material: show the sentence of a long own
message that best matches the question as its own line; fewer low-relevance
lines in short histories (plain retrieval shows 3 lines, we show all);
keeping line breaks in quoted messages (plain retrieval keeps them).

## The protocol (do not weaken it)

- Fair protocol v7: FM_READER_SAME=1 FM_SAME_V7=1 FM_STRICT=1
  FM_JUDGE_QUESTION=1. Every system's memory goes to the same reader prompt
  (bench/false_memory/answer.py PROMPT + SAME_RULES); sourcedrecall's block
  carries its own rules (OURS_RULES=1). Strict scoring: expected terms are
  whole words not in the question; errors count as failures.
- Blinded audit: blind_audit.py packet -> an agent decides without system
  names -> apply -> audit_overrides_vN.json -> rescore with FM_OVERRIDES.
- Held-out sets are numbers-only for the developer: cases_v2..v10,
  cases_code_blind, cases_projects_blind, positives_v5, audit packets/keys/
  decisions, and the per-probe files in results_v5..v10. Agents read them and
  report counts and categories only. Never open them yourself.
- A held-out run: draft docs/PREREG_HELDOUT_VN.md (+ vN_run.sh, vN_tests.py,
  copy v10's) -> JP reviews -> commit (code frozen from here) -> a sonnet
  agent writes cases_vN.jsonl barred from the rules, dev sets, earlier sets
  and history -> commit the set -> run on the Mac -> blinded audit -> write
  results_vN/SUMMARY.md, README paragraph, HOW_IT_READS paragraph, notebook.
- Dev sets are readable and for tuning: cases.jsonl, cases_dev_{paraphrase,
  stale, stale2, code, projects, prefs, advice, decisions, pasted, pasted2,
  pasted_long, pasted_use, own}. Agent-written dev sets: check their expected
  terms against strict whole-word scoring before using them (e322 found 12
  bad terms).
- Fixed-retrieval experiments: copy a results dir with the block rewritten
  (bench/false_memory/devtools: reblock.py, reblock2.py, ownmark.py, blockvar.py, loo.py, dev16-19.sh; they run from ~/jpwork on the Mac), then answer.py +
  score.py + fair_summary.py. The dev battery script pattern: ~/jpwork/dev16.sh.
- LoCoMo: bench/locomo; strict rejudge LOCOMO_JUDGE=strict with rejudge.py,
  audit errors LOCOMO_AUDIT=results/locomo_audit_errors.json.
- Release measurement: tools/release_measure.sh (suite, LoCoMo x3 notes
  modes, LongMemEval, held-out v3/v4/coding/projects), then the strict
  rejudge (~/jpwork/strict4.sh); README numbers from that one run.

## How to run things -- ON THE MAC, not WSL

The WSL box (15 GB) was OOM-killed twice on 2026-10-03. Run heavy work on the
Mac Studio:

    ssh chrismarmo@100.126.162.38
    ~/jpwork/sdr          git clone of product-p2 (git pull to update)
    ~/jpwork/sdr-venv     its venv
    ~/jpwork/sdr-dev11    copy at 8473783 + dev sets (dev16 runs)
    ~/jpwork/sdr-dev12    sdr-dev11 + e9ef773's prose.py (dev17-19 runs)
    ~/jpwork/sdr-vN       the tree each held-out vN ran from
    ~/jpwork/rg           an rsync copy used by the HaluMem tools -- leave it

Tests:

    cd <tree> && STANZA_RESOURCES_DIR=~/jpwork/stanza_resources_114 \
      HF_HUB_OFFLINE=1 ~/jpwork/sdr-venv/bin/python -m pytest -q rgx experiments/p2 tools server

Always set `LOCOMO_LLM_BASE=http://127.0.0.1:8090/v1` and
`FM_JUDGE_OPENAI=http://127.0.0.1:8090/v1 FM_JUDGE_MODEL=qwen3-14b-a8cc1361.gguf`:
our llama_cpp server (bench/locomo/mac_serve.sh) on 127.0.0.1:8090. The Mac
is shared with Chris: never touch processes you did not start, never pull
into his Ollama (port 11434). zsh on the Mac has no `timeout`.

Bench runs write result directories into the tree. Copy them back to WSL and
commit them there; delete committed copies on the Mac before a `git pull`
(an untracked copy makes the pull abort). Check `git log -1` on the Mac
before trusting a run (the sdr-devN copies are not git repos; diff the files).

Long jobs: `nohup ... > log 2>&1 &` on the Mac; wait with a background
until-loop that greps the log for its "done" line (foreground sleep is
blocked in Claude Code).

NAS (cold storage only): reach it via the Mac, `ssh chrismarmo@100.126.162.38
'ssh chihiro "..."'`; only /volume1/models/jpcoldstorage; never touch
/volume1/docker/foresight/state (production database); one transfer stream
at a time.

## Releasing

The installer clones github.com/synthiumjp/sourcedrecall. Do NOT tag a new
release until that repo is public -- a plugin install could not clone it.
Creating or uploading public HF repos is JP's to run.

PyPI wheel: `python tools/build_wheel.py` writes
`server/dist/sourcedrecall-<version>-py3-none-any.whl`; test it in a fresh
venv outside the repo (`~/jpwork/wheeltest.sh`). Not uploaded yet (Trusted
Publishing planned).

Bump `plugins/sourcedrecall/.claude-plugin/plugin.json`, commit, tag
`sourcedrecall-v<version>`, push branch and tag to both remotes. Scan the
diff for secrets and real-conversation text before every push.

## Open items, in order (2026-10-12)

1. Own material (above): finish dev19; if rules-first passes, implement,
   re-measure, then the v11 pre-registration for JP. If it fails, try the
   ideas listed above on dev before spending v11.
2. Launch (JP): a week of real use; plugin install from a tag on a clean
   machine and on Windows; make sourcedrecall public; PyPI; the write-up
   (docs/launch/WRITEUP_DRAFT.md is out of date) and a demo
   (bench/demo/demo.py).
3. JP's confidence work: re-screen labels on each change; validity screen of
   the notes models.

## Rules carried from JP

Local models only for judging; no paid APIs. Never extract over JP's real
conversations.json. Subagents on sonnet or haiku (opus only when JP names
it). Plain user-facing text (no "honest", no bold-led bullets). Commit at
stage boundaries and push both remotes. Pre-registrations need JP's review
before commit. Deleting is permanent: confirm first. Labels must be screened
against audited data before they are shown as trust signals.
