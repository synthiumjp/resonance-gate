"""The refusal suite: what the extractor must NOT assert, and why.

STRUCTURE (CheckList, Ribeiro et al. ACL 2020) x INVENTORY (CommitmentBank,
de Marneffe/Simons/Tonhauser 2019).

CommitmentBank organises speaker commitment around four ENTAILMENT-CANCELLING
OPERATORS -- negation, modal, question, conditional antecedent -- crossed with
the embedding predicate's factivity. That is the taxonomy this parser has been
rediscovering one bug at a time: e235 found questions, e264 found questions
inside questions, e265 found conditionals. This file replaces that whack-a-mole
with the inventory.

CheckList supplies the test TYPES, and the second one is the point:

  MFT  the irrealis frame must NOT produce the proposition
  DIR  the MATCHED DECLARATIVE must produce it
  INV  refusal survives paraphrasing the marker

DIR is what makes an MFT meaningful. "The parser emitted nothing" is not
evidence of correct refusal -- it is equally consistent with the parser simply
failing on the sentence. Only the pair (suppressed under the operator, emitted
without it) shows the operator is what did the work.

A case with `assert_instead` is one where something MUST still be stored: a
negation asserts its negative, and a FACTIVE predicate presupposes its
complement even under negation or a question ("I regret that I left Perrin"
commits to leaving; so does "I don't regret that I left Perrin").
A case may carry `unless_contains`: a record containing the forbidden string
is FORGIVEN when it also carries that marker, because the embedding predicate
is what makes it honest. "<owner> doubts that <owner> will move to Berlin" is
a correct fact; "<owner> will move to Berlin" standing alone is not.
"""

