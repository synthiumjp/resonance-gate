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
import os
import re

from consistency import get_llm

# canonical attribute synonyms so mentions MERGE into one slot and corroborate
# ("residence"/"location"/"city" -> location). Unknown attrs pass through.
_CANON_ATTR = {
    "residence": "location", "location": "location", "live": "location",
    "city": "location", "based": "location", "home": "location", "hometown": "location",
    # a person legitimately has MULTIPLE roles -- occupation is MULTI-VALUED, not
    # single. Fold all role phrasings into one multi-valued slot; do NOT collapse
    # to one. (entry 69: the registrant is an SES exec, clinical psychologist,
    # independent researcher AND author -- all real, all kept.)
    "employer": "occupation", "work": "occupation", "job": "occupation",
    "occupation": "occupation", "role": "occupation", "profession": "occupation",
    "career": "occupation", "title": "occupation", "job_role": "occupation",
    "current_role": "occupation", "current_position": "occupation",
    "position": "occupation", "current_interest": "interest",
    "research_interest": "interest", "interest": "interest",
    "current_tool": "tool", "tool": "tool", "tools": "tool", "software": "tool",
    "uses": "tool", "using": "tool", "tech_stack": "tool", "stack": "tool",
    "education": "education", "degree": "education", "studying": "education",
    "study": "education", "qualification": "education",
    "ongoing_project": "project", "current_project": "project", "project": "project",
    "active_project": "project",
    "building": "project", "working_on": "project", "startup": "project",
    "relationship": "relationship", "family": "relationship", "partner": "relationship",
    "spouse": "relationship", "kids": "relationship", "children": "relationship",
    "possession": "possession", "possessions": "possession", "owns": "possession",
    "device": "possession", "hardware": "possession",
    "hobby": "hobby", "interest": "hobby", "interests": "hobby",
    "social_media_platform": "social_media", "social_media": "social_media",
    "software_used": "tool", "tool_used": "tool", "project_name": "project",
    "github_username": "username", "computer": "device",
    "computer_name": "device", "gpu": "device", "salary": "income",
    "current_salary": "income", "current_package": "income",
    "annual_income": "income", "yearly_income": "income", "wage": "income",
    "pay": "income", "earnings": "income",
    "events": "event", "experience": "event", "activity_event": "event",
    "plans": "plan", "intention": "plan", "upcoming_event": "plan",
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

# v2 (entry 74): targets the entry-68/69 residue -- third-party attribution,
# roleplay/persona framings, and tech identifiers read as personal facts.
# OPT-IN via RG_EXTRACT_V2=1: changing the prompt invalidates the extraction
# cache, so v1 stays the default until a deliberate rebuild.
SYSTEM_V2 = SYSTEM.replace(
    "- If the message states no stable personal fact, output exactly: []",
    """- OTHER PEOPLE: a fact about someone else in the user's life (partner, \
child, parent, sibling, friend, colleague, their boss) is NOT a fact about the \
user. If it is a stable family fact worth keeping, the attribute MUST name the \
relationship (e.g. "wife_occupation", "daughter_university", "brother_job"); \
NEVER put someone else's job, device, income, or location under a bare user \
attribute. If in doubt, skip it.
- ROLEPLAY / PERSONA: if the message sets up a roleplay, persona, story, or \
counterfactual ("pretend", "act as", "imagine I'm", "if I were", "in this \
scenario/story"), extract NOTHING from inside that framing.
- TECH IDENTIFIERS: usernames, hostnames, or emails inside commands, paths, \
URLs, or code (e.g. ssh alice@host22) are NOT personal facts about the user.
- If the message states no stable personal fact, output exactly: []""")


# v3 (entry 78): the WORLD reframe -- the memory holds the user's world, not
# only the user. Facts get a SUBJECT: "self", a relationship role ("wife"),
# a named person ("chris marmo"), an org, or a project. Third-party facts are
# no longer rejected -- they are ATTRIBUTED. Terminal/technical identifiers
# are facts about no one. OPT-IN via RG_EXTRACT_V3 (own cache/report).
SYSTEM_V3 = """Extract STABLE facts about the user's WORLD from one message: \
facts about the user themself, AND about the people, organisations and \
projects in their life. A stable fact could go on a profile page: where \
someone lives/works, what they own or use regularly, relationships, an \
ongoing project, a routine.

Output ONLY a JSON array, one object per fact:
[{"subject": "self" OR the other person/org/project (e.g. "wife", "friend \
chris", "tic tracker"), "attribute": "<short noun, e.g. residence, employer, \
possession, current_tool, weekly_class>", "value": "<short>"}]

STRICT rules -- when unsure, output fewer:
- subject "self" ONLY for facts the user states about their OWN life.
- A fact about someone/something else gets THAT subject: "my wife is doing a \
nursing placement" -> {"subject": "wife", "attribute": "placement", "value": \
"nursing"}. NEVER file another person's fact under subject "self".
- IGNORE instructions to the assistant, quoted text, code, file paths, \
section refs, numbers/metrics, and technical jargon.
- TERMINAL/TECH identifiers are facts about NO ONE: usernames, hostnames, \
IPs, emails, or prompts inside commands, paths, URLs, logs or pasted output \
(e.g. "ssh alice@host22", "(.venv) alice@box dir %") -- extract nothing from \
them.
- IGNORE metaphors and progress-talk ("keep digging", "moving to phase 5").
- IGNORE roleplay, personas, stories, counterfactuals ("pretend", "act as", \
"imagine I'm", "if I were") -- extract NOTHING from inside that framing.
- IGNORE hypotheticals, questions, and things people might do.
- If the message states no stable fact, output exactly: []"""


# v4 (HaluMem benchmark, entry TBD): v3's "IGNORE hypotheticals ... things
# people might do" rule also swallows EVENT-type memories -- a concrete thing
# that HAPPENED ("attended a pottery workshop on jan 6") isn't a stable
# profile fact and isn't a hypothetical either, it just fell through the
# cracks. Gold memory-point coverage on HaluMem was 4.4% because of this.
# v4 keeps every v3 rule (subject typing, terminal/tech identifiers, roleplay,
# first-person discipline) and carves two narrow exceptions out of the
# "things people might do" ban: EVENTS (happened) and PLANS (concretely
# stated intent, with timing). Pure wishes/hypotheticals still extract
# nothing. OPT-IN via RG_EXTRACT_V4 (own cache/report).
SYSTEM_V4 = SYSTEM_V3.replace(
    "- IGNORE hypotheticals, questions, and things people might do.\n"
    "- If the message states no stable fact, output exactly: []",
    """- EVENTS: a concrete event or experience someone reports having \
HAPPENED (not a routine) gets attribute "event"; value is a short \
description INCLUDING any stated date/time (e.g. {"subject": "self", \
"attribute": "event", "value": "attended a pottery workshop on jan 6 2026"}).
- PLANS: a stated CONCRETE plan or intention gets attribute "plan"; value \
likewise includes any stated timing (e.g. "trip to japan in november"). \
This is the ONLY exception to ignoring things people might do -- the plan \
must be explicitly stated, not a wish or hypothetical ("maybe i should \
learn piano someday" is NOT a plan -- extract nothing from it).
- Recurring/routine activities (a weekly class, a regular habit) stay under \
their existing attribute (e.g. weekly_class) -- they are NOT events.
- Org/team/repo tokens inside repository remotes or URLs (git@host:org/repo.git, \
github.com/org/repo) are TECH identifiers, NOT employers, projects or teams -- \
extract nothing from them.
- IGNORE pure hypotheticals, wishes, questions, and things people MIGHT do \
where no concrete plan is stated.
- If the message states no stable fact, output exactly: []""")


def canon_subject(s):
    """Normalise a subject: lowercase, strip possessives/articles. 'my wife'
    -> 'wife'; 'my friend chris' -> 'chris (friend)' stays as given otherwise."""
    s = re.sub(r"\s+", " ", str(s).lower().strip())
    s = re.sub(r"^(my|the|our)\s+", "", s)
    return s or "self"


def active_system():
    if os.environ.get("RG_EXTRACT_V4"):
        return SYSTEM_V4
    if os.environ.get("RG_EXTRACT_V3"):
        return SYSTEM_V3
    return SYSTEM_V2 if os.environ.get("RG_EXTRACT_V2") else SYSTEM


def extract_profile_facts(text, system=None):
    """[{attribute, value}] stable self-facts from ONE user turn. Realtime: single
    turn, no history, small output."""
    out = get_llm().create_chat_completion(
        messages=[{"role": "system", "content": "/no_think " + (system or active_system())},
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
                fact = {"attribute": a, "value": v}
                # v3: subject-typed world facts; absent (v1/v2) means self
                subj = canon_subject(f.get("subject", "self"))
                if subj != "self":
                    fact["subject"] = subj[:40]
                facts.append(fact)
    return facts
