"""Subjectless fragments at the start of a user turn (2026-10-02).

People drop the subject in chat: "Still nursing at St Vincent's though",
"Vegetarian now, for about a year". The parser needs a subject, so these
produced nothing. A fragment that opens a user turn is about the speaker
only when it opens the conversation or answers a question put to the user
that mentions nobody else ("What do you do?"). After "What does your sister
do?", "How's the family?" or a draft about someone else it is skipped.

Three shapes only, all checked on the parse:
  * an -ing verb with a noun argument: "Loving the new job", "Training for
    a marathon". "Looking good", "Getting there", "Working on it" have no
    noun argument (or only a pronoun) and are left alone;
  * an adjective from a closed list of states: "Vegetarian now", "Pregnant!";
  * a past-tense verb with a noun argument: "Sold the Corolla on Saturday",
    "Cancelled the gym membership". "Sell the Corolla" is an imperative.
The fragment is parsed as "I'm <fragment>" ("I <fragment>" for the past
tense); the record keeps the original sentence as its source.
"""
import os
import re

STATE_ADJ = {"vegetarian", "vegan", "pescatarian", "pregnant", "single",
             "married", "divorced", "engaged", "separated", "widowed",
             "retired", "unemployed", "sober", "allergic", "freelance",
             "self-employed"}
_ARG_DEPS = ("obj", "obl", "iobj")
_FIRST_WORD = re.compile(r"^\W*(?:still|now|currently|just|recently|mostly|"
                         r"finally|also|actually)?\s*([A-Za-z-]+)", re.I)


_THIRD = re.compile(r"\byour\s+(?!own\b)\w+|\b(he|she|they|him|her|them|his|"
                    r"their|the (?:family|kids?|baby|dog|cat|team|boss|"
                    r"landlord|doctors?|new hire|character|story|draft))\b",
                    re.I)
_NAME = re.compile(r"(?<!^)(?<![.!?]\s)\b[A-Z][a-z]+")


def _about_user(prev):
    """Is a fragment answering `prev` about the user?

    Review 2026-10-02: a fragment answers whatever was just raised, and
    "How's the family?", "What's the dog up to?", "Tell me about your wife."
    or a draft bio for someone else all raise someone else. So the rule
    fires only at the start of a conversation, or right after a question
    put to the user ("What do you do?") that mentions nobody else."""
    if not prev:
        return True
    sents = re.split(r"(?<=[.!?])\s+", prev.strip())
    if _THIRD.search(prev) or any(_NAME.search(x) for x in sents[-2:]):
        return False
    qs = [q for q in sents if q.endswith("?")]
    if not qs:
        return False
    q = qs[-1]
    # Review 2026-10-02: "What would you like me to include in the speech?",
    # "Can you summarise this?" -- the reply is material for a task, not
    # news about the user
    if (re.search(r"\b(me|I|I'll|I'd|my)\b", q)
            or re.match(r"^\W*(can|could|would|will) you\b", q, re.I)):
        return False
    return bool(re.search(r"\byou\b", q, re.I))


_DENIAL = re.compile(r"^\W*(no\b|nope|not\b|nah|just kidding|kidding|jk\b|"
                     r"joking|lol\b|haha)", re.I)


_IRREGULAR_PAST = frozenset("""sold bought got made took left quit lost found
sent met went gave began broke ran wrote drove had paid built caught chose
fell flew forgot grew heard kept led lent rode sat slept spent stood swam
taught told threw won wore""".split())


def _candidate(sentence):
    """-> "ing", "adj", "past" or None, from the first word (after an
    adverb such as "still" or "finally")."""
    m = _FIRST_WORD.match(sentence)
    if not m:
        return None
    w = m.group(1).lower()
    if w.endswith("ing"):
        return "ing"
    if w == "been":                 # "Been rehearsing hard all week"
        return "been"
    if w in STATE_ADJ:
        return "adj"
    if w.endswith("ed") or w in _IRREGULAR_PAST:
        return "past"
    return None


_PERSONS = frozenset("""sister brother mum mom dad mother father wife husband
partner boyfriend girlfriend friend boss manager colleague son daughter kid
kids child children neighbour neighbor flatmate roommate cousin aunt uncle
grandma grandpa nan""".split())