# capability, operator, irrealis frame, what must not appear, the matched
# declarative control, what that control must produce, and -- when the
# irrealis frame still owes a fact -- what it must produce instead.
CASES = [
    # ---- OPERATOR 1: QUESTION --------------------------------------------
    dict(capability="question", operator="polar interrogative",
         role="assistant",
         irrealis="Are you interested in attending conferences?",
         must_not="interested in attending",
         control="I am interested in attending conferences.",
         control_role="user", control_asserts="interested in attending"),

    dict(capability="question", operator="existential interrogative",
         role="assistant",
         irrealis="Are there specific workshops you're particularly drawn to?",
         must_not="drawn to",
         control="I am particularly drawn to workshops.",
         control_role="user", control_asserts="drawn to"),

    dict(capability="question", operator="wh-interrogative, subject position",
         role="assistant",
         irrealis="What aspects of remote work are most valuable to you?",
         must_not="most valuable",
         control="Remote work is most valuable to me.",
         control_role="user", control_asserts=None),

    dict(capability="question", operator="wh-interrogative, object position",
         role="assistant",
         irrealis="Which language do you use at work?",
         must_not="use at work",
         control="I use Go at work.",
         control_role="user", control_asserts="uses Go"),

    dict(capability="question", operator="tag question",
         role="assistant",
         irrealis="You work at Lumen Health, don't you?",
         must_not=None,          # documents current behaviour; see the test
         control="I work at Lumen Health.",
         control_role="user", control_asserts="works at Lumen Health"),

    # ---- OPERATOR 2: CONDITIONAL ANTECEDENT ------------------------------
    dict(capability="conditional", operator="if-antecedent",
         role="user",
         irrealis="If I moved to Berlin I would need to learn German.",
         must_not="moved to Berlin",
         control="I moved to Berlin.",
         control_role="user", control_asserts="moved to Berlin"),

    dict(capability="conditional", operator="if-consequent",
         role="user",
         irrealis="If I moved to Berlin I would need to learn German.",
         must_not="need to learn German",
         control="I need to learn German.",
         control_role="user", control_asserts="learn German"),

    dict(capability="conditional", operator="unless",
         role="user",
         irrealis="Unless I find a new job I will stay at Acme.",
         must_not="find a new job",
         control="I found a new job.",
         control_role="user", control_asserts="found a new job"),

    dict(capability="conditional", operator="counterfactual past",
         role="user",
         irrealis="If I had taken the Perrin offer I would be in Berlin now.",
         must_not="taken the Perrin offer",
         control="I took the Perrin offer.",
         control_role="user", control_asserts="took the Perrin offer"),

    # a PRESUPPOSITION under the same tree shape -- must SURVIVE (e235)
    dict(capability="conditional", operator="since-clause (NOT conditional)",
         role="user",
         irrealis="Since I moved to Albi I have been happier.",
         must_not=None,
         control="I moved to Albi.",
         control_role="user", control_asserts="moved to Albi",
         assert_instead="moved to Albi"),

    dict(capability="conditional", operator="when-clause (NOT conditional)",
         role="user",
         irrealis="When I moved to Berlin I learned German.",
         must_not=None,
         control="I moved to Berlin.",
         control_role="user", control_asserts="moved to Berlin",
         assert_instead="moved to Berlin"),

    # ---- OPERATOR 3: MODAL ------------------------------------------------
    dict(capability="modal", operator="epistemic possibility",
         role="user",
         irrealis="I might switch to Rust next year.",
         must_not=None,
         control="I switched to Rust.",
         control_role="user", control_asserts="switched to Rust"),

    dict(capability="modal", operator="future intention",
         role="user",
         irrealis="I am going to learn Rust.",
         must_not=None,
         control="I learned Rust.",
         control_role="user", control_asserts="learned Rust"),

    dict(capability="modal", operator="deontic",
         role="user",
         irrealis="I should really move closer to the office.",
         must_not=None,
         control="I moved closer to the office.",
         control_role="user", control_asserts="moved closer"),

    # ---- OPERATOR 4: NEGATION --------------------------------------------
    dict(capability="negation", operator="verbal negation",
         role="user",
         irrealis="I don't drink coffee.",
         must_not="drinks coffee",
         control="I drink coffee.",
         control_role="user", control_asserts="drinks coffee",
         assert_instead="does not drink coffee"),

    dict(capability="negation", operator="copular negation",
         role="user",
         irrealis="I am not a vegetarian.",
         must_not=None,
         control="I am a vegetarian.",
         control_role="user", control_asserts="is a vegetarian"),

    dict(capability="negation", operator="never",
         role="user",
         irrealis="I have never worked at Perrin.",
         must_not=None,
         control="I have worked at Perrin.",
         control_role="user", control_asserts="has worked at Perrin"),

    # ---- FACTIVITY: the embedding predicate -------------------------------
    # A NON-FACTIVE attitude verb does not commit its speaker to the
    # complement; a FACTIVE one presupposes it, even under negation.
    # `unless_contains` makes the MFT precise rather than substring-blind:
    # "<owner> doubts that <owner> will move to Berlin" is a CORRECT record
    # and it contains the forbidden string. What must not exist is the
    # complement standing ALONE as its own assertion.
    dict(capability="factivity", operator="non-factive (doubt)",
         role="user",
         irrealis="I doubt that I will move to Berlin.",
         must_not="will move to Berlin", unless_contains="doubt",
         control="I will move to Berlin.",
         control_role="user", control_asserts=None),

    dict(capability="factivity", operator="non-factive (think)",
         role="user",
         irrealis="I think the billing service is written in Go.",
         must_not=None,
         control="The billing service is written in Go.",
         control_role="user", control_asserts=None),

    dict(capability="factivity", operator="factive (regret) -- presupposes",
         role="user",
         irrealis="I regret that I left Perrin.",
         must_not=None,
         control="I left Perrin.",
         control_role="user", control_asserts="left Perrin",
         assert_instead="left Perrin"),

    # ---- LOADED QUESTIONS: an assistant must not inject by presupposition --
    # "When did you stop working at Perrin?" PRESUPPOSES that the user worked
    # there and stopped. If the store inherited an assistant's presupposition,
    # the assistant could write the user's memory by asking questions. These
    # currently pass; the rows exist so that stays true.
    dict(capability="question", operator="loaded question (change-of-state)",
         role="assistant",
         irrealis="When did you stop working at Perrin?",
         must_not="Perrin",
         control="I stopped working at Perrin.",
         control_role="user", control_asserts="stopped working at Perrin"),

    dict(capability="question", operator="loaded question (why-presupposition)",
         role="assistant",
         irrealis="Why did you leave Perrin?",
         must_not="leave Perrin",
         control="I left Perrin.",
         control_role="user", control_asserts="left Perrin"),

    dict(capability="question", operator="loaded question (how-long)",
         role="assistant",
         irrealis="How long have you been vegetarian?",
         must_not="vegetarian",
         control="I have been vegetarian for six years.",
         control_role="user", control_asserts="has been vegetarian"),

    # ---- MODAL: the modal must SURVIVE into the record ---------------------
    # A modal is not refused -- "I might switch to Rust" is worth storing. What
    # must never happen is the modal being dropped, leaving a bare assertion
    # the speaker never made. `unless_contains` states exactly that.
    dict(capability="modal", operator="epistemic (might)",
         role="user",
         irrealis="I might switch to Rust next year.",
         must_not="switch to Rust", unless_contains="might",
         control="I switched to Rust.",
         control_role="user", control_asserts="switched to Rust",
         assert_instead="might switch to Rust"),

    dict(capability="modal", operator="epistemic (may)",
         role="user",
         irrealis="I may move to Berlin.",
         must_not="move to Berlin", unless_contains="may",
         control="I moved to Berlin.",
         control_role="user", control_asserts="moved to Berlin",
         assert_instead="may move to Berlin"),

    dict(capability="modal", operator="ability (could)",
         role="user",
         irrealis="I could take the Perrin offer.",
         must_not="take the Perrin offer", unless_contains="could",
         control="I took the Perrin offer.",
         control_role="user", control_asserts="took the Perrin offer",
         assert_instead="could take the Perrin offer"),

    # ---- the user's OWN question still presupposes ------------------------
    # Symmetric with the loaded-question rows above: an assistant's
    # presupposition must NOT be inherited, but the user's own is theirs to
    # make. Same tree shape, opposite disposition, decided by ROLE.
    dict(capability="question", operator="user's own presupposition",
         role="user",
         irrealis="Since I moved to Albi, how do I get residency?",
         must_not=None,
         control="I moved to Albi.",
         control_role="user", control_asserts="moved to Albi",
         assert_instead="moved to Albi"),

    dict(capability="factivity", operator="assistant hearsay (report frame)",
         role="assistant",
         irrealis="I remember you mentioning that you play the cello.",
         must_not=None,          # tiered as hearsay, not asserted -- see test
         control="I play the cello.",
         control_role="user", control_asserts="plays the cello"),
]

