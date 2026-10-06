"""Decisions the user made with the assistant (2026-10-06).

The memory keeps the user's own words; what the assistant says about the
user stays an unconfirmed claim. A proposal the user ACCEPTS is different:
the assent makes it the user's decision. In dialogue-act terms the
assistant's turn is an offer or suggestion and the user's turn an
acceptance; together they are a commitment the user made.

    assistant: "I'd suggest switching the build to pnpm for the workspaces."
    user:      "yes do it"
    -> "<owner> decided with the assistant: switching the build to pnpm for
        the workspaces"

Only an acceptance that opens the user's turn counts, and none that comes
with a reservation ("ok but keep npm", "sure, maybe later") or as a question.
When the user restates the choice ("ok use pnpm"), their own words are the
decision. A user's own "let's X" is a decision too, with no proposal needed.
"""
import re

_ASSENT_WORDS = (
    r"yes|yeah|yep|yup|sure|ok|okay|alright|sounds good|sounds great|"
    r"perfect|great|agreed|deal|do it|go ahead|go for it|please do|"
    r"let'?s do (?:it|that)|let'?s go with (?:it|that)|that works|works for me|"
    r"fine by me|fine with me|fine|absolutely|definitely|makes sense|good idea")
_ASSENT = re.compile(rf"^\W*(?:{_ASSENT_WORDS})\b", re.I)
_RESERVATION = re.compile(
    r"\b(no|not|don'?t|nope|nah|later|maybe|hmm+|think about|instead|but|"
    r"unless|rather|wait|hold on|not yet|let me check)\b", re.I)
# the user's own restatement after the assent: "ok use pnpm", "yes, go with
# vitest", "sure, switch to postgres"
_RESTATE = re.compile(
    rf"^\W*(?:{_ASSENT_WORDS})\W+(?P<x>(?:use|go with|switch to|"
    r"move to|stick with|add|enable|set up|keep|pick|choose|try)\b[^.!?]*)", re.I)
_LETS = re.compile(r"^\W*let'?s\s+(?P<x>(?:use|go with|switch|move|stick with|"
                   r"add|enable|set up|keep|adopt|drop|remove|migrate)\b[^.!?]*)",
                   re.I)
_PROPOSAL = [re.compile(p, re.I) for p in (
    r"\b(?:shall|should) I\s+(?P<x>[^?.!]+)\?",
    r"\b(?:want|would you like|do you want) me to\s+(?P<x>[^?.!]+)\?",
    r"\bhow about\s+(?P<x>[^?.!]+)\?",
    r"\bI(?:'d| would)\s+(?:suggest|recommend|go with|use)\s+(?P<x>[^.!?]+)",
    r"\bI\s+(?:suggest|recommend)\s+(?P<x>[^.!?]+)",
    r"\b(?:we|you) could\s+(?P<x>[^.!?]+)",
    r"\blet'?s\s+(?P<x>[^.!?]+)",
    r"\bmy (?:suggestion|recommendation) (?:is|would be)\s+(?:to\s+)?(?P<x>[^.!?]+)",
)]


def _clean(x, max_words=14):
    x = " ".join(x.split()).strip(" ,;:-")
    x = re.sub(r"^(?:that you|that we|you|we|to)\s+", "", x, flags=re.I)
    words = x.split()
    return " ".join(words[:max_words]) if words else None


_PURE = re.compile(r"^(?:(?:please|thanks|thank you|do it|do that|go ahead|go for it|"
                   r"sounds good|that works|works for me|for me|let'?s do (?:it|that)|"
                   r"perfect|great|cool|nice|ok|okay|yes|yeah|sure|absolutely|"
                   r"that one|then)[\s,!.]*)*$", re.I)
# accepting by acting on the proposal: "ok migrate it", "yeah perfect, move
# it", "let's go with that"
_ANAPHORIC = re.compile(r"^(?:(?:ok|okay|yes|yeah|sure|perfect|great|then|please)[\s,]+)*"
                        r"(?:let'?s\s+)?(?:do|move|migrate|switch|change|wire|set|add|use|"
                        r"deploy|apply|merge|ship|go with|run|make|rewrite)\s+"
                        r"(?:it|that|them|this|those|yours)\b[\s,.!]*$", re.I)
