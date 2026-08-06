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


# v5 (HaluMem entry 94: extraction coverage is the binding constraint --
# oracle ceiling 43%, and the missing golds are dominated by NARRATIVE
# memories -- motivations, reasons, values, feelings, reflections,
# relationship dynamics -- that v4 has no ontology for. v4's attribute set
# is terse attribute:value (occupation, location, event, plan...); it drops
# the WHY. v5 keeps every v4 rule (subjects, events/plans, roleplay/
# identifier bans, wish guard) and adds a NARRATIVE class of fact whose
# value is allowed to carry the stated reason/qualifier verbatim-ish (up to
# ~15 words, vs v4's short values) instead of being collapsed to a bare
# noun. OPT-IN via RG_EXTRACT_V5 (own cache/report; checked BEFORE V4 in
# active_system so it can be enabled without disturbing the v4 default).
#
# Dev-set iteration note: a revision was TRIED and REVERTED. Iteration-1
# extraction (users 10-12, qwen3:1.7b/ollama) raised oracle gold-in-store
# from v4's 11.8% to 19.8% (+8.0 pts, short of the +10 bar) -- but cache
# inspection showed the EXTRACTION was already capturing the right narrative
# facts with reasons (e.g. "immersive cultural experiences ... for
# understanding human behavior" was extracted verbatim). The loss happens
# DOWNSTREAM: run_profile_full._cluster (shared by halumem_run.ingest_user)
# merges same-attribute values on ANY shared content token, so two distinct
# narrative facts that both end in a similar generic reason tail collide and
# one label's specific wording is discarded. A revision telling the model to
# drop generic/repeated reason tails ("KEEP IT SPECIFIC") was tried to
# reduce that collision risk; re-extracting with it measured WORSE
# (17.4%, -2.4 pts vs iteration 1) -- the gold answers themselves often
# needed that "generic" reason text, so suppressing it cost more than the
# declustering gained. Reverted; SYSTEM_V5 below is iteration 1's text. The
# real fix is downstream (attribute-aware/topic-aware clustering, not a
# prompt change) and is out of this mission's scope -- flagged for follow-up.
#
# Regression probe (27-case suite, qwen3:1.7b/ollama, v4 vs this final v5):
# v4 26/27, v5 24/27 -- v5 lost TWO cases (a third-party neg: "my old boss
# maria now runs a bakery" got split into residence/employer/current_tool
# facts instead of being filed under subject "maria"; a wpos: "my old
# supervisor is over at swinburne university" landed as subject "self"
# instead of "supervisor"), exceeding the "lose at most 1" bar. Both are
# subject-typing slips on THIRD-PARTY facts, not narrative-attribute
# misuse -- plausibly prompt-length/attention pressure from the added
# narrative block.
#
# v5.1 (this revision, TWO tweaks tried, per-mission budget):
#
# TWEAK 1 (reverted, not shipped): added the maria worked example PLUS an
# "even when other details follow in the same sentence" clause PLUS an
# explicit "old/former roles still get that person's subject" reinforcement
# sentence to the subject-rule bullet, and to hold length flat, dropped the
# narrative-values bullet's THIRD worked example (the "snakes" preference
# case). Probe: 26/27 (fixed maria; incidentally also fixed the pre-existing
# v4 "mac studio" wpos miss; still lost "swinburne" -- see below). Cleared
# the >=26/27 bar on the number alone -- BUT a narrative-intactness spot
# check (6 FRESH non-verbatim narrative sentences, none copied from the
# prompt's own examples) found REAL regression: 3/6 produced a narrative
# fact vs iteration-1's 5/6 -- the reflection and relationship_dynamic cases
# specifically stopped extracting. Trimming the "snakes" example cost more
# than the subject-rule reinforcement gained, echoing the iteration-2
# lesson above (removing narrative content measurably hurts narrative
# recall on THIS model) even though the probe number alone looked clean.
# Discarded on the "narrative extraction intact" requirement, not the
# probe-score requirement.
#
# TWEAK 2 (SHIPPED, below): a MINIMAL third-party addition -- just the maria
# worked example appended inline to the existing subject-rule bullet, no
# extra reinforcement sentences -- with the full narrative block (all three
# original worked examples, snakes included) left untouched. Probe: 25/27
# (fixes maria cleanly vs iteration-1's 24/27, zero new regressions:
# "mac studio" was already broken in v4 itself, "swinburne" was already
# broken in iteration-1). Narrative spot-check: 5/6, IDENTICAL to
# iteration-1 -- no narrative regression.
#
# NEITHER tweak clears BOTH stated bars simultaneously (tweak 1: probe >=26
# but narrative degraded; tweak 2: narrative intact but probe 25/27, one
# short). Per the two-tweak budget, tweak 2 is kept as the better of the
# two: it is a STRICT improvement over iteration-1 (fixes one real case,
# breaks nothing, no narrative cost), whereas tweak 1's extra probe point
# was bought by sacrificing exactly the narrative recall this whole v5 line
# exists for (Mission-1's cluster fix showed narrative-value coverage is
# THE driver of the oracle gain) -- re-extracting on a narrative-degraded
# prompt would risk repeating the iteration-2 regression under a passing
# probe number. Reported honestly rather than re-extracted: users 10-12
# were NOT re-extracted with this revision; the standing result is
# iteration-1's caches (unchanged) + the Mission-1 cluster-fix oracle
# numbers over them (recorded in notebook entry 95).
#
# The one remaining miss ("my old supervisor is over at swinburne
# university" -> the model echoes the LITERAL string "maria (old boss)" as
# the subject instead of generalising to "supervisor" or "old supervisor")
# is a few-shot literal-copy artifact, not a rule-comprehension failure --
# flagged, not fixed; a distinct worked example for a role-only (no name)
# third party might address it but was out of the two-tweak budget.
SYSTEM_V5 = SYSTEM_V4.replace(
    """- A fact about someone/something else gets THAT subject: "my wife is doing a \
nursing placement" -> {"subject": "wife", "attribute": "placement", "value": \
"nursing"}. NEVER file another person's fact under subject "self".""",
    """- A fact about someone/something else gets THAT subject: "my wife is doing a \
nursing placement" -> {"subject": "wife", "attribute": "placement", "value": \
"nursing"}; "my old boss maria now runs a bakery" -> {"subject": "maria \
(old boss)", "attribute": "occupation", "value": "runs a bakery"}. NEVER \
file another person's fact under subject "self"."""
).replace(
    "- IGNORE pure hypotheticals, wishes, questions, and things people MIGHT do "
    "where no concrete plan is stated.\n"
    "- If the message states no stable fact, output exactly: []",
    """- NARRATIVE facts are extractable, not commentary: a stated motivation, \
belief, value, feeling, reflection, preference, or relationship dynamic is a \
stable fact about someone's inner life just as much as their job or city. \
Use attribute "motivation" (why they do or want something), "belief" \
(something they hold to be true), "value" (something they prioritise or \
care about), "feeling" (an emotion they report about something ongoing, \
not a one-off reaction to this message), "reflection" (an insight or \
realisation about themselves or their life), "preference" (something they \
like/dislike, together with why), or "relationship_dynamic" (how a \
relationship works or has changed, and why). Subject is "self" for the \
user's own narrative, or the relevant person/relationship for someone \
else's (e.g. "wife").
- NARRATIVE VALUES KEEP THE REASON: when the message states a reason, \
cause, or qualifier alongside the narrative, the value MUST include it, \
verbatim-ish, up to about 15 words -- do not collapse it down to a bare \
noun. Example: "she values her moments of solitude because they help her \
recharge and think clearly" -> {"subject": "self", "attribute": "value", \
"value": "solitude for recharging and gaining clarity"}, NOT \
{"attribute": "value", "value": "solitude"}. Example: "i appreciate snakes \
for how low-maintenance and fascinating they are" -> {"subject": "self", \
"attribute": "preference", "value": "snakes for their low maintenance and \
unique behaviors"}. Example: "working on projects together has really \
brought my wife and me closer" -> {"subject": "wife", "attribute": \
"relationship_dynamic", "value": "relationship enhanced by working on \
collaborative projects together"}. If NO reason/qualifier is stated, keep \
the value short (as any other v4 attribute) -- never invent a reason that \
was not said.
- Still IGNORE pure hypotheticals, wishes, questions, and things people \
MIGHT do where no concrete plan is stated -- a narrative fact must be \
stated as true of them, not a hypothetical feeling ("i'd probably love \
gardening if i had a yard" is NOT a preference fact).
- If the message states no stable fact, output exactly: []""")


