# How sourcedrecall reads a conversation

sourcedrecall decides what to store, and what has gone out of date, with a
grammar parser and rules taken from linguistics, not with a language model.
Each rule below is a claim about English that the benchmarks can support or
refute. For each: what it says, where the idea comes from, examples both
ways, and what was measured. Rules that were tried and failed are listed at
the end with their numbers.

The parser is Stanza 1.14.0's English pipeline (Universal Dependencies
parses), run without PyTorch through `stanza_ort`; the rules are in `rgx/`
and `experiments/p2/`. Measurements come from `bench/` (readable development
sets unless marked held out; held-out sets were written before any system
saw them and are read only as counts). Last measured 2026-10-07.

## Held-out test (v5, pre-registered)

The rules below were tested once on a set nobody working on the system had
read: 120 scenarios written by an agent from a brief without the rules' word
lists, with hypotheses fixed beforehand (`docs/PREREG_HELDOUT_V5.md`,
results in `bench/false_memory/results_v5/SUMMARY.md`). Five of seven met,
two missed:
- met: old state given as current 0/25 for stated changes and 3/25 for
  implied ones (plain retrieval 4 and 7); no change label on a current fact
  (0/20); decisions recalled 10/10, a declined proposal given as decided
  0/10; the claim check said "said" for 1 of 12 denied, hedged,
  assistant-only or never-said claims; advice, the right conversation in the
  top 5 10/10.
- missed: the labels on implied changes ("may have changed since" on 2 of
  25 scenarios against at least 12 hypothesised; the answers were right in
  22 of 25 from the dated quotes), and "no longer true" did not beat its base
  rate as screened (3 of its 4 lines marked the right fact, phrased as an
  event the screen could not match).

## Which words count as the user's own

**Questions are not statements.** A clause whose subject or head is a
wh-word, or with the auxiliary before the subject, asks rather than asserts
(subject-auxiliary inversion). People leave out the question mark, so a
clause that opens with the inverted auxiliary or a wh-word counts too, and
so does a wh-word that determines one of the clause's arguments.
- not stored: "which errors should I retry in general", "should i add a test in the same commit"
- stored: "Never have I been so sure" is fronting, not a question, and is left alone
- Status: supported. "which errors should I retry" had been stored as a fact
  in every coding scenario's background; with the rule, none.

**Hedges, reports and wishes are not assertions.** "I don't think I'm
lactose intolerant", "My dad keeps telling me I'm too stubborn", "I wish I
could surf", "Maybe we rewrite it in Rust" store nothing about the user.
- Status: supported in the parser since 0.4 (irrealis and report frames).

**Pasted text is someone else's words.** A message that introduces material
("Can you summarise this email?", "Here's the README:", "from a webpage:")
and an email-shaped block (greeting ... sign-off) are kept but not read as
the user's statements.
- A pasted "Never send drafts to the client directly" had become a standing
  instruction; with the rule it does not. Over all 5,882 LoCoMo messages and
  the development sets, the rule changed no message.
- Status: supported.

## Standing instructions

**An English imperative is the base form of the verb with no subject.** A
subjectless clause with always/never/don't, "from now on", or a habit verb
with an object ("Keep answers terse", "Avoid red and green in charts") is an
instruction to the assistant, and leads every later session.
- instruction: "Please never add comments to my code", "From now on always answer in British English"
- not: "Haven't set foot in the Leeds office since they went remote" and
  "Not freelancing any more" (a perfect and a gerund, not base forms);
  "Fix the failing test" (a one-off request)
- Status: supported. The base-form test was added 2026-10-05 after both
  "not" examples had been stored as instructions.

## Facts that went out of date

**A later statement of the same kind of state replaces an earlier one.**
Residence, employer, role, relationship and similar states are single-valued:
"I moved to Brunswick" after "I live in Fitzroy" makes the Fitzroy fact "no
longer true".
- Label screening, all 12 sets: "no longer true" was never shown on a line
  about the current state.
- Status: supported; the most reliable label.

**A remark tied to its moment is said in passing.** A temporal adverbial of
the present ("today", "this week", "at the moment") or a mood ("so tired")
marks a statement that was true when said and need not be now; it never
replaces a lasting fact.
- passing: "I'm eating keto today", "I'm in Sydney this week"
- not passing (a change of state said "today"): "They made me a senior
  designer today", "We got married on Saturday", "The MacBook Air arrived today"
- Status: supported after the 2026-10-05 fix; before it, the label was shown
  on 4 lines about the current state in one development set (now 2).

