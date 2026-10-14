# Handover: sourcedrecall (product track)

Last updated 2026-10-12 (evening). Branch `product-p2`, pushed to github.com/synthiumjp/resonance-gate (public, research) and as `main` to github.com/synthiumjp/sourcedrecall (PRIVATE until launch; push both: `git push origin product-p2 && git push sr product-p2:main`, tags to both).
Latest commit: see `git log` (the relevance cut is d89d830). Latest release
tag: `sourcedrecall-v0.5.2` (installs from resonance-gate); everything since
is unreleased (docs/CHANGELOG.md). Full suite on the Mac: 1,331 passed, 5
skipped. Notebook up to e324. Rules
and their evidence: docs/HOW_IT_READS.md. JP's goal: a usable, credible,
viable open-source product -- every claim reproducible, local models only.

JP's aim (2026-10-12): a lightweight, linguistics-first memory that competes
with heavier systems, LLM-agnostic and freely available. Judge every change
to what the reader sees on two local readers of different families
(Qwen3-14B :8090 and Phi-4 :8091 on the Mac) and drop changes that help one
model only.

Read first in a new session: this file, notebook entries 316-324,
bench/false_memory/results_v10/SUMMARY.md, docs/PREREG_HELDOUT_V11.md (DRAFT, uncommitted,
waiting for JP), docs/REVIEW_2026-10-12.md (the second adversarial review;
items fixed and open are listed below), docs/REVIEW_2026-10-09.md.

## 2026-10-15 morning (read this first)

- Parser retrain done (EWT + GloVe only): UD EWT test, gold words, LAS
  88.83 (ours, head repair on) / 88.77 (Stanza ewt_nocharlm) / 90.04
  (shipped combined); UPOS 96.41 / 96.68 / 96.77 (~/jpwork/ud_cmp.py).
  Converted to ~/jpwork/parser_models/ours (no charlm, 40 MB vectors).
  Parity: our training saved `resolve_head_constraints: False` in the
  model config, so Stanza on PyTorch skipped the head repair the pipeline
  does for its own models (key absent = on); stanza_ort always repairs.
  With the key removed (~/jpwork/ewt_train/en_ewt_glove_nocharlm_parser_rhc.pt,
  the file to keep and cite) all 7,755 parity texts are identical. The ONNX
  archive needs no change.
- Running: ~/jpwork/locodev_parser.sh (LoCoMo dev convs 0-1, shipped vs
  ours, tree ~/jpwork/sdr-ours = 0e575db, Qwen 8090; log locodev_parser.log).
  Publish only if ours holds.
- Export reviewed (e7767f6): product CITATION.cff, rgx/README ledger link
  and CI judge-cache deps cut, REVIEW_2026-09-05 dropped, user's name out of
  an rgx comment. Re-export at Mac ~/jpwork/sdr-export2 passes 1,183
  (delete its COMMIT_SRC before committing). Packed size 14 MB. Push waits
  for JP.

## 2026-10-14 afternoon

- First-session fix: the plugin's MCP server is a stand-in
  (plugins/sourcedrecall/bin/setup_server.py) while the install runs, then
  hands over and sends tools/list_changed (b6f3cd1). JP's session had no
  memory tools all day: he restarted during the install, the launcher
  exited, Claude Code cached the failure. clean_install_test.sh now checks
  the handover during a real install.
- HaluMem update + QA (first two users, d6613e0): updates 156/304 against
  plain 96, QA 185/352 against 162; in README and bench/halumem (scores
  only).