def canon_subject(s):
    """Normalise a subject: lowercase, strip possessives/articles. 'my wife'
    -> 'wife'; 'my friend chris' -> 'chris (friend)' stays as given otherwise."""
    s = re.sub(r"\s+", " ", str(s).lower().strip())
    s = re.sub(r"^(my|the|our)\s+", "", s)
    return s or "self"


# v5.2 (entry 128): SUPERSESSION CAPTURE. When a turn STATES a change, the
# value records what it replaced -- slot linking becomes explicit at ingest
# instead of unreconstructable downstream (the entry-113/115 timeline
# starvation: "green tea" -> "black coffee" share no tokens, so no
# after-the-fact linker can chain them; the turn that SAID "switched from
# green tea to black coffee" could have). Opt-in via RG_EXTRACT_V52.
SYSTEM_V52 = SYSTEM_V5.replace(
    "- Still IGNORE pure hypotheticals, wishes, questions, and things people ",
    """- CHANGES KEEP THE OLD VALUE: when the message states that something \
CHANGED, REPLACED, or STOPPED ("i switched from X to Y", "no longer X, now \
Y", "i quit X", "we moved from X to Y"), the value MUST name both: \
"Y (previously X)" -- e.g. "i've switched from green tea to black coffee" \
-> {"subject": "self", "attribute": "preference", "value": "black coffee \
(previously green tea)"}; "i quit apple to join google" -> {"subject": \
"self", "attribute": "employer", "value": "google (previously apple)"}. \
Only when the change is STATED -- never infer one.
- Still IGNORE pure hypotheticals, wishes, questions, and things people """)