**A change of state names its domain (soft link).** A change-of-state verb
carries its domain in its frame -- the preposition or object it takes
(subcategorisation): graduate and enrol (study); promoted, started at/as,
made me a..., report to, transfer to (work); got engaged, broke up
(relationship); moved to/into/out, closed on a house (home); gave up, went
vegan, quit smoking (diet). Without the frame there is no change: "I moved
the sofa", "I started a new book", "I made a cake", "I closed the window". A generic change (switch, trade in, replace, give
up) takes the domain of its object, from WordNet's hypernym hierarchy: a
paramedic and a pharmacy assistant are both workers, decaf and coffee both
beverages, a "vegan" is an eater and so not a worker. A contrast marker
("now", "back to", "instead", "has been ... since", which presupposes a
starting point) links within a named domain. News about the user's people
never counts ("my friend Dev just started at Birch"). A link made this way is
marked "may have changed since", not "no longer true".
- Readable change sets: of 54 out-of-date facts the parser had not marked,
  22 now are, with 0 false marks in 136 scenarios where nothing changed.
  Held out (v2-v4): 4 more of 27, 0 false marks in 92.
- Status: supported, with a known gap: brand names (ThinkPad, Kia,
  Symbicort, futsal) are not in WordNet.

**Presupposition triggers state a new situation without asserting it.** An
ordinal with a time unit ("Fourth week as a paramedic", "First week at
Kestrel Print"), a phase ("Day ten of decaf", "Six weeks into drums") or a
duration with someone ("Three months with Daniel now", "Anniversary dinner
with Ben") takes for granted a state that began recently (Karttunen 1974;
Levinson 1983 on presupposition triggers). The presupposed state is read as
its own statement, with "now" for its onset; receipts quote what was said.
- not triggered: "First day at the beach was fun" (a place, not an
  organisation), "Three weeks with no rain" (not a name), and anything the
  sentence places in the past or a story ("First year at Oxford was hard
  back in 1998", "Five years with Jenny ended in 2010", "in the book") or
  ends ("Second week at Tesco I quit")
- Known failure: "Second week at Disneyland was exhausting" reads as a job.
  Telling a destination from a workplace needs knowledge of the place.
- Status: supported in the parser tests; the adversarial review's 28
  counterexamples fired 19 times before the past and ending conditions.

**"May have changed since" needs the newer statement to be the user's own,
its change word in its own clause, and a relation to the older fact**: the
same kind of state, a shared word in the two values, or the same kind of
thing in WordNet. An earlier version also accepted embedding similarity of
0.5; the adversarial review showed it links unrelated pairs ("I live in
Fitzroy" / "I moved the sofa", cosine above 0.5), and it was removed.
- Label screening: in coding sessions the label had fired 31 and 35 times at
  about 6% precision, on talk full of "now", "new" and "switched"; after the
  fix 8 and 3. On the held-out change set v4, answers were unchanged (old
  state given as current 2/44, new state 41/44, unchanged things 16/16).
- Status: supported; it now catches fewer true changes (4 instead of 8 lines
  on v4), the cost of not crying wolf. Held out (v5): no false change label
  in 20 no-change scenarios, but labelled only 2 of 25 implied changes:
  refuted as a signal of implied change; the answers did not need it.

## Decisions made with the assistant

**An accepted proposal is the user's decision.** In dialogue-act terms the
assistant's turn is a suggestion or offer and the user's turn an acceptance.
The acceptance must be the whole turn -- the assent alone ("yes do it",
"sounds good, go ahead") or the assent and the action restated ("ok use
pnpm", "alright let's switch to Tailwind") -- with no reservation ("ok but
keep npm", "maybe later"), not a question, and answering a proposal in the
assistant's last two sentences. A user's own "let's X" is one too, without
"later" or "tomorrow". The adversarial review's 25 counterexamples ("Perfect,
it works now", "yes I did", "alright, I read it" after a suggestion) fired
21 times before the whole-turn condition, none after on the ones re-tested. A later decision that says it changes something
("switch back to npm") replaces the earlier one.
- Readable set of 24 scenarios (`cases_dev_decisions.jsonl`), answer level
  with the rule after the adversarial review: decisions recalled 4/10 ->
  7/10; after a reversal, the new choice given 5/9 -> 8/9; a declined
  proposal or a replaced decision given as current 0/14 -> 1/14 (after "ok
  migrate it" to Postgres, "use SQLite for now" was not marked replaced: the
  two share no word and their embeddings are not close).
- An acceptance can also act on the proposal ("ok migrate it", "yeah
  perfect, move it") or name the choice ("path versioning it is"); an offer
  that follows a proposal ("We could use go-cmp. Want me to rewrite the
  assertions?") is joined to it.
- Status: supported, held out (v5): accepted decisions recalled 10/10, a
  declined or deferred proposal given as decided 0/10.

## Notes written by the small model

**Person deixis is resolved before the model reads a conversation.** "I"
and "my" point at whoever is speaking, "you" and "your" at the listener
(Bühler's origo; Levinson 1983 on person deixis). A 0.6B model loses track
of who is speaking and gives the user the other person's news: Melanie's "I
took the kids to the museum" became "Caroline has kids" in Caroline's notes.
So each pronoun is replaced by who it refers to, with the verb agreeing:
"Yesterday I took the kids" from the other side becomes "Yesterday Other
took the kids", and the user's "your kids must love it" becomes "Other's
kids must love it". English personal pronouns are a closed class, so this
is a deterministic rewrite (`notes.explicit_person`).
- LoCoMo development conversations, notes judged against their session by
  Qwen3-14B, the same training data with and without the rewrite: notes
  right 348 -> 381 (76% -> 80%), notes giving the user the other speaker's
  facts 75 -> 62 (16% -> 13%; Qwen3-14B's own notes 3%).
- Status: supported, partial. Most remaining errors carry no pronoun ("the
  kids", "the studio"): the model fuses the conversation's topic onto the
  user, which is not a deixis error.

Tried and refuted for the same problem (output filters, after the model):
- Dropping a note that leans on words only the other side used: judged
  right 77% -> 85%, but answers fell 69.1% -> 67.4% (+4/-8): it removed true
  notes, including true notes about the other person.
- Reading person off the parse of the user's sentences (a note noun the
  user only ever possesses as "your X" or uses under a "you" subject): it
  caught a third of the wrong-person notes and lost one right note for
  every two wrong ones. Its misses ("I'd love to see the kids") carry no
  person at all: once the note is written, the information is gone.

## Finding the right messages

**A request for advice is answered by what the user owns or likes.**
Questions addressed to the assistant ("Can you recommend...", "any tips
for...", "what should I...") rank messages by embeddings with a little BM25
instead of the cross-encoder trained on web queries.
- LongMemEval single-session preference questions (30): session recall@5
  90.0% -> 100%, @1 56.7% -> 70.0%. The weighting was chosen on those 30, so
  this is not a held-out figure. The pattern matched none of the other 470
  LongMemEval questions or LoCoMo's 1,986.
- Status: supported, tuned.

## Checking a claim

**"Did the user say this?" is answerable; "is it true now?" is not, without
a model.** `profile_check` reads a claim as a message and returns whether the
user said it, with what is known since.
- Readable sets: "said" right about provenance 322/323; true claims recognised
  207/263; denied, hedged or never-said claims returned as said 1/55 (held
  out, before the last rules: 5/61).
- Status: supported as provenance. As a statement about now, "supported" was
  right 81% of the time; refuted, so it is not offered.

## Adversarial review (2026-10-06)

An agent was asked to break the rules with counterexamples and to check
every published number. Its counterexamples are now tests
(`rgx/test_adversarial.py`, and the unrelated-news and claim-value tests in
`server/tests/test_memory_view.py`). What it found, and what changed:
"may have changed since" linked unrelated later news (11 of 18 pairs, also
on the committed code); the claim check said "said" for a claim whose value
differed ("allergic to peanuts" from "allergic to penicillin"); presupposition
triggers and decisions fired on most counterexamples; "said in passing" had
stopped marking ordinary events said today; an instruction rule took
"Summarize this paragraph for me" as standing. Each is fixed as described
above and measured again on the benchmark sets.

## Tried and refuted

Kept here with their numbers, because a rule that failed is part of the
evidence.

- **Re-ranking for multi-hop questions** (LoCoMo, answering messages among
  the 8 a reader sees, of 106): z-scored fusion of BM25, embeddings and the
  cross-encoder 42 -> 46; MiniLM-L12 46; ColBERT (answerai-colbert-small) with
  BM25 50. Answers on the development conversations against the same
  baseline (68.2%, identical on a rerun): +15/-23, +15/-17, +18/-22 questions.
  Refuted: finding more of the right messages did not give better answers.
  The optional notes mode is what closes the multi-hop gap (62.3% on the test
  conversations, Mem0 61.9%).
- **Sentence-level indexing** of messages: no gain on multi-hop, worse on
  single-hop. Refuted.
- **Stripping greetings, compliments and questions** before ranking: worse
  on single-hop (92 -> 87 of 120). Refuted.
- **WordNet hyponyms of the question's head noun as query expansion**
  ("instruments" -> clarinet, violin): no change. Refuted: it only widened a
  candidate pool that already held the answers.
- **Coverage selection** for list questions (one message per session first):
  worse. **A word budget** instead of a line count: no gain. Refuted.
- **Notes written by the parser** (its own short statements of what the
  user said, in the notes slot, no model): LoCoMo development conversations
  67.4% against 68.2% without, multi-hop 19 against 23 of 43. Refuted: the
  model's notes help by merging facts ("plays the clarinet and the violin"),
  not by being short; restating adds tokens without that.
- **A digest for list questions** (RG_DIGEST, off): the parser's facts
  whose object is the asked-for kind in WordNet ("What instruments..." ->
  clarinet, violin) as one extra line. It fired on about a third of the
  development list questions, often with partial or unrelated facts
  ("symbols" is too broad a word); answers +0/-1 against the same run without
  it. Refuted: where the parser had the facts, the messages were already in
  the context.
- **"Supported" as "true now"** in the claim check: 81% precise. Refuted;
  the verdict is provenance.
- **Reading negation off raw message text** to call a claim contradicted:
  too often aimed at something else in the clause ("no air con", "can't find
  the kitchen"). Refuted; only the parser's negated facts contradict.
