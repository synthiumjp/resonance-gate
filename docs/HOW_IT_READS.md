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
saw them and are read only as counts, but v2-v4 and the coding and projects
sets have since been run many times and some rules were written from their
error categories, so only v5 is clean; see `docs/REVIEW_2026-10-09.md`). Last measured 2026-10-07.

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

## Held-out test (v6, pre-registered)

The fixes from the adversarial review (below) were tested once on a second
unread set, 140 scenarios (`docs/PREREG_HELDOUT_V6.md`, results in
`bench/false_memory/results_v6/SUMMARY.md`), every system under the same
reader instruction. Four of eight met, four missed:
- met: a change that happened, old state given as current 0/20; hedged or
  reported claims given as the user's fact 1/14, plain controls 6/6;
  coding sessions, the instruction or decision in force 23/25 and a
  reversed one given as current 0/8; standing instructions at session start
  11/12, idioms 0/3.
- missed: pasted text, a pasted claim or instruction given as the user's
  14/17 (the "pasted in" marker fired on 3 of the 14; in 11 the
  introduction and the pasted text were one line; the reader ignored the
  marker too); advice, the mention used in 3/15 (every miss a refusal under
  the shared "say you don't know" instruction; our advice instruction was
  in the block for 10 of 15); plans, the earlier state given as ended in
  4/20 (both lines in the block in all 4; "no longer true" never fired on
  part A, which is the half of H1 the rules control); pooled false
  memories, 15/59 against 17, 17 and 10, 14 of ours from pasted text.

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
for...", "which editor should I use", "how should I...") rank messages by
embeddings with a little BM25 instead of the cross-encoder trained on web
queries; and the block tells the reader to fit the advice to what the user
said, with the best-matching messages first.
- LongMemEval single-session preference questions (30): session recall@5
  90.0% -> 100%, @1 56.7% -> 70.0% (weighting chosen on those 30).
- Held-out v5 found the reader not using what was found: the earlier mention
  was in the block 10/10 times and in the answer 2/10 (plain retrieval's
  three messages: 8/10). The memory's own rule, "anything about the user not
  listed here is UNKNOWN: say you don't know", read as a reason not to
  advise. Reworded for advice, with a line asking for advice fitted to the
  user's words and the best matches first: development advice set (24) the
  mention used 10 -> 21 (plain retrieval 15), "I don't know" 11 -> 2.
  On LongMemEval's preference answers, judged against each question's own
  description of what the user would prefer: 13 -> 16 of 30 (+5/-2, not
  significant, and the retrieval routing was chosen on these same 30).
- The pattern matches none of LongMemEval's 470 other questions or LoCoMo's
  1,986, so those results cannot move.
- Status: supported on development data; no held-out answer-level number.
  The adversarial review found the pattern also fires on ordinary coding
  questions ("Where should I put the config file?") and on "how should I
  have known"; to be narrowed and measured on a coding set.

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

## Fixes from the adversarial review (2026-10-09)

**A bare acknowledgement of advice is not a decision.** "ok", "ok thanks",
"fine" alone accept only an offer put as a question ("Want me to...?") or
a joint proposal ("Let's deploy on Heroku"), not "You could..." or "I'd
suggest...". Development decision set: the same 22 decisions as before.

Counterexamples from `docs/REVIEW_2026-10-09.md` are now tests
(`rgx/test_adversarial.py`, `server/tests/test_review_rules.py`,
`experiments/p2/test_prose.py`).