def active_system():
    if os.environ.get("RG_EXTRACT_V52"):
        return SYSTEM_V52
    if os.environ.get("RG_EXTRACT_V5"):
        return SYSTEM_V5
    if os.environ.get("RG_EXTRACT_V4"):
        return SYSTEM_V4
    if os.environ.get("RG_EXTRACT_V3"):
        return SYSTEM_V3
    return SYSTEM_V2 if os.environ.get("RG_EXTRACT_V2") else SYSTEM



# v6 (entry 185: the wall is PRECISION, not recall). Measured on round 5, RG
# emits 17.75 memories per session against gold's 10.69 -- a 1.66x
# over-extraction, over-emitting on 89% of sessions and under-emitting on 8%.
# Over-extraction alone caps extraction F1 at ~75% (10.69/17.75) before any
# quality question. Every prior extraction revision, v4 and v5 included, pushed
# COVERAGE: v5 exists because entry 94 read the oracle ceiling as a recall
# problem. That direction is now measured to be wrong.
#
# Two changes, both aimed at precision, neither removing v5 content:
#
# 1. A required TYPE from a CLOSED SET -- persona | event | relationship.
#    HaluMem's gold is organised in exactly these three categories (Persona
#    61.8%, Event 30.0%, Relationship 8.2%), and MOSAIC's "entity-typed graph
#    storage across events, personas and relationships" is that taxonomy
#    adopted 1:1. We have been emitting untyped attribute:value pairs into it.
#
# 2. The type acts as the PRECISION FILTER. A candidate that does not sit
#    cleanly in one of the three categories is dropped rather than forced into
#    the nearest one. This is the mechanism for the 1.66x -> ~1.0x cut, and it
#    is selective rather than a blunt per-session cap: it removes the items
#    that were never gold-shaped to begin with.
#
# The v5 narrative block is left ENTIRELY intact. The v5.1 notes above record
# that trimming narrative content measurably cost narrative recall on this
# model (5/6 -> 3/6 on a fresh spot check) even when the probe score looked
# clean, so narrative facts keep their place -- they are typed, not cut.
SYSTEM_V6 = SYSTEM_V5.replace(
    """Output ONLY a JSON array, one object per fact:
[{"subject": "self" OR the other person/org/project (e.g. "wife", "friend \
chris", "tic tracker"), "attribute": "<short noun, e.g. residence, employer, \
possession, current_tool, weekly_class>", "value": "<short>"}]""",
    """Output ONLY a JSON array, one object per fact:
[{"type": "persona" | "event" | "relationship", "subject": "self" OR the other \
person/org/project (e.g. "wife", "friend chris", "tic tracker"), "attribute": \
"<short noun, e.g. residence, employer, possession, current_tool, \
weekly_class>", "value": "<short>"}]

Every fact MUST carry exactly one type from that closed set:
- "persona": a durable attribute of a person -- who they are, what they have, \
where they live or work, what they prefer, believe, feel, value or intend.
- "event": something that HAPPENED or is concretely planned, with its stated \
timing where given.
- "relationship": the connection BETWEEN two named parties (who someone is to \
someone else), not a fact about either one alone.
THE TYPE IS A FILTER, NOT A LABEL. If a candidate fact does not sit cleanly in \
one of these three categories, DO NOT emit it and DO NOT force it into the \
nearest one. Emitting fewer, well-typed facts is correct; padding the list is \
an error.""")