# INVARIANCE: refusal must survive rewording the MARKER, not just the one
# phrasing a bug happened to be found in.
# `unless` is required for negation: EVERY correct negated record contains its
# own positive as a substring ("<owner> no longer drinks coffee" contains
# "drinks coffee"). What must not exist is the positive standing free of any
# negator, so the test asks for the negator rather than for the absence of the
# verb.
INVARIANCE = [
    dict(capability="conditional", needle="moved to Berlin", role="user",
         variants=[
             "If I moved to Berlin I would need German.",
             "If I were to move to Berlin I would need German.",
             "Supposing I moved to Berlin, I would need German.",
             "Assuming I moved to Berlin, I would need German.",
             "Provided I moved to Berlin, I would need German.",
         ]),
    dict(capability="question", needle="interested in Rust", role="assistant",
         variants=[
             "Are you interested in Rust?",
             "Would you be interested in Rust?",
             "Is there any chance you're interested in Rust?",
             "Could you be interested in Rust?",
         ]),
    dict(capability="negation", needle="drink", role="user",
         unless=("not", "never", "no longer", "hardly", "stopped", "n't"),
         variants=[
             "I don't drink coffee.",
             "I no longer drink coffee.",
             "I have never drunk coffee.",
             "I hardly ever drink coffee.",
             "I stopped drinking coffee.",
         ]),
    # e271: this row found a real leak. A fronted epistemic adverb was being
    # dropped as a discourse adverb, so "Perhaps I will switch to Rust" stored
    # a plain future the speaker never asserted.
    dict(capability="modal", needle="switch to Rust", role="user",
         unless=("might", "may", "could", "perhaps", "maybe", "possibly",
                 "probably", "presumably", "potentially"),
         variants=[
             "I might switch to Rust.",
             "I may switch to Rust.",
             "Perhaps I will switch to Rust.",
             "Maybe I will switch to Rust.",
             "Possibly I will switch to Rust.",
             "I could switch to Rust.",
         ]),
    dict(capability="factivity", needle="left Perrin", role="user",
         unless=("doubt", "deny", "denies", "dispute", "disputes",
                 "contest", "refute"),
         variants=[
             "I deny that I left Perrin.",
             "I dispute that I left Perrin.",
             "I doubt that I left Perrin.",
             "I refute that I left Perrin.",
         ]),
]
