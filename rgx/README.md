# rgx — deterministic memory extraction

Extract durable facts from dialogue with **no LLM at extraction time**.
A dependency parse plus a person-shift transformation; every record carries
the turn it came from.

```python
from rgx import Extractor

ex = Extractor(owner_name="Martin Mark")
for r in ex.extract(dialogue, session=3):
    print(r.kind, r.text, "<-", r.role, "turn", r.turn, "q=%.2f" % r.quality)
```

```
attr    Martin Mark's name is Martin Mark          <- user turn 0
event   Martin Mark lives in Columbus              <- user turn 0
event   Martin Mark does not like boxing           <- user turn 0
event   Martin Mark has been reflecting on
        Martin Mark's career lately                <- assistant turn 1
```

## Measured

HaluMem-Medium, held-out user, scored by the benchmark's own judge harness:

| extractor | recall |
|---|---|
| **rgx (0 model calls)** | **0.4609** |
| prompted 14B | 0.2122 |

+24.9pt, McNemar exact p = 4.8e-23. Precision and a second user are still
being measured — see `docs/EXPERIMENT_LEDGER.md`, which records what failed
as well as what worked, including six instrument defects found along the way.
Five of them flattered the results.

## What it will not do

- **Invent content.** Every content word must trace to the source turn. A slot
  *name* may come from the schema; a *value* may not.
- **Invert a fact.** Negation is preserved. `"I don't like boxing"` is never
  stored as `"does like boxing"` — a bug that shipped here for a while and is
  invisible to token-overlap metrics, since the inverted sentence shares every
  content word with the true one.
- **Emit a name it was not given.** Records are written in the third person and
  the owner's name is substituted deterministically.
- **Call a model.** A model may *check* or *repair* afterwards; it does not
  write the memory.

## Install

```
pip install stanza
python -c "import stanza; stanza.download('en')"
```

CPU only. ~0.16 s/sentence.

## Why a parser rather than an LLM

The transformation is a **person shift** — first person to third, with verb
agreement, pronoun shift inside the span, and a small lexicon mapping surface
expressions to slot names. That is morphology and dependency structure, not
semantics. On this benchmark a prompted 14B was being paid to do agreement.

Parser choice matters: spaCy's `en_core_web_sm` scores **61.45% LAS** on
conversational data against Stanza's **85.19%** (CAIT, arXiv:2605.19718).
Swapping to UD was worth +3pt of judged recall on its own.
