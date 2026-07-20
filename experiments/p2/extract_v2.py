"""p2 extractor v2. New prompt, same pinned model (SmolLM3-3B Q4_K_M).

WHY. The frozen `write_path.EXTRACT_SYSTEM` specifies "relation is a short
lowercase verb phrase like: works at, lives in, was born in, manages, reports
to, is married to, is a sibling of, studied at". That schema is inherited from
the synthetic E3/E5 research corpus, and on real conversation it produces TWO
failures that are actually one bug:

  UNDER-EXTRACTION on the spans that matter. Measured on 39 LongMemEval
  knowledge-update instances, extracting from the gold-evidence spans
  themselves, only 5/39 yielded any fact surviving gate+scope. It sees nothing
  in "I set a personal best of 27:12", "I've tried four Korean restaurants",
  "Rachel moved to the suburbs" -- because none of those are workplace,
  residence or kinship facts.

  OVER-EXTRACTION of junk elsewhere. Given a span it has no schema for, it
  falls back on its own few-shot examples: a dairy-farming conversation
  produced (Dana | works at | Orion Foods) and (Nina Vogel | was born in |
  Verona), verbatim from the prompt.

Both follow from a relation inventory too narrow for the content. v2 widens
the inventory and attacks the leak directly.

CHANGES, each targeting a measured failure:
  1. No closed relation list. The relation is whatever verb phrase the
     utterance uses.
  2. Explicit coverage of what the frozen prompt omits: quantities, counts,
     measurements, times and dates, events that happened, states, possessions,
     preferences, and facts about OTHER people the speaker mentions.
  3. A hard anti-leak rule -- every argument must be copied from the
     utterance. This is aimed squarely at the few-shot regurgitation.
  4. Examples use placeholder-ish names and are structurally diverse, and the
     instruction to copy from the utterance is repeated after them, so the
     examples are less available as fallback content.
  5. Conservatism on hedges/questions/negation is KEPT -- the gate's modality
     stage depends on those not being silently normalised away, and that part
     was working.

The frozen `write_path.extract_triples` is left untouched so the research
artifact stays reproducible and so v1/v2 can be compared on the same
diagnostic (`run_updates.py`), which is the baseline this must beat: 5/39.
"""

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_R = os.path.dirname(os.path.dirname(_HERE))
for _p in (_R, f"{_R}/substrate", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

EXTRACT_V2 = """You extract factual statements from one utterance of a conversation, as triples.

Output ONLY lines of this exact form, nothing else:
(subject | relation | object)

WHAT TO EXTRACT. Any fact the speaker directly asserts about themselves, about people \
in their life, or about things they own or do. This includes:
- quantities and counts:  "I've tried four Korean restaurants"
- measurements and times: "I set a personal best of 27:12"
- events that happened:   "I got back from a hike today"
- states and situations:  "my apartment is 20 minutes from my old place"
- possessions:            "I bought a 50mm prime lens"
- preferences:            "I prefer morning appointments"
- other people:           "Rachel moved to the suburbs", "my mum had surgery"
- work, home, family, study, health, money, schedule

DO NOT EXTRACT:
- questions ("do you know any good detailers?")
- hedged or uncertain statements ("I think", "might", "maybe", "not sure")
- hypotheticals ("if I moved to Boston...")
- plans and intentions ("I'm thinking of moving", "I'll check the website")
- negations ("I don't work there any more")
- things someone else claimed ("my friend says...")
- general knowledge with no connection to the speaker ("anthropology is the study of \
human beings", "Heidegger has two planes of thought")
- the assistant's suggestions or explanations
If the utterance contains no such fact, output exactly: NONE

RULES ON THE TRIPLE ITSELF:
- COPY the subject and object from the utterance. NEVER output a name, place or \
organisation that does not appear in the utterance. If you cannot find the argument in \
the text, do not emit the triple.
- subject is a person or thing: "I", "my sister", "Rachel", "my road bike"
- relation is a short verb phrase taken from the utterance
- object is what the relation points at, kept short
- one fact per line; several facts in one utterance give several lines

Examples:
"I've tried four different Korean places so far." -> (I | have tried | four Korean restaurants)
"My sister Priya just started at a hospital in Leeds." -> (Priya (sister) | started at | a hospital in Leeds)
"Ran the 10k in 52:30 on Sunday, chuffed with that." -> (I | ran the 10k in | 52:30)
"Do you know if the shop is open?" -> NONE
"I reckon I might switch banks at some point." -> NONE
"My old flat was closer to work than this one." -> (my old flat | was closer to work than | this one)

Remember: every subject and object must be copied from the utterance itself."""

_TRIPLE_RE = re.compile(r"^\(\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\)$")
_HEDGE = re.compile(r"\b(i think|i heard|might|maybe|used to|would|doesn'?t|don'?t|"
                    r"no longer|any ?more|probably|wonder|hoping|planning|thinking of)\b",
                    re.IGNORECASE)


def extract_triples_v2(utterance, max_tokens=128):
    from llm import generate
    raw = generate(EXTRACT_V2, f"Utterance: {utterance}", max_tokens=max_tokens,
                   temperature=0.0)
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.upper() == "NONE":
            continue
        m = _TRIPLE_RE.match(line)
        if not m:
            continue
        t = (m.group(1), m.group(2).lower(), m.group(3))
        if any(_HEDGE.search(x) for x in t):
            continue
        if t not in out:
            out.append(t)
    return out
