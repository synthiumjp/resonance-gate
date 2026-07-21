"""p2 LLM profile extractor: the realtime, per-turn replacement for the model-free
extractors that entry 64 showed hit their ceiling on real chat.

Entry 64 verdict: the belief/commensurability MACHINERY is sound; the model-free
EXTRACTION manufactures junk on real research/engineering chat ("keep digging" read
as storage, "§7.4.1" as an employer). This swaps in an LLM extractor that
understands what IS a stable personal fact vs a metaphor/instruction/technical
token, feeding the SAME belief memory.

REALTIME by design: one small-context call per user turn (no history in the
prompt), so it runs async while the assistant is already generating its reply, and
the belief state updates incrementally. Latency per call is the realtime budget and
is measured by the runner. qwen3:14b here is the QUALITY probe; if quality holds, a
smaller/faster model is the realtime target.

Output contract: a short JSON array of {attribute, value} STABLE self-facts.
"""

import json
import re

from consistency import get_llm

# canonical attribute synonyms so mentions MERGE into one slot and corroborate
# ("residence"/"location"/"city" -> location). Unknown attrs pass through.
_CANON_ATTR = {
    "residence": "location", "location": "location", "live": "location",
    "city": "location", "based": "location", "home": "location", "hometown": "location",
    "employer": "occupation", "work": "occupation", "job": "occupation",
    "occupation": "occupation", "role": "occupation", "profession": "occupation",
    "career": "occupation", "title": "occupation",
    "current_tool": "tool", "tool": "tool", "tools": "tool", "software": "tool",
    "uses": "tool", "using": "tool", "tech_stack": "tool", "stack": "tool",
    "education": "education", "degree": "education", "studying": "education",
    "study": "education", "qualification": "education",
    "ongoing_project": "project", "current_project": "project", "project": "project",
    "building": "project", "working_on": "project", "startup": "project",
    "relationship": "relationship", "family": "relationship", "partner": "relationship",
    "spouse": "relationship", "kids": "relationship", "children": "relationship",
    "possession": "possession", "possessions": "possession", "owns": "possession",
    "device": "possession", "hardware": "possession",
    "hobby": "hobby", "interest": "hobby", "interests": "hobby",
    "social_media_platform": "social_media", "social_media": "social_media",
}


def canon_attr(a):
    return _CANON_ATTR.get(str(a).lower().strip(), str(a).lower().strip())

SYSTEM = """Extract STABLE personal facts the user states about THEIR OWN life from \
one message. A stable fact is something that could go on their profile: where they \
live, their job/role/employer, tools or software they regularly use, routines/habits, \
relationships/family, possessions, an ongoing project or plan of THEIRS.

Output ONLY a JSON array, one object per fact:
[{"attribute": "<short noun, e.g. residence, employer, current_tool, weekly_class>", \
"value": "<short>"}]

STRICT rules -- when unsure, output fewer:
- ONLY first-person facts about the USER's own life. Not about code, math, research \
content, the assistant, or other people's situations.
- IGNORE instructions to the assistant, quoted text, code, file paths, section refs \
(like §7.4.1), numbers/metrics, and technical jargon.
- IGNORE metaphors and progress-talk: "keep digging", "moving to phase 5", "keep \
building", "going in circles" are NOT facts.
- IGNORE hypotheticals, questions, and things they might do.
- If the message states no stable personal fact, output exactly: []"""


def extract_profile_facts(text):
    """[{attribute, value}] stable self-facts from ONE user turn. Realtime: single
    turn, no history, small output."""
    out = get_llm().create_chat_completion(
        messages=[{"role": "system", "content": "/no_think " + SYSTEM},
                  {"role": "user", "content": text[:1600]}],
        max_tokens=200, temperature=0.0)
    txt = out["choices"][0]["message"]["content"]
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.DOTALL).strip()
    m = re.search(r"\[.*\]", txt, re.DOTALL)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except Exception:
        return []
    facts = []
    for f in arr:
        if isinstance(f, dict) and f.get("attribute") and f.get("value"):
            a = re.sub(r"\s+", "_", str(f["attribute"]).strip().lower())[:30]
            v = str(f["value"]).strip()[:80]
            if a and v:
                facts.append({"attribute": a, "value": v})
    return facts