def _tail_ids(words, root):
    """Ids under a comma-spliced tail of the root: a parataxis / list /
    discourse child, or a conjunct with its own subject."""
    if root is None:
        return set()
    kids = {}
    for w in words:
        kids.setdefault(w.head, []).append(w)
    starts = [w for w in kids.get(root.id, [])
              if w.deprel in ("parataxis", "list", "discourse")
              or (w.deprel == "conj" and any(c.deprel.startswith("nsubj")
                                            for c in kids.get(w.id, [])))]
    out, stack = set(), list(starts)
    while stack:
        w = stack.pop()
        out.add(w.id)
        stack.extend(kids.get(w.id, []))
    return out


def _has_noun_arg(root, words):
    """A noun argument on the root or on a verb coordinated with it
    ("rehearsing hard and working on business plans"). A number object
    counts too: "Turned 30 yesterday" (2026-10-03, stale dev set)."""
    heads = {root.id} | {w.id for w in words
                         if w.head == root.id and w.deprel == "conj"}
    return any(w.head in heads and w.deprel in _ARG_DEPS
               and (w.upos in ("NOUN", "PROPN")
                    or (w.upos == "NUM" and w.deprel == "obj"))
               for w in words)


# 2026-10-03 (stale dev set): "Got hooked on flat whites", "Got promoted
# to lead" -- a get-passive. Its root is the participle, not a VBD.
_GET_PASSIVE_EVENTS = {"marry", "engage", "promote", "fire", "hire",
                       "divorce", "sack", "lay", "accept", "diagnose"}


def _get_passive(words, root):
    return (root is not None and root.xpos == "VBN"
            and any(w.head == root.id and w.deprel == "aux:pass"
                    and (w.lemma or "").lower() == "get" and w.id == 1
                    for w in words))


def _accept(head, nlp):
    """-> the sentence rewritten with "I'm"/"I", or None."""
    shape = _candidate(head)
    if not shape:
        return None
    # "Married? No." is a question; "Reading: War and Peace" is a heading;
    # "Sending you the file" is about this conversation, not the user's life.
    if (head.rstrip().endswith("?") or ":" in head
            or re.search(r"\byou(r)?\b", head, re.I)):
        return None
    # A fragment has no subject and no finite verb of its own -- "Pregnant
    # women should avoid sushi", "Married with Children is my favourite
    # show", "Stealing cars is wrong" are sentences. A past-tense fragment
    # ("Sold the Corolla on Saturday") is finite itself: its root is the one
    # finite verb allowed. An imperative ("Sell the Corolla") is VB, not VBD.
    orig = nlp(head).sentences[0].words
    oroot = next((w for w in orig if w.deprel == "root"), None)
    # a comma-spliced tail is its own clause ("Picked up a Mazda 3 on
    # Saturday, it's got a few scratches") -- judge the fragment without it
    tail = _tail_ids(orig, oroot)
    orig = [w for w in orig if w.id not in tail]
    getpass = shape == "past" and _get_passive(orig, oroot)
    if shape == "past" and not getpass and (oroot is None or oroot.xpos != "VBD"):
        return None
    if shape == "been":
        # "Been rehearsing hard", "Been promoted to team lead", "Been vegan
        # since January", judged on "I've been <...>"
        new = "I've " + head[0].lower() + head[1:]
        words = nlp(new).sentences[0].words
        root = next((w for w in words if w.deprel == "root"), None)
        if root is None or not any(w.head == root.id and w.deprel.startswith("nsubj")
                                   and w.text == "I" for w in words):
            return None
        if root.xpos in ("VBG", "VBN") and _has_noun_arg(root, words):
            return new
        if root.text.lower() in STATE_ADJ:
            return new
        return None
    if any(w.deprel.startswith(("nsubj", "csubj", "expl"))
           or (w.upos in ("VERB", "AUX") and "VerbForm=Fin" in (w.feats or "")
               and not (shape == "past" and w is oroot)
               and not (getpass and w.id == 1))
           for w in orig):
        return None
    new = ("I " if shape == "past" else "I'm ") + head[0].lower() + head[1:]
    # Judged on the rewritten sentence: without a subject Stanza often tags
    # the -ing word as a noun ("Nursing at St Vincent's" -> NN root).
    words = nlp(new).sentences[0].words
    root = next((w for w in words if w.deprel == "root"), None)
    if root is None:
        return None
    subj = [w for w in words if w.head == root.id and w.deprel.startswith("nsubj")]
    if len(subj) != 1 or subj[0].text != "I":
        return None
    # "Nursing at St Vincent's, my sister." -- the nurse is the sister; an
    # appended PERSON (a name, or "my <person>") disqualifies, an appended
    # remark ("200-day streak now", "send help") does not
    for w in words:
        if w.deprel in ("appos", "dislocated", "vocative") and (
                w.upos == "PROPN" or w.text.lower() in _PERSONS):
            return None
    if getpass:
        ok = (root.xpos == "VBN" and any(
                  w.head == root.id and w.deprel == "aux:pass"
                  and (w.lemma or "").lower() == "get" for w in words)
              and (_has_noun_arg(root, words)
                   or (root.lemma or "").lower() in _GET_PASSIVE_EVENTS))
    elif root.xpos in ("VBG", "VBD") and (root.xpos == "VBD") == (shape == "past"):
        ok = _has_noun_arg(root, words)
    else:
        ok = root.text.lower() in STATE_ADJ
    return new if ok else None


