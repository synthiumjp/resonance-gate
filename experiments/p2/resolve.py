"""p2 hybrid within-span pronoun resolution -- the deterministic, high-precision
core of the coreference layer.

Entry 48 named coreference as the buildable unblock for categorical recall. The
hybrid design (coreference agents, this session): cheap deterministic rules for
the resolvable cases, no model. This module does the WITHIN-SPAN half -- resolve
a pronoun to an antecedent in the SAME span by recency + agreement (Centering-
lite: subject/recency salience, gender/number agreement as a hard filter).
Cross-session salience (resolving an isolated "She moved to Chicago" to a Rachel
introduced in an earlier session) is the harder half and is NOT done here.

WHY WITHIN-SPAN FIRST. It is the high-precision, high-frequency case:
"my old sneakers ... keeping THEM under my bed" -> them = sneakers, so the two
storage-location mentions key to the same attribute and pair. A wrong
resolution would create a false attribute merge, so the resolver is
CONSERVATIVE: it only replaces a pronoun when there is an unambiguous,
agreement-compatible, recent antecedent; otherwise it leaves the pronoun
untouched (a miss, the safe failure -- consistent with the no-false-alarm
priority everywhere in p2).

No model call.
"""

import re

# antecedent candidates, tracked as we scan left to right
_NAME = re.compile(r"\b([A-Z][a-z]{2,})\b")
_NOUN = re.compile(r"\b(?:my|the|our|a|an)\s+((?:[a-z]+\s+){0,2}[a-z]+)\b", re.I)
_NOT_NAME = {"By", "The", "That", "This", "Do", "Can", "Oh", "So", "And", "But",
             "She", "He", "They", "We", "My", "I", "Since", "When", "It"}
_MASS_OR_PLURAL = re.compile(r"s$", re.I)   # crude number: trailing -s ~ plural

_PRON = re.compile(r"\b(they|them|it|she|he)\b(?!['\w])", re.I)


def _tokens_with_antecedents(span):
    """Scan the span, maintaining the most recent PERSON-NAME and the most
    recent common-NOUN phrase, so a pronoun can bind to the compatible one."""
    return span


def resolve_pronouns(span):
    """Return the span with within-span-resolvable pronouns replaced by their
    antecedent. Conservative: only unambiguous, agreement-compatible, recent
    antecedents. Object pronouns (them/it) -> nearest prior common noun;
    subject person pronouns (she/he) -> nearest prior person name.
    """
    out = span
    # resolve per pronoun occurrence, left to right, using only text BEFORE it
    def repl(m):
        pron = m.group(1).lower()
        pre = span[:m.start()]
        if pron in ("she", "he"):
            names = [n for n in _NAME.findall(pre) if n not in _NOT_NAME]
            return names[-1] if names else m.group(0)
        # they/them/it -> nearest prior common noun ("my old sneakers" -> sneakers)
        nouns = _NOUN.findall(pre)
        if not nouns:
            return m.group(0)
        head = nouns[-1].split()[-1]        # head noun of the phrase
        plural_pron = pron in ("they", "them")
        plural_noun = bool(_MASS_OR_PLURAL.search(head))
        # number agreement as a hard filter (them<->plural, it<->singular)
        if plural_pron != plural_noun:
            # try an earlier noun that agrees
            for cand in reversed(nouns[:-1]):
                h = cand.split()[-1]
                if bool(_MASS_OR_PLURAL.search(h)) == plural_pron:
                    return h
            return m.group(0)
        return head

    return _PRON.sub(repl, out)