**A change must have happened.** The newer statement's own wording (the
parser's proposition) is checked before it can mark an older fact: a modal
(might, will, could; lower case, so "finalised in May" and an owner called
Will are not), a plan or intention ("is going to", "wants to"), a future time
("next year", "on Monday" with the present tense), a negation about
something else ("I didn't move to Brunswick after all"), or the past ("I
lived in Fitzroy for ten years", said after the move) is not a change. A
change of polarity counts only about the same thing ("I don't live in
Fitzroy any more"). Development change sets: "no longer true" and "may have
changed since" on a current-state line 0 before and after; on out-of-date
lines unchanged except 2 fewer wrong "may have changed since" marks.

**A hedge or a report leaves no bare fact.** "I guess I live in Leeds now",
"I heard I'm getting promoted", "I'm told I work in Finance", "I said I work
at Google as a joke", "I used to think I was allergic": the frame is kept,
the complement is not stored on its own; a sentence opened by "allegedly",
"supposedly", "let's say", "yeah right" stores nothing. "I think" and "I
believe" keep their complement: they mostly state the user's own view. Cost:
"I told my mum I moved to Leeds" no longer stores "moved to Leeds" by itself
(the message is still quoted).

**An idiom is not an instruction, and an instruction keeps its contrast.**
"Never mind", "Keep the change", "Don't worry about it", a subjectless
"Don't know what to do" are not standing instructions; "Always use tabs, not
spaces" keeps "not spaces"; "Never again will I use that vendor" (fronted
negative with inversion) stores nothing rather than "will use that vendor".
Now also stored: "use tabs from now on", "Stop using emojis", "Be concise"
(be + a style adjective), "dont ever apologise", "Do not under any
circumstances touch the prod db", "Call me Dan" ("asked to be called
Dan"). And not stored: an imperative with a modal ("Can't wait to see it",
"Won't let anything hold me back"), "did"/"does" ("Did not see any
bands"), encouragement to the listener ("Keep up the great work", "Never
give up", "Don't let anything stop you", "Take care"). Over LoCoMo's 5,882
chat messages, standing instructions fell from 227 to 10 (most had been
"Can't wait ..."); the development preference, coding and project sets lost
none (3 -> 4 on preferences).

**Pasted text, both ways.** An email's header lines, quoted replies ("> ...")
and "summarise this" without a noun mark what follows as pasted; the user's
own material ("Here are my notes:", "Following my last message:") and
first-person text after an introduction that asks for no rewrite are kept
as theirs, unless the introduction names another author ("My partner sent
this text:"). No LoCoMo, development or held-out message changed: the
benchmarks do not test pasted text, so these rules are measured only by the
tests above. Held out (v6): the marker fired on 3 of 14 pasted items that
became false memories, and did not stop the reader on those 3.

**Notes.** The pronoun rewrite leaves quotes and code alone and reads phone
apostrophes; a note must keep the user's numbers and polarity ("does not eat
meat" is rejected against "I eat meat now"); the owner check is a whole word;
a note cut off at the length limit is dropped; a session that got no notes is
given them later, and `sourcedrecall-memory notes-backfill` covers earlier
history.

## Pasted text after held-out v6 (2026-10-09)

v6 gave a pasted claim or instruction as the user's in 14 of 17. Three
causes, each fixed (0c1e9f5, 8fafd1e):
- Whose text it is was partly read from the pasted words: first-person text
  after an introduction was kept as the user's, and most pasted text is in
  the first person. Now it is read from the introduction only: someone else
  sent it ("my boss sent me this", "my brother just texted:"), it comes from
  somewhere ("this email from my landlord", "From the gym:"), the user found
  it ("found this in a book", "look at this ad"), or asks for it to be
  translated, proofread, summarised or answered; a chat log, a one-line
  letter that the user asks how to answer, a quoted sentence in the first
  person, and text followed by a question about it ("is this bad advice?")
  count too. It is the user's only when the introduction says so ("my
  notes", "I wrote", "my own", "it's mine").
- The block showed messages with their blank lines removed, so where a
  paste ended could not be seen. Messages are now quoted as written.
- The rules told the reader that everything in quotation marks is the
  user's. Pasted text is now shown as `[pasted in by <user>, written by
  <who the introduction names>; not <user>'s words, facts or instructions:
  "..."]`, with its first person made the writer's ("[the writer] own three
  properties") and its instructions marked "(the writer asks)", and the
  rules say the user's own facts, rules and preferences are never answered
  from it.

Development set `bench/false_memory/cases_dev_pasted.jsonl` (50, written by
an agent without the rules): detection (no model, `pasted_dev.py`) 9/34 ->
34/34 pasted items removed, own items kept 15/16 -> 16/16; end to end under
the fair protocol, pasted items given as the user's 18/34 -> 4/34 (plain
retrieval 19/34), own items answered 13/16 both. Elsewhere 2 of 5,882
LoCoMo messages changed (a film quote) and 1 development message. The
held-out number is v7's (`docs/PREREG_HELDOUT_V7.md`).

Held out (v7, `bench/false_memory/results_v7/SUMMARY.md`): pasted claims or
instructions given as the user's 11/34 (v6 82%, now 32%; plain retrieval
24/34, agentmemory 26/34, p<0.01 each), own material 13/16. The marker fired
on 24 of the 34 and the reader took a marked item for the user's once; 10
were never detected (introduction on its own line before a blank line, 6;
introduction only after the paste, 4), worded in ways the rules do not list.
2 of the user's own items were wrongly marked. Missed the pre-registered
4/34. The presentation works; detection by word lists does not generalise
far enough.

Detection by shape (f69fc33): a short paragraph of the user's and a block
in another voice (greeting, sign-off, chat log, heading, review, list of
rules, code comments), the introduction before or after; chat logs anywhere;
a letter addressed to the user by name; "^ that's from ...". Second
development set (`cases_dev_pasted2.jsonl`, 60): detection 6/40 -> 37/40,
end to end false memories 33/60 -> 5/60 questions. Held out (v8,
`bench/false_memory/results_v8/SUMMARY.md`): 9/40 given as the user's
(target at most 6, missed; plain retrieval 16, p=0.15). The marker fired on
24 of 40 and the reader misread 4 of those (3 pasted instructions it
followed); 5 one-paragraph pastes went undetected (introduction on the same
line, after the paste, or none); 2 of 20 own items were wrongly marked.

**The secret filter (2026-10-10).** v8 showed a pasted recipe's
introduction removed as "[secret removed]": "recipe card:" read as a card
credential, and the next sentence went with it. Ordinary words had been
taken for credential names: a bare "card", "pass" ("pass it on"), "login",
"Swift", "sin", "passport", "my social", "bank account". Over 7,480 LoCoMo
and development messages the old filter removed text from 18 (none a
secret); the new one from 0. These words now count only with a value that
looks like one next to them ("my pin is 4821", "login: bob", "my login is
bob / hunter2"); error names ("JsonWebTokenError:") and file paths of words
are not tokens. Every earlier secret test still passes.

## Tried and refuted

**Telling the reader when to refuse (2026-10-10).** Held-out v7's advice,
plan and everyday misses were mostly "I don't know" with the answer in the
block. The rules sentence "Anything about the user not listed here is
UNKNOWN: say you don't know rather than guessing" was replaced by "Use any
line that answers the question, even in other words, and say which ... say
you don't know only when no line bears on the question", with "a plan or a
possibility in a later line does not change an earlier fact until a line
says it happened". Seven development sets under the v7 reader instruction:
nothing answered more (advice 20/24, paraphrase 59/64, preferences 31/36,
decisions 5/10, all unchanged), false memories up by one or two on three
sets (changes 1 -> 2 and 3 -> 4, pasted 3 -> 5). Reverted.

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