# the user as SUBJECT; "My sister is a nurse." is about the sister, so the
# fragment after it ("Working nights at the Alfred.") is hers
_FIRST_PERSON = re.compile(r"^\W*(i|i'm|i’m|i've|i’ve|i'd|we|we're|we’re|we've)\b",
                           re.I)


_OTHER_IN_SENT = re.compile(
    r"\babout\b|\b(met|saw|visited|called|read|watched)\b|"
    r"\bmy\s+(?:" + "|".join(sorted(
        "dog cat pet puppy kitten wife husband partner boyfriend girlfriend "
        "mum mom dad mother father son daughter sister brother friend boss "
        "manager colleague kid kids child children baby neighbour neighbor "
        "flatmate roommate".split())) + r")\b")


def _mentions_other(sent):
    """"I'm writing a story about Anna.", "I met Sam today.", "I love my
    dog." -- the fragment after it may be theirs (review 2026-10-02)."""
    if _OTHER_IN_SENT.search(sent):
        return True
    words = re.findall(r"[A-Za-z']+", sent)
    return any(w[:1].isupper() and w not in ("I", "I'm", "I've", "I'd")
               for w in words[1:])


# 2026-10-05 (implied-change catalogue): presupposition triggers. An
# ordinal with a time unit ("Fourth week as a paramedic", "First week at
# Kestrel Print"), a phase ("Day ten of decaf", "Six weeks into drums"), a
# duration with someone ("Three months with Daniel now", "Anniversary dinner
# with Ben") presupposes a state that began recently (Karttunen 1974,
# Levinson 1983 on presupposition triggers). The presupposed state is read
# as its own sentence, with "now" for the onset the trigger presupposes, and
# the user's sentence is kept as said.
_ORD = (r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
        r"\d+(?:st|nd|rd|th))")
_NUM = (r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
        r"a few|several|\d+)")
_UNIT = r"(?:day|week|month|year|shift|term|semester)"
_X = r"(?P<x>[^,.;!?]+?)"
_END = r"(?=\s+(?:was|is|has been|went|so|and|but)\b|[,.;!?]|$)"
_PRESUP = [
    (re.compile(rf"^\W*(?:sitting in\s+)?(?:my\s+)?{_ORD}\s+(?:\w+\s+){{0,2}}as\s+{_X}{_END}", re.I),
     "I am {x} now."),
    # the place must be an organisation: a name, or a job word ("First day
    # at the beach" presupposes nothing about work)
    (re.compile(rf"^\W*(?i:(?:my\s+)?{_ORD}\s+{_UNIT}\s+(?:at|with)\s+(?:the\s+new\s+)?)"
                r"(?P<x>(?:[A-Z][\w&'-]*\s*){1,4}|(?i:(?:the\s+|my\s+)?(?:new\s+)?"
                r"(?:job|company|firm|school|office|practice|hospital|clinic)\b))", 0),
     "I work at {x} now."),
    (re.compile(rf"^\W*(?:day|week|month)\s+\w+\s+(?:of|on)\s+{_X}{_END}", re.I),
     "I'm on {x} now."),
    (re.compile(rf"^\W*{_NUM}\s+(?:days|weeks|months|years)\s+into\s+{_X}{_END}", re.I),
     "I'm doing {x} now."),
    (re.compile(rf"^\W*(?i:{_NUM}\s+(?:days|weeks|months|years)\s+(?:with|dating)\s+)"
                r"(?P<x>[A-Z][a-z]+)\b"), "I'm with {x} now."),
    (re.compile(r"^\W*(?i:(?:our\s+)?anniversary\s+(?:dinner\s+|trip\s+)?with\s+)"
                r"(?P<x>[A-Z][a-z]+)\b"), "I'm with {x} now."),
    (re.compile(rf"^\W*started\s+(?:at|with)\s+{_X}(?=\s+(?:on|last|this|today|yesterday)\b|[,.;!?]|$)",
                re.I), "I started at {x}."),
    (re.compile(r"^\W*(?:transferred|moved)\s+to\s+(?P<x>the\s+[^,.;!?]+?\s+"
                r"(?:team|site|office|group|department|branch))\b", re.I),
     "I moved to {x}."),
    (re.compile(rf"^\W*(?P<x>{_NUM}\s+[a-z]+s)\s+now\b", re.I), "I have {x} now."),
]