# naming the choice: "path versioning it is"
_IT_IS = re.compile(r"^(?P<x>[^,.;!?]{2,60}?)\s+it is[\s.!]*$", re.I)
_LATER = re.compile(r"\b(later|tomorrow|next (?:week|month|time)|sometime|someday|"
                    r"eventually|at some point|again)\b", re.I)


def proposal(assistant_text):
    """What the assistant proposed at the END of its message (its last two
    sentences), or None: an acceptance answers what was just offered."""
    sents = [x for x in re.split(r"(?<=[.!?])\s+", (assistant_text or "").strip()) if x]
    whole = " ".join(sents)
    tail = " ".join(sents[-3:])
    # an offer put as a question ("Shall I set it up with postgres?") is what
    # a bare "sounds good" answers, even with its reasons after it
    q = None
    for rx in _PROPOSAL[:3]:
        for m in rx.finditer(whole):
            if q is None or m.start() > q[0]:
                q = (m.start(), m.group("x"))
    st = None
    for rx in _PROPOSAL[3:]:
        for m in rx.finditer(tail):
            if st is None or m.start() > st[0]:
                st = (m.start(), m.group("x"))
    adjacent = bool(q and st and st[0] < q[0]
                    and not re.search(r"[.!?]\s+\S", tail[st[0]:q[0]].rstrip()[:-1] if False else
                                      re.sub(r"[.!?]\s*$", "", tail[st[0]:q[0]].strip())))
    if q and st and st[0] < q[0] and (adjacent or re.search(r"\b(it|them|that|this|those)\b", q[1], re.I)):
        # "We could use go-cmp for diffs. Want me to rewrite the assertions?"
        # -- the offer refers back to the proposal
        return _clean(f"{st[1]}; {q[1]}", max_words=24)
    if q:
        return _clean(q[1])
    return _clean(st[1]) if st else None


def _lets(clause):
    m = _LETS.match(clause)
    if not m:
        return None
    x = re.split(r",|;|\band\b|\bbut\b", m.group("x"))[0]
    if _LATER.search(x) or _RESERVATION.search(x):
        return None
    return _clean(x)


def decision(user_text, assistant_text=None):
    """-> (decision text, where it came from: 'user' | 'proposal') or None.

    2026-10-06 adversarial review: "Perfect, it works now", "great, thanks,
    that explains it", "yes I did" and "alright, I read it" after a
    suggestion were taken as acceptances (21 of 25 negative cases). An
    acceptance is now the WHOLE turn: the assent alone ("yes do it",
    "sounds good, go ahead"), or the assent and the action restated ("ok use
    pnpm", "alright let's switch to Tailwind")."""
    t = (user_text or "").strip()
    if not t or t.endswith("?"):
        return None
    first = re.split(r"(?<=[.!?])\s+", t)[0]
    if len(re.split(r"(?<=[.!?])\s+", t)) > 2:
        return None                     # a longer message is not a bare acceptance
    if _ANAPHORIC.match(first):
        p = proposal(assistant_text)
        return (p, "proposal") if p else None
    x = _lets(first)
    if x:
        return x, "user"
    m = _ASSENT.match(first)
    if not m or _RESERVATION.search(first):
        return None
    rest = first[m.end():].strip(" ,.!;-")
    if _ANAPHORIC.match(rest):
        p = proposal(assistant_text)
        return (p, "proposal") if p else None
    it_is = _IT_IS.match(rest)
    if it_is:
        return _clean(it_is.group("x")), "user"
    if _PURE.match(rest):
        p = proposal(assistant_text)
        return (p, "proposal") if p else None
    r = _RESTATE.match(first)
    if r and not _LATER.search(r.group("x")):
        return _clean(re.split(r",|;|\bbut\b", r.group("x"))[0]), "user"
    x = _lets(rest)
    if x:
        return x, "user"
    return None
