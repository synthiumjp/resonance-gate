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

    # ---- NEGATION OVER THE MATRIX PREDICATE (review 2026-09-05) ----------
    # CommitmentBank's core case: negation on a NON-FACTIVE matrix cancels
    # the complement's entailment. "I wouldn't say I'm a vegetarian" stored
    # "<owner> is a vegetarian" -- the complement standing alone, as if the
    # speaker had asserted it. Three surface forms, one operator.
    dict(capability="negation", operator="metalinguistic (it's not true that)",
         role="user",
         irrealis="It's not true that I moved to Berlin.",
         must_not="moved to Berlin",
         control="It is true that I moved to Berlin.",
         control_role="user", control_asserts="moved to Berlin"),

    dict(capability="negation", operator="negated non-factive matrix (wouldn't say)",
         role="user",
         irrealis="I wouldn't say I'm a vegetarian.",
         must_not="is a vegetarian", unless_contains="say",
         control="I'd say I'm a vegetarian.",
         control_role="user", control_asserts="is a vegetarian"),

    dict(capability="negation", operator="negated non-factive matrix (never said)",
         role="user",
         irrealis="I never said I was a vegetarian.",
         must_not="was a vegetarian", unless_contains="said",
         control="I said I was a vegetarian.",
         control_role="user", control_asserts="was a vegetarian"),

    # the FACTIVE counterpart must SURVIVE negation of its matrix
    dict(capability="negation", operator="negated factive matrix -- presupposes",
         role="user",
         irrealis="I don't regret that I left Perrin.",
         must_not=None,
         control="I regret that I left Perrin.",
         control_role="user", control_asserts="left Perrin",
         assert_instead="left Perrin"),

    # negation carried on the SUBJECT, not the verb
    dict(capability="negation", operator="neither/nor coordinated subject",
         role="user",
         irrealis="Neither my wife nor I like horror movies.",
         must_not="like horror movies", unless_contains="not",
         control="My wife and I like horror movies.",
         control_role="user", control_asserts="like horror movies",
         assert_instead="not like horror movies"),

    # ---- THIRD-PARTY ATTITUDE (review 2026-09-05) --------------------------
    # The complement of a NON-FACTIVE attitude/report verb whose subject is
    # someone OTHER than the owner is that person's claim, not the owner's
    # fact. "My mom says I'm lazy" stored "<owner> is lazy"; "My friend thinks
    # I should quit my job" stored "<owner> should quit <owner>'s job" -- a
    # friend's advice indistinguishable from the owner's own plan. The matrix
    # record ("<owner>'s mom says ...") is the honest form and must stay.
    dict(capability="factivity", operator="third-party report (my mom says)",
         role="user",
         irrealis="My mom says I'm lazy.",
         must_not="is lazy", unless_contains="says",
         control="I'm lazy.",
         control_role="user", control_asserts="is lazy"),

    dict(capability="factivity", operator="third-party attitude (my friend thinks)",
         role="user",
         irrealis="My friend thinks I should quit my job.",
         must_not="should quit", unless_contains="thinks",
         control="I should quit my job.",
         control_role="user", control_asserts="should quit"),

    dict(capability="factivity", operator="generic-subject attitude (people think)",
         role="user",
         irrealis="People think I'm rude.",
         must_not="is rude", unless_contains="think",
         control="I'm rude.",
         control_role="user", control_asserts="is rude"),

    # the owner's OWN attitude verb still lets the complement through
    dict(capability="factivity", operator="owner's own report (I'd say)",
         role="user",
         irrealis="I'd say I'm a vegetarian.",
         must_not=None,
         control="I'm a vegetarian.",
         control_role="user", control_asserts="is a vegetarian",
         assert_instead="is a vegetarian"),

    # ---- NEGATION THAT DOES NOT CANCEL (review 2026-10-02) ------------------
    # e278's `_negated_matrix` cancelled the complement under ANY negated
    # matrix that was not on a short factive list, and the review found true
    # facts it now loses: "I can't believe I got the job" stored NOTHING.
    # Added before the fix. Two failed (can't believe, never knew: nothing
    # stored at all). The rest PASS on the matrix record, which carries the
    # complement ("did not know Alex Reyes had a brother") and which the
    # product read path retrieves -- verified 2026-10-02 -- so they guard
    # against total loss, not against losing the bare duplicate.
    dict(capability="negation", operator="incredulity (can't believe) -- presupposes",
         role="user",
         irrealis="I can't believe I got the job.",
         must_not=None,
         control="I got the job.",
         control_role="user", control_asserts="got the job",
         assert_instead="got the job"),

    dict(capability="negation", operator="past ignorance (didn't know) -- presupposes",
         role="user",
         irrealis="I didn't know I had a brother.",
         must_not=None,
         control="I had a brother.",
         control_role="user", control_asserts="had a brother",
         assert_instead="had a brother"),

    dict(capability="negation", operator="past ignorance (never knew) -- presupposes",
         role="user",
         irrealis="I never knew I had a brother.",
         must_not=None,
         control="I had a brother.",
         control_role="user", control_asserts="had a brother",
         assert_instead="had a brother"),

    dict(capability="negation", operator="negated telling scopes over the telling",
         role="user",
         irrealis="I haven't told my parents I moved to Berlin.",
         must_not=None,
         control="I moved to Berlin.",
         control_role="user", control_asserts="moved to Berlin",
         assert_instead="moved to Berlin"),

    # present-tense "don't know that" IS a hedge, unlike "didn't know"
    dict(capability="negation", operator="present hedge (don't know that)",
         role="user",
         irrealis="I don't know that I'm a good cook.",
         must_not="is a good cook", unless_contains="know",
         control="I'm a good cook.",
         control_role="user", control_asserts="is a good cook"),

    # ---- THIRD-PARTY REPORTS KEEP THE ATTRIBUTED FORM ------------------------
    # "The doctor told me I have diabetes" no longer stores the bare fact, but
    # the attributed record survives and answers "Do I have diabetes?" at
    # rank 1 (verified through the product read path, 2026-10-02). These rows
    # lock that in: the fact must stay in the store, WITH its source.
    dict(capability="factivity", operator="third-party news told to the owner",
         role="user",
         irrealis="The doctor told me I have diabetes.",
         must_not=None,
         control="I have diabetes.",
         control_role="user", control_asserts="has diabetes",
         assert_instead="has diabetes"),

    # the owner as a CO-subject is the owner's own attitude, not a third party's
    dict(capability="factivity", operator="owner-inclusive plural attitude",
         role="user",
         irrealis="My wife and I think we should move to Berlin.",
         must_not=None,
         control="We should move to Berlin.",
         control_role="user", control_asserts="should move to Berlin",
         assert_instead="should move to Berlin"),

    # a modal inside an ASSISTANT report frame must survive into the record
    dict(capability="modal", operator="modal under a report frame (assistant)",
         role="assistant",
         irrealis="I heard you might be interested in learning Swift.",
         must_not="interested in learning Swift", unless_contains="might",
         control="I am interested in learning Swift.",
         control_role="user", control_asserts="interested in learning Swift"),

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
    # review 2026-09-05: negation over the matrix predicate, five wordings
    dict(capability="negation", needle="vegetarian", role="user",
         unless=("not", "never", "n't", "doubt"),
         variants=[
             "I wouldn't say I'm a vegetarian.",
             "I don't think I'm a vegetarian.",
             "I never said I was a vegetarian.",
             "It's not true that I'm a vegetarian.",
             "I'm not sure I'm a vegetarian.",
             "I can't say I'm a vegetarian.",
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