# 2026-10-06 adversarial review: 19 of 28 negative sentences fired --
# "First year at Oxford was hard back in 1998", "Five years with Jenny ended
# in 2010", "Day 3 of the conference", "Third week as a result". A trigger
# presupposes a CURRENT state only when nothing in the sentence places it in
# the past or in a story, and the slot is not an idiom or an event.
_PAST = re.compile(r"\b(back in|ago|last (?:year|month|week|summer|winter|time)|"
                   r"in (?:19|20)\d\d|ended|finished|cancel+ed|broke up|split up|"
                   r"used to|when i was|years? before|in the (?:book|film|movie|show|story|game)|"
                   r"was over|didn'?t last|quit|left|resigned|got fired|laid off|"
                   r"handed in)\b", re.I)
_IDIOM = re.compile(r"^(?:a result|a kid|a child|a teen\w*|a baby|a joke|a whole|"
                    r"a matter|a favour|a favor|usual|always|ever)\b", re.I)
_EVENT = re.compile(r"\b(conference|holiday|holidays|vacation|trip|festival|"
                    r"christmas|easter|war|course of|tour|camp|retreat|honeymoon)\b", re.I)


def _presupposed(sent):
    """-> the state a presupposition trigger at the start of `sent` takes
    for granted, as a first-person sentence, or None."""
    if _PAST.search(sent):
        return None
    for rx, tpl in _PRESUP:
        m = rx.match(sent)
        if m:
            x = " ".join(m.group("x").split())
            # "Second week at Tesco I quit": the slot stops before "I"
            x = re.split(r"\s+(?:I|i|we|my)\b", x)[0].strip()
            if not x or _IDIOM.match(x) or _EVENT.search(x):
                return None
            if tpl.startswith("I have"):
                x = x.lower()
            if tpl.startswith("I work at") and x.lower() in ("job", "new job"):
                return "I have a new job now."
            if 1 <= len(x.split()) <= 6:
                return tpl.format(x=x)
    return None


def rewrite(text, nlp, prev=None):
    """-> (text to parse, {rewritten sentence: original}) -- unchanged text
    and an empty map when no sentence is an accepted fragment.

    The first sentence of the turn may be a fragment; a later one only when
    the sentence before it was about the user too ("I handed in my notice at
    the cafe. Starting as a paralegal at a law firm on Monday.")."""
    if os.environ.get("RG_FRAGMENTS") == "0" or not _about_user(prev):
        return text, {}
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    out, orig, about_user = [], {}, True
    for i, sent in enumerate(sents):
        nxt = sents[i + 1] if i + 1 < len(sents) else ""
        new = None
        pre = None
        if about_user and not _DENIAL.match(nxt):
            pre = _presupposed(sent)
            new = None if pre else _accept(sent, nlp)
        if pre:
            # the presupposed state, then the sentence as said
            orig[pre] = sent
            out.append(pre)
            out.append(sent)
        elif new:
            orig[new] = sent
            out.append(new)
        else:
            out.append(sent)
        about_user = bool(new or pre) or (bool(_FIRST_PERSON.match(sent))
                                   and not _mentions_other(sent))
    if not orig:
        return text, {}
    return " ".join(out), orig
