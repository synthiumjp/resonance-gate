"""p2: the schema filter — scope, not relation type.

WHAT THE DATA SAID. Over 105 facts extracted from real haystack users, the
retained population was dominated by TOPICS THE USER DISCUSSED rather than
facts about the user: keanu reeves, napa valley, schrodinger equation,
poisson distribution, Heidegger, anthropology, and a cast of story characters
the user was writing (Loki | is | the antagonist). Only 2 facts came from a
gold-evidence span, and both were

    (my current road bike | has | been used for 2,000 miles)

Note the relation: `has`. My first instinct was to filter by relation type and
drop contentless copulas (`is`, `has`, `have`), which are 35/105 of the
corpus. That would have destroyed BOTH gold facts. Relation type is not the
signal.

SCOPE IS THE SIGNAL. A personal memory is about the speaker, the people in
their life, and the things they own or are committed to. It is not about
whatever they happened to discuss. Keanu Reeves is not in the user's life;
their road bike is.

    SELF             "I", "me"                       -> in scope
    SELF_POSSESSIVE  "my city", "my current road bike"-> in scope
    ORBIT            a named person/org the speaker has stated a relationship
                     with ("my colleague Dana", or an entity appearing as the
                     object of a relationship relation)   -> in scope
    TOPIC            everything else                  -> OUT of scope

This is a bounded, deterministic, model-free filter, and it is the salience
step that entries 27-29 were missing. Kang et al. (arXiv:2606.10616) show
LLM importance SCORING sits at F1 0.020-0.027 against gold evidence, so a
scorer is not the answer; a scope rule is.

CAVEAT, stated because it is the obvious failure mode: this schema cannot
capture facts about third parties the user cares about but never marks as
theirs ("Sarah got promoted", where Sarah is a colleague named only once). The
ORBIT rule catches those only once a relationship has been stated. Expect
recall loss on exactly that population; whether it matters is measurable and
not yet measured.
"""

import re

SELF = "SELF"
SELF_POSSESSIVE = "SELF_POSSESSIVE"
ORBIT = "ORBIT"
TOPIC = "TOPIC"
IN_SCOPE = (SELF, SELF_POSSESSIVE, ORBIT)

# relations that state a personal relationship; their OBJECT enters the orbit
_RELATIONSHIP = re.compile(
    r"\b(married|wife|husband|partner|sibling|brother|sister|parent|mother|"
    r"father|son|daughter|child|children|cousin|friend|colleague|coworker|"
    r"co-worker|boss|manager|manages|reports? to|works? (?:at|for)|employed|"
    r"landlord|neighbour|neighbor|dentist|doctor|therapist|classmate|"
    r"teammate|roommate|flatmate)\b", re.I)

_SELF = re.compile(r"^\s*(i|me|myself)\s*$", re.I)
_SELF_POSS = re.compile(r"^\s*(my|our)\b", re.I)
# role-qualified names the extractor emits, e.g. "Dana (colleague)".
# Must be a ROLE word, not any parenthetical: "Burke et al. (2010)" is a
# citation, not a person in the user's life, and matched the naive pattern.
_ROLE = (r"brother|sister|sibling|cousin|colleague|coworker|co-worker|friend|"
         r"neighbour|neighbor|manager|boss|landlord|dentist|doctor|therapist|"
         r"classmate|teammate|roommate|flatmate|wife|husband|partner|mother|"
         r"father|parent|son|daughter|child|uncle|aunt|nephew|niece|"
         r"mother-in-law|father-in-law|sister-in-law|brother-in-law")
_QUALIFIED = re.compile(rf"\(\s*(?:my\s+)?(?:{_ROLE})[^)]*\)\s*$", re.I)


class Scope:
    """Tracks which entities are in the speaker's orbit, learned from the
    relationship facts the speaker states. Grows as the transcript proceeds —
    an entity is in orbit from the point a relationship is asserted, not
    retroactively, which is the honest behaviour for a streaming memory."""

    def __init__(self):
        self.orbit = set()

    def observe(self, triple):
        """A stated relationship puts the other party in orbit."""
        s, r, o = [str(x).strip() for x in triple]
        if _QUALIFIED.search(s):
            self.orbit.add(_norm(s))
        if _RELATIONSHIP.search(r) and (_SELF.match(s) or _SELF_POSS.match(s)):
            self.orbit.add(_norm(o))
        if _QUALIFIED.search(o):
            self.orbit.add(_norm(o))

    def classify(self, subject):
        s = str(subject).strip()
        if _SELF.match(s):
            return SELF
        if _SELF_POSS.match(s):
            return SELF_POSSESSIVE
        if _norm(s) in self.orbit:
            return ORBIT
        return TOPIC

    def in_scope(self, subject):
        return self.classify(subject) in IN_SCOPE


def _norm(x):
    x = re.sub(r"\s*\([^)]*\)\s*$", "", str(x).strip().lower())
    return re.sub(r"\s+", " ", x).strip(" .,!?")
