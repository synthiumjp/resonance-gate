"""Minimal spaCy-Token-shaped test fixtures (duck-typed: .text, .pos_,
.dep_, .head) for exercising binding.py / cues_gate.py without a real
spaCy install. Not a test module itself -- no test_ functions here."""

from dataclasses import dataclass


@dataclass
class Tok:
    text: str
    pos_: str
    dep_: str
    head: "Tok" = None

    def __post_init__(self):
        if self.head is None:
            self.head = self


def reflexive_same_clause():
    """'Rachel saw herself.' -- Condition A satisfied: herself binds
    Rachel within their single shared clause."""
    saw = Tok("saw", "VERB", "ROOT")
    rachel = Tok("Rachel", "PROPN", "nsubj", head=saw)
    herself = Tok("herself", "PRON", "dobj", head=saw)
    return herself, rachel


def reflexive_cross_clause():
    """'Rachel said Tom hurt himself.' -- 'himself' must bind Tom (its own
    clause), never Rachel (the outer clause)."""
    said = Tok("said", "VERB", "ROOT")
    rachel = Tok("Rachel", "PROPN", "nsubj", head=said)
    hurt = Tok("hurt", "VERB", "ccomp", head=said)
    tom = Tok("Tom", "PROPN", "nsubj", head=hurt)
    himself = Tok("himself", "PRON", "dobj", head=hurt)
    return himself, tom, rachel


def condition_b_same_clause():
    """'Rachel saw her.' -- 'her' cannot corefer with Rachel: the
    same-clause subject c-commands the object pronoun."""
    saw = Tok("saw", "VERB", "ROOT")
    rachel = Tok("Rachel", "PROPN", "nsubj", head=saw)
    her = Tok("her", "PRON", "dobj", head=saw)
    return her, rachel


def cross_sentence_pronoun():
    """'Rachel moved. She moved to Chicago.' -- separate sentences/parse
    trees; binding theory correctly has no opinion here."""
    moved1 = Tok("moved", "VERB", "ROOT")
    rachel = Tok("Rachel", "PROPN", "nsubj", head=moved1)
    moved2 = Tok("moved", "VERB", "ROOT")   # own ROOT: a separate sentence
    she = Tok("She", "PRON", "nsubj", head=moved2)
    return she, rachel
