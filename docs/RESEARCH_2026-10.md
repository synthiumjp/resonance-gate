# Recent work on agent memory (survey of 2026-10-09)

A survey made by an agent with web search after the held-out v6 result,
aimed at the three problems v6 left open (pasted text, advice, plans) and
at how results should be reported. Items marked "checked" were read at the
primary source (the arXiv abstract page or the repository) on 2026-10-09;
the rest come from search results or secondary roundups and are not
verified.

## Directly on the open problems

Pasted text and memory poisoning:
- MemSecBench (arXiv 2607.27080, 2026-07-29; checked). 310 cases from 48
  contexts; follows a malicious instruction from storage to a later action
  to repair. Carriers: user messages (43.5%), workspace files, tools,
  external content (web pages, email). Backends: a file store, Mem0,
  Mem0-Graph, A-MEM. No code or data link on the abstract or HTML page.
- From Untrusted Input to Trusted Memory (arXiv 2606.04329, 2026-06-03,
  revised 06-18; checked). MPBench: four write channels, six attack
  classes, on OpenClaw and Hermes agents; "agents designed to write and
  retrieve memory more aggressively are more exploitable". No code link.
- Utility Under Attack (arXiv 2608.21230, 2026-08-21; checked).
  Provenance-weighted retrieval was "statistically indistinguishable from
  no defense (p=0.80)"; only excluding untrusted sources helped, at a cost
  to utility. Proposes bounded occupancy at retrieval instead of additive
  penalties. Harnesses and corpora said to be released (link not on the
  abstract page). This matches v6: a "pasted in" label did not stop the
  reader. A fix has to change what the reader sees.
- Not checked: InjecMEM (2608.23471), "When Agents Remember Too Much"
  (2607.06595), MemAudit (2605.23723), MemLineage, SMSR, survey 2604.16548.

Speaker attribution: SpeakerMem-R1 (2609.26780) stores speaker-labelled
verbatim messages with derived states, close to this design; "Who Said
What" (2609.39344); 2602.01313 reports multi-hop accuracy of 26% under
multi-party attribution with oracle evidence. Not checked. Nothing found on
detecting pasted email or documents inside a user's message.

Advice and personalisation:
- Know It, Act on It (arXiv 2607.29433, 2026-07-31; checked). 16 systems,
  five memory architectures, 1,000 preferences at three strengths: agents
  recall a preference but often do not act on it in a paired scenario; the
  gap is widest for health and therapy preferences. Our v6 advice misses
  (the mention in the block, the reader refusing) are this failure.
- BenchPreS (2603.16557): when not to apply a preference; the control for
  any advice fix. Not checked.

Plans against changes that happened: nothing found that targets it. The
nearest is Ground Truth First (2607.21962, not checked): facts with validity
intervals generated before the text, and rankings that change with history
length.

## Benchmarks and how to report

- LoCoMo audit (Penfield Labs, 2026-04-04, github.com/dial481/locomo-audit,
  commit 9493fb4; checked). 99 of 1,540 gold answers wrong (ceiling 93.6%);
  80 in our test conversations 2-9. With gpt-4o-mini and the "be generous"
  judge prompt (the one we use), deliberately wrong answers were accepted
  10.6% of the time when specific and 62.8% when vague but on topic. Our
  numbers without the 80: `LOCOMO_AUDIT` in `bench/locomo/score.py`
  (README). Our judge on the same wrong answers: `bench/locomo/judge_stress.py`
  (queued). The audit files are CC BY-NC and are downloaded, not copied
  (`bench/locomo/fetch_audit.sh`).
- agent-memory-bench (github.com/GiulioDER/agent-memory-bench; checked).
  Pre-registered, 34 coding tasks graded by execution, no LLM judge;
  Claude Code memory layers plug in as plugins, MCP servers or hooks.
  Current run (deepseek-v4-flash, 26 tasks): no arm, including two memory
  products and a length-matched placebo, beat no memory (baseline 0.577,
  placebo and the "recall" server about 0.659, every interval includes
  zero). sourcedrecall could be entered; runs need a paid agent model.
- LongMemEval-V2 (2605.12493): web-agent trajectories with state tracking
  and premise awareness. MIST (2606.10949): memory raising sycophancy by
  storing misconceptions without their correction. Not checked.
- Published LoCoMo numbers now reach 85-94% (Zep, EverMemOS, Agent Zero
  Memory 2608.29606) with large or agentic readers; the audit shows the top
  ones exceed what a correct answer key allows in some categories. Ours
  must stand next to the reader, judge and harness used.

## Small models and local-first

- MemReader (2604.07877): a distilled 0.6B extractor beating a GPT-4o-mini
  extractor in several settings. Prior art for the notes models; cite it.
- LightMem (2604.07798), Agent Memory Distillation (2608.07169: a 1.7B
  student uses injected memories poorly). Not checked.

## Built-in memory in the assistants

Claude's chat memory reached all plans in March 2026 with an import tool in
May; Gemini imports from ChatGPT and Claude (March); ChatGPT announced
background curation ("Dreaming", June). All summarise; none keeps the
user's words. Secondary sources only.

## What follows for this project

1. Pasted text: keep pasted material out of the user's quoted words in the
   block (shown apart, attributed in the line itself), not a label added
   to a quoted line; measure on a new set, then on MemSecBench or MPBench
   if their data is released.
2. Advice: a paired recall-then-apply probe in the next held-out set, with
   BenchPreS-style controls for over-application.
3. Report LoCoMo with the audit removed and our judge's measured leniency.
4. A plans-against-changes set of our own; nothing public exists.
5. Coding claims stay modest: the one execution-graded coding benchmark
   found no memory system better than none.