# SYSTEM_ASSISTANT (entry 190/191): extraction prompt for ASSISTANT turns.
#
# Entry 189 found we skip assistant turns entirely, capping recall at 35.4%
# against an 86.9% ceiling. But ingesting assistant turns wholesale means
# ingesting the model's own output, and a model that embellishes writes its
# embellishments into memory as fact (memory contamination). Entry 190 proposed
# provenance tiering; that has a hole -- assistant-sourced gold is often stated
# ONCE (the prior job title appears only there), so requiring user corroboration
# to promote would discard exactly what we came for.
#
# The resolution is to constrain WHAT we take, not how much we trust it. In the
# data the three kinds are cleanly separable:
#     "Your background as a Senior Data Scientist ..."  RESTATEMENT -> memory
#     "Google is a great company"                       OPINION     -> drop
#     "You should try meditation"                       ADVICE      -> drop
# Only a restatement of something the USER has established is memory.
#
# This is a SCOPE rule, not an assertion-calibration rule. Entry 186's law --
# instructing the model does not change assertion behaviour -- applies to
# telling a model how confident to be. Scope rules do work here: v3/v4's
# "ignore roleplay", "ignore code paths", "ignore tech identifiers" all hold.
# Conflating the two is what made entry 186's typed-filter attempt fail.
SYSTEM_ASSISTANT = """Extract STABLE facts about THE USER that this ASSISTANT \
message RESTATES or REFERS BACK TO. The assistant is talking to the user about \
the user's own life; your job is to recover facts the user has already \
established, including ones this message is the only record of.

Output ONLY a JSON array, one object per fact:
[{"subject": "self" OR the other person/org/project, "attribute": "<short \
noun>", "value": "<short>"}]

EXTRACT only what the assistant attributes to the user as already true:
- second-person statements about the user's history, situation or attributes \
("your background as a senior data scientist", "since you moved to Google", \
"your recent diagnosis") -- these are the assistant recalling what the user \
told it, and are often the ONLY record of a previous value.
- a PRIOR value the assistant names when acknowledging a change ("moving from \
Apple to Google" -> employer_previous: apple).

NEVER EXTRACT:
- the assistant's OWN opinions, evaluations or encouragement ("that's a great \
approach", "Google is a good company") -- these are not facts about the user.
- ADVICE, suggestions, or anything the assistant proposes the user DO ("you \
should try", "have you considered", "it might help to") -- a suggestion is not \
a fact, even if the user later acts on it.
- questions the assistant asks.
- anything the assistant introduces that the user has not established -- if it \
reads as new information invented by the assistant rather than recalled from \
the user, DROP IT.

When unsure whether the assistant is RECALLING or INVENTING, output nothing.
If the message restates no user fact, output exactly: []"""

def extract_profile_facts(text, system=None):
    """[{attribute, value}] stable self-facts from ONE user turn. Realtime: single
    turn, no history, small output."""
    msgs = [{"role": "system",
             "content": "/no_think " + (system or active_system())},
            {"role": "user", "content": text[:1600]}]
    # RG_LLM_BASE routes extraction through an ALREADY-RUNNING llama-cpp server
    # instead of loading a second in-process copy of the same GGUF, which would
    # contend for VRAM with the composer/judge server. Unset keeps the original
    # in-process path, so existing callers are unaffected.
    base = os.environ.get("RG_LLM_BASE", "").strip()
    if base:
        import json as _json
        import urllib.request as _u
        body = _json.dumps({"model": "local", "messages": msgs,
                            "max_tokens": 200, "temperature": 0.0}).encode()
        req = _u.Request(base.rstrip("/") + "/chat/completions", data=body,
                         headers={"Content-Type": "application/json"})
        with _u.urlopen(req, timeout=300) as resp:
            out = _json.load(resp)
    else:
        out = get_llm().create_chat_completion(messages=msgs, max_tokens=200,
                                               temperature=0.0)
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
            # 160 (was 80): v5 narrative values keep a stated reason clause
            # verbatim-ish, up to ~15 words -- longer than v4's short values.
            # Relaxing the cap only ever truncates less; v4-era short values
            # are unaffected.
            v = str(f["value"]).strip()[:160]
            if a and v:
                fact = {"attribute": a, "value": v}
                # v6: carry the typed category through when present. Kept as a
                # passthrough rather than a requirement so v3/v4/v5 caches,
                # which have no type, parse unchanged.
                t = str(f.get("type", "")).strip().lower()
                if t in ("persona", "event", "relationship"):
                    fact["mtype"] = t
                # v3: subject-typed world facts; absent (v1/v2) means self
                subj = canon_subject(f.get("subject", "self"))
                if subj != "self":
                    fact["subject"] = subj[:40]
                facts.append(fact)
    return facts
