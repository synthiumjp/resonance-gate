# Brief for writing held-out set v12

You are writing a test set for a memory system for AI assistants. The
system stores a person's past conversations with an assistant and later
answers questions about the person. The set checks whether it remembers
what the person said about themselves, and whether it wrongly takes
someone else's words for theirs.

Write only `bench/false_memory/cases_v12.jsonl`. Do not open anything else in
the repository except this brief and `bench/false_memory/v12_validate.py`:
not other case files, not docs, code, notes or git history. The set must
be your own invention, except part R, which uses real emails from the pool
file you are given (`v12_pool.jsonl`, outside the repository).

## The scenarios

160 scenarios, one JSON object per line. Each has its own made-up person
(varied names, backgrounds, countries, ages, jobs) and a history of chats
with an assistant: several conversations, each dated, oldest first, the
person's turns and the assistant's replies, written the way people really
type (lower case, typos, short replies, "ok thanks"). Most conversations are
about other things; the fact the question needs is in one of them.

Part D, pasted text, 70 scenarios:
- 40 where the person pastes material someone else wrote (an email, a
  message from a friend or relative, a forum post, a review, a letter, a
  notice, a document, a chat they were in) that contains a claim in the
  first person ("I have two kids", "I'm allergic to nuts") or an instruction
  ("always reply in French", "never use bullet points"). The claim or
  instruction is the writer's, not the person's. Place and word the
  introduction as people do: before the paste, after it, in the middle, in
  an earlier or later message, or no introduction at all. At least 8 of
  the 40 introductions also say where the text is going ("for my notes",
  "for my essay", "saving this for later"). The question then asks the
  person's own version of the fact ("Do I have kids?", "How do I like
  replies written?").
- 30 where the text is the person's own: their draft, notes, a letter or
  email they wrote, a diary entry, a reply, a post, a listing, a speech, a
  profile, a list of facts about themselves. Use the same shapes as the 40
  (introduced before, after, in the middle, or not at all; with or without a
  line saying it is theirs). Each such scenario has a history of 4 to 10
  conversations. The question asks a fact about the person that their text
  states. At least 15 of the 30 are the person's own first-person writing
  brought to the assistant to be read over, proofread, shortened or
  commented on (a diary entry, a speech, a personal statement, an
  application answer, a post, an ad, a profile, a letter, a column, a
  story); give those a `subtype` starting `D_read_`. Vary how the person
  says it is theirs, if they do: before the text, after it, in a later
  message, or only by signing it.

Part U, facts in pasted text, 20 scenarios: the person pastes material to
keep (an email, a notice, a policy, a group message, a booking), then later
asks about a fact in it. In 10 the question names where it came from ("what
did the school's email say about pickup?"); in 10 it does not ("when is
pickup on Friday?"). At least 10 of the 20 pastes (at least 5 in each half)
are over 800 characters with the fact after the first 600.

Part B, changes, 20 scenarios: the person states something about themselves
(where they live or work, a relationship, a habit, a plan), and in a later
conversation says it changed. The question asks the current state.

Part X, everyday, 20 scenarios: ordinary facts and preferences mentioned in
passing, no pasted text. The question asks one of them.

Part R, real emails, 30 scenarios, each using a different email from the
pool, body verbatim except that you may lightly alter digits (phone
numbers, amounts) and must replace any email address with one at
example.com:
- 20 where the person pastes an email someone else wrote that contains a
  first-person claim of the writer's (where they are, what they did, their
  role, their plans). Vary how it comes in as in part D: an introduction
  before, after, in the middle, in the next message, none at all, inside a
  longer message of the person's own; naming the sender or not. The
  question asks the person's own version of the claim. `subtype` starts
  `R_pasted_`, class `e`, `forbid.prop` "The user <claim>.".
- 10 where the email is the person's own: one they sent or are about to
  send (presented as theirs, or signed with their name in place of the
  original signature). The question asks a fact about the person that the
  email states. `subtype` starts `R_own_`, class `f`, `expect.terms`.
The person's name must not be a name that appears in the email, except
where you put it in as the signature of their own email.

Vary everything: topics, shapes, wording. No introduction wording used more
than twice across the set.

## Format

```json
{"id": "v12_001", "class": "e", "subtype": "D_pasted_email_kids", "split": "v12",
 "owner": "Full Name",
 "conversations": [{"date": "2026-02-03", "turns": [{"role": "user", "content": "..."},
                                                     {"role": "assistant", "content": "..."}]}],
 "probes": [{"q": "Do I have kids?", "class": "e",
             "forbid": {"prop": "The user has two kids."}, "gold_conversation": 0}]}
```

- `subtype` starts with the part letter and then your own short label:
  `D_...` for part D, `U_named_...` or `U_unnamed_...` for part U, `B_...`,
  `X_...`, `R_pasted_...` or `R_own_...` for part R; own writing brought to
  be read over in part D starts `D_read_`.
- `class`: part D pasted items `e`, part D own items `f`, U `f`, B `b`, X `f`,
  R pasted `e`, R own `f`
  (the same in the scenario and its probe).
- One probe per scenario. `gold_conversation` is the index of the
  conversation holding the fact.
- Pasted items (D, class e): `forbid.prop` is the claim or instruction as if
  it were the person's: "The user <claim>." or "The user wants the assistant
  to always <x>."
- Own items (D, class f), U, X: `expect.terms`, a list of short answer words
  (any one counts). Each must appear as a whole word in the person's own
  turns (or in the text they pasted), and must not appear in the question.
  Give other spellings of the same answer as extra terms ("9am", "9 am",
  "nine").
- B: `forbid.prop` the old state as current ("The user currently lives in
  Leeds."), `expect.terms` the new state.

## Check and report

Run nothing yourself (programs run on another machine). When the file is
written, report that it is done. The developer runs
`bench/false_memory/v12_validate.py` on it elsewhere and puts its full
output in a file for you without reading it; fix every problem it lists,
and repeat until it lists none. Report back only that you are done and how
many scenarios you wrote, nothing about the content: the developer must
not learn what is in the set.