- README evidence: the LoCoMo release dirs now hold the d89d830 run the
  README quotes (they had 8473783's); LongMemEval answers in
  bench/longmemeval/answers_75487ec; judge gold check 120/120
  (bench/locomo/JUDGE_STRESS.md).
- Legacy triple tools, service.py and substrate_path.py removed (3d1bd84);
  test_zero_network now guards the profile path.
- Clean product repo: `tools/export_product.py SRC tools/export_keep.txt
  DEST` (run on the Mac on a `git archive`; the keep list came from a
  manifest of what the docs cite). Memory modules
  go to core/, the HaluMem harness to bench/halumem/harness, machine paths
  scrubbed. The export (~/jpwork/sdr-export, a copy at
  ~/sourcedrecall-export on WSL) passes the suite (1,183) and the clean
  install test. NOT pushed: it replaces synthiumjp/sourcedrecall's history
  and waits for JP.
- Parser retrain (licence): depparse restarted on CPU 15:16
  (~/jpwork/ewt_train/dep_only.sh; the 10-13 checkpoint with another tag
  vocabulary had crashed it, moved to stale/). Then convert
  (STANZA_PACKAGES=ours), parity, benchmark, publish, NOTICE.

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

Own material (the v10 miss): on dev the reader refused facts in the user's
own drafts because of the rules paragraph together with the unrelated lines
around the fact (notebook e323: with the fact's line alone it answered,
rules and all). Rejected: rules above the lines (dev19), line breaks kept,
an own-writing note, shorter rules. Adopted (d89d830): the relevance cut in
memory_api `_messages_block` (`RG_MSG_CUT`, default 0.5; "off" shows every
line): with a parser-routed message shown, another message stays if its
bge-small cosine with the question is >= 0.5, it is in the same
conversation, or the parser ties its facts to the routed one; not for
advice, list questions or blocks with pasted text. Dev end to end (Qwen):
own 26 -> 30 of 40, false memories unchanged on all 9 sets (7 of 248),
stale2 unchanged; Phi-4: own 34 -> 33 (plain retrieval 33), FM unchanged.
LoCoMo dev 68.2 -> 67.8%. The cross-encoder version of the cut was
rejected (dropped the messages that changed a fact: stale2 FM 3 -> 7).

Second reader finding: with Phi-4 our block already answered own material
as well as plain retrieval (34 vs 33 of 40) with a quarter of the false
memories (3 vs 13 of 20). The v10 own gap was mostly Qwen3-14B's caution.

Review 2026-10-12 fixes (5c4e691, 124d29b, 210a2ff): Claude Code capture
skipped only sidechain/meta lines, so compaction summaries and every
task notification were stored as the user's words; paste intros naming a
destination ("add this to my notes") or a source plus an own noun ("my boss
sent me this for my review") made pasted text own; "X wrote this" was own;
an unreadable conversations.json was overwritten.

Later that evening, from WSL (ssh to the Mac was refused by the
permission check, so none of these has had the full suite on the Mac yet;
each was tested locally with what runs without the parser):
- 999fd4b secret filter no longer quadratic (3.16): 8 KB 8 s -> 0.2 s,
  output identical on ~50,000 bench strings and 653 repo files;
- 08aee32 secret filter gaps (3.17): next-line values, "my pass is",
  Authorization headers, key=, PGP blocks, five languages' "password";
  no bench text changed;
- 7abb1c4 field lists are not chat logs (3.18): 8 dev spans change, all
  better; LoCoMo not yet checked (run devtools/detect_diff.py with the
  LoCoMo json on the Mac);
- 97845d8 the three ONNX models and both archives pinned to revisions
  with checksums (4.2);
- e45d7e8 release_measure.sh's held-out step under the fair protocol (1.2),
  README 1.1 sentence, table dated 372c05a; ea6ae08 HOW_IT_READS status
  pass (1.10); 0596969 v10 "said it did not know" counts in README and
  SUMMARY (1.8);
- cd5931e MCP tool annotations (3.2, part); 19e1e13 Windows lock waits
  (3.5, not run on Windows); 317484e host details to untracked .hosts.env
  (4.6; old commits on the public remote still hold them).
Still open: the rest of 3.2 (MCP user turns, future dates, existing
conversation ids, rehydrate scope: JP to decide), forget (3.4: HMAC,
titles, substrings, count), the lock held while parsing (3.5), CI (4.4:
needs the Mac venv's package list), rules ablation (2.1), equal-budget
plain retrieval (2.2), audit of expected-term misses (2.3).

## Overnight 2026-10-12/13 (JP asleep; read this first)

Queued on the Mac, each waiting for the one before:
1. release5.log: release re-measure of d89d830 (standard notes, LongMemEval,
   old-protocol held-out step), ends "release measure done".
2. v11.log: held-out v11 (v11_chain.sh -> sdr-v11/bench/false_memory/v11_run.sh),
   ends "v11 done". Then: blinded audit per reader (sonnet agents on the
   packets audit_results_v11*), v11_tests.py, results_v11/SUMMARY.md.
3. night.log (night_chain.sh): strict LoCoMo re-judge of the d89d830 answers;
   the held-out regression step under the fair protocol (W=sdr-release-d89d830);
   HaluMem users 0-1, sdr and plain, from sdr-halumem (post-v11 code),
   official evaluation.py with the local judge (logs halumem_*.log).
4. night2.log (night2_chain.sh): LongMemEval-S knowledge-update then
   temporal-reasoning answer accuracy, plain and sdr (sdr-lme tree,
   bench/longmemeval/lme_answers.py), results in ~/jpwork/lme/answers_*.

Branch post-v11 (pushed to origin, not merged; the v11 freeze): MCP limits,
forget (HMAC, titles, spool, count), titles scrubbed before cut, first-run
message + `sourcedrecall-memory status|last`, block quoting safety, parse
outside the store lock, launcher messages and Python cap, resumable download,
1 GB import cap, MCP descriptions cut and diagnostics hidden, "[MEMORY" typed,
Windows detach, HaluMem and LongMemEval harnesses. Full suite on the Mac on
the branch: 1,368 passed. Merge into product-p2 after the v11 run.

Main branch overnight: CI green (ubuntu, macOS, Windows), NOTICE third-party
section, SECURITY.md, uninstall section, docs/FAQ.md, docs/MARKET_2026-10-12.md,
docs/PLAN_TO_LAUNCH.md (with the Fable review's advice still to fold in).

Done overnight: 1 (bench/RELEASE_d89d830.log, db5e925) and 2 (v11,
results_v11/SUMMARY.md, 13841ff): Qwen 7 of 8 met, pasted 5/40 against 23
and 24; own material 24/30 against plain retrieval 30/30, H4 and so H9
missed with both readers. The 6 own misses are detection: the user's own
first-person writing (diary, speech, statements, ad) marked pasted and its
facts dropped, despite "my draft". Fixing on post-v11 with a new readable
dev set cases_dev_own2.jsonl (agent-written, 30 own writing + 10 others'
writing in the same shapes). The developer saw two Qwen overrides' text by
mistake (recorded in the summary).

Later (03:00-04:10): the fix (fe55586) and dev27 on both readers: own
writing 24 -> 27 of 30, real pasted emails taken as the user's 18 -> 4 of
30, every older dev set unchanged, LoCoMo dev 67.8% unchanged. post-v11
MERGED into product-p2 (1d92020, suite 1,382 passed), pushed to both
remotes. README LoCoMo figures now from d89d830 (+ strict re-judge). The
held-out real-email set end to end, once, on 1d92020: ~/jpwork/realrun.log.
Morning 2026-10-13: held-out real emails end to end once on 1d92020
(7/20 Qwen, 5/20 Phi-4; plain retrieval 15, 16). 8d100ef: an email pasted
alone, introduced in the next message, is pasted (cases_dev_real2 9 -> 3
and 10 -> 3 of 30). JP approved v12; PREREG_HELDOUT_V12.md committed
(27fd77f), code FROZEN until the v12 run. Set being written by an agent
(cases_v12.jsonl; pool ~/jpwork/realpaste/v12_pool.jsonl, also in the
session scratch); validate on the Mac (v12_validate.py output to the agent
unread), commit the set, run `QWEN_URL=http://127.0.0.1:8092/v1 bash
v12_run.sh` from a tree of the set's commit, blinded audit per reader,
v12_tests on both. A second Qwen3-14B server runs on 8092
(~/jpwork/reader3/server.pid, .venv-judge, same flags as 8090) because
HaluMem's scorer holds 8090 for many hours (1,649 accuracy items per user,
~13 s each). Parser licence question explained to JP (options: ask
Stanford, convert on the user's machine, retrain on EWT only, state it).

v12 DONE (09:29; results_v12/SUMMARY.md, 053b07b; README/FAQ eb760d8):
Qwen 7 of 11 met; pasted 12/40 (plain 28, agentmemory 35), real emails
7/20 (plain 14), own 25/30 (plain 29); H1, H4, H10, H11 and H9 missed.
Not a regression (v11 code detects the same on v12); new shapes. Code is
no longer frozen. Proposed to JP: a small learned "someone else's text?"
classifier beside the rules (rules do not converge set by set); trim
HaluMem to the updating and QA parts (accuracy scoring ~13 h per user).
2026-10-14 (JP): README opening approved and in (f9596d8). Fresh, clean
product repo approved: build it from this one with only the product, docs
and the benchmark runs the README and bench/REPRODUCE.md cite (bench/ is
291 MB, 208 MB of it old LoCoMo runs); run the suite and
tools/clean_install_test.sh against it on the Mac; show JP before any push
(it will replace synthiumjp/sourcedrecall's history). JP's real use: the
plugin installs in his WSL Claude Code from this checkout, via
~/.claude/settings.json env SOURCEDRECALL_REPO_URL=/home/jp/rg,
SOURCEDRECALL_REF=sourcedrecall-v0.5.2-local (a LOCAL tag, never push it:
release.yml publishes on sourcedrecall-v* tags); to update his install,
make a new local tag and change SOURCEDRECALL_REF. Launch (public repo,
tag, PyPI) when JP says. Mac: EWT tagger training on CPU, then depparse;
HaluMem update + QA running (~/jpwork/resume2.sh). LongMemEval done: KU
64/78 vs 61, temporal 73/133 vs 64.

JP 2026-10-13 evening: NO test runs on GitHub; all testing on the Mac.
tests.yml and install.yml are manual-only; do not start them. Windows
status from the CI runs before that: install, hooks, briefing and CLI work;
the MCP server answered initialize and tools/list but hung on the first
profile_context (numpy imported lazily inside the running server). Fix
b55ed30 (import numpy/onnxruntime in the main thread first) VERIFIED on
JP's PC (JP approved a Windows test; test folder C:\\Users\\JP\\AppData\\Local\\Temp\\sdr-wintest, run.cmd). Tested too: how
Claude Code on native Windows starts the plugin's MCP command (an
extensionless bash script): it cannot; the session-start hook now shows Windows
users the `claude mcp add ... sourcedrecall.exe` command once (14e9da1). Memory per
server 1.2 GB -> 400 MB (a31c0e0).

2026-10-13 afternoon/evening (JP: "make this a real competitor... free and
great"): launch gate 1 done: tools/clean_install_test.sh + the "clean
install" workflow pass on Linux, macOS and Windows (install 64-111 s, 950
MB; warm question 50 ms; peak RSS 1.2 GB, to trim). The test found the
README example on one line taken as the user's (fixed, 40e9217), unclear
first-run messages (fixed), silent hook input errors (fixed, cf217aa).
The Mac panicked THREE times (11:47, 13:40, 15:33; WindowServer/watchdogd
watchdog) with 3-4 GPU processes or MPS training: no MPS training, at most
two GPU processes (memory file). Now (19:25): EWT tagger on CPU
(~/jpwork/ewt_train/train.sh, then depparse), one Qwen server running
~/jpwork/resume2.sh (LongMemEval temporal resuming at 59/133, then
HaluMem update + QA). LongMemEval knowledge-update: sdr 64/78, plain
61/78; temporal plain 64/133.

The Mac rebooted at 11:47 (cause unknown; it had three Qwen3-14B servers
and Phi-4 up). Restarted with two Qwen servers (8090, 8092) and Phi-4:
~/jpwork/dev29b.sh (dev29's remaining sets, 8092; dev29.log has shapes and
own) and ~/jpwork/resume_chain.sh (LongMemEval resuming, then HaluMem
update + QA, 8090). dev29 done and pushed (610b435 attribution rule +
paste classifier; f071173 parser runtime without a charlm; 8aad8b9 NOTICE:
the current parser archive is non-commercial, CoNLL 2017 vectors).
LongMemEval knowledge-update: sdr 64/78, plain 61/78 (temporal running).
Parser retrain (JP, 2026-10-13): ~/jpwork/ewt_train/train.sh (POS then
depparse on EWT + GloVe, no charlm, MPS); then STANZA_PACKAGES=ours
convert.py -> parity -> parse accuracy and the dev sets / LoCoMo dev with
RGX_PARSER_MODELS pointing at the new archive; publish only if it holds.
Earlier: night2-4 replaced by ~/jpwork/after_chain.sh on 8092 (after.log): v10
reproduction check, demo, LongMemEval KU + temporal. HaluMem (night.log)
keeps 8090.

Night chain step 2 ran under zsh, so the competitors' files were not
copied (word splitting); sourcedrecall's counts are fine: v3 0/30, v4
3/44, coding 0/51, projects 0/32 (fair protocol).

For JP in the morning: the parser model licence question (Stanza's English
models are trained partly on non-commercial GUM/GUMReddit text; NOTICE says
so; options: ask Stanford, convert Stanza's own download on the user's
machine instead of redistributing, or accept and state it); the plan
revision after the Fable review; v11 and the external benchmark results.

## In flight at handover (2026-10-12 evening)

Release re-measurement on d89d830 on the Mac: tree
~/jpwork/sdr-release-d89d830, log ~/jpwork/release5.log (ends "release
measure done"), started 16:22, ~9 h. Then the strict rejudge (adapt
~/jpwork/strict4.sh to the new tree: link ours, keep mem0_strict/rag_strict
from ~/jpwork/sdr-release/bench/locomo/results/strict_release_test_*), copy
the log to bench/RELEASE_d89d830.log, update README numbers from that one
run, fill the release line in docs/PREREG_HELDOUT_V11.md, and give the
draft to JP. release5 started before e45d7e8, so its held-out step (4) is
the old protocol: rerun step 4 alone from tools/release_measure.sh with
W=~/jpwork/sdr-release-d89d830 for the fair-protocol counts. The commits
after d89d830 (secret filter, field lists, pins, annotations, lock) need
the full suite on the Mac before v11's freeze. Phi-4 server: ~/jpwork/reader2/server.pid (ours; stop it when
not needed, `kill $(cat ~/jpwork/reader2/server.pid)`).

Dev trees on the Mac: sdr-dev13 (e9ef773 + score log RG_MSG_LOG, dev20-22,
dev24), sdr-dev14 (detection fixes + cross-encoder cut, dev23), sdr-dev15
(cosine cut, dev25), sdr-dev16 (= d89d830's block code, dev26 and
LoCoMo dev), sdr-head (suite runs; rsync of the working tree). ~/jpwork/sdr
is stale (f078bf4).

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

    source .hosts.env && ssh $SDR_MAC     # .hosts.env is untracked (host details stay out of the public repo)
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

NAS (cold storage only): reach it via the Mac, `ssh $SDR_MAC 'ssh $SDR_NAS
"..."'`; the one folder that may be used, and the one that must never be
touched, are in .hosts.env; one transfer stream at a time.

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

1. Finish the release re-measure on d89d830, then JP reviews
   docs/PREREG_HELDOUT_V11.md (+ v11_run.sh, v11_tests.py, uncommitted);
   commit the reviewed version, then the set, then the run (both readers).
   The open review items above, in the order of the review's top five.
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
