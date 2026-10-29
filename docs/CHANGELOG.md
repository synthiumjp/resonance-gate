# Changelog

Numbers are from the benchmarks in `bench/` (same local reader and judge for
every system; see `bench/REPRODUCE.md`). The research notebook (`notebook.md`)
has the details behind each change.

## 0.6.0

- Coding history. Each Claude Code session's record is kept per project:
  failed test, build and run commands with up to three of their error
  lines, what was edited after and whether the command passed later,
  commands that worked, commits, decisions, and the session as short dated
  passages. `history_search` (MCP), `/recall` in Claude Code and
  `sourcedrecall-memory history` search it; the session-start summary
  names the project's recent history. `sourcedrecall-import claude-code`
  stores past sessions from `~/.claude/projects`. On the pre-registered
  coding set (`docs/PREREG_CODING_V1.md`), 72.1% of 136 questions against
  56.6% for Claude Code's memory simulated with a Sonnet writer, 80.9% for
  both together, 74.3% for a plain search over the same passages.
- The session-start summary leaves out facts the project's Claude Code
  `MEMORY.md` already states.
- Facts about other people and things that a later fact replaces are now
  marked "may have changed since" when the two fill the same sentence frame
  with different names, and for facts not about you the note names the
  later fact and its date. Long messages are quoted by their best sentences
  around the question, and values that share only slot words are kept
  apart. All on by default (`RG_FRAME_CHANGES`, `RG_NOTE_LATER`,
  `RG_TRIM_LONG`, `RG_SLOT_CLUSTER` set to 0 turn them off). On
  MemoryAgentBench's held-out FactConsolidation lists, single facts 49 -> 84
  and 40 -> 80 of 100, still below plain retrieval (89 and 94); LoCoMo
  65.6% -> 65.4%.
- A later statement of yours with a change word ("now", "switched", "new")
  no longer marks an earlier related one "may have changed since"; a later
  statement that says the opposite about the same thing ("I don't live in
  Fitzroy any more") still does. `RG_LATER_CHANGES=1` brings the change
  words back. On LoCoMo they marked about 450 facts, nearly all wrongly,
  and no development set needed them.
- A death ends only what its own clause says; verbs whose subject holds
  many values at once ("directed", "wrote") and slots like "allergic to"
  are not read as changes.
- A note on a long message that is cut is kept only when the quoted part
  shows the fact it is about.
- Through MCP, `profile_ingest` and `profile_confirm` are marked
  destructive, so a client that reads the hint asks first, and
  `profile_ingest` always starts a new conversation. Every forget,
  correction and confirmation is logged in `changes.jsonl` with its time,
  whether it came through MCP or the command line, and the fact's id, never
  its words.
- An "always" or "never" rule deep inside a message over 600 characters
  (likely a pasted document) no longer becomes a standing instruction.
- The plugin installs the versions a fresh install was tested with
  (`server/constraints.txt`), and the newest allowed where one of them does
  not install. A Cursor turn appended while a forget rewrites the spool is
  no longer lost.
- The credential filter also removes `--password`, `--token` and
  `--api-key` flags, `user:password@host` without a scheme, `whsec_`
  webhook secrets and "mypassword is ...".
- A session whose storing was cut off (the computer slept, or on WSL the
  Linux side stopped after the terminal closed) is stored at the next
  session start, up to three tries. Before, its conversation was kept but
  its facts were not, and nothing said so. `hook.log` now has a line when
  storing starts as well as when it ends. A session that fails to store
  with an error is kept and tried again the same way; after three tries it
  is set aside and the log says so.
- One message the parser cannot read no longer loses the whole session's
  facts: it is skipped, counted in `hook.log`, and tried again next time.
  A name of only spaces no longer makes storing fail on pasted text.
- "[Request interrupted by user]" is no longer stored as something you said.
- In Claude Code, `! sourcedrecall-run memory ...` and `! sourcedrecall-run
  import ...` run the memory and import commands from the plugin's own
  environment; messages and pages name the command that works where you
  are (the plugin's commands are not on your PATH). The README says the
  plugin asks for your name and how to check that it works.
- A failed install is tried again after an hour or when the plugin is
  updated, and `! sourcedrecall-run install` retries it at once (it used to
  install into a different folder). On Debian and Ubuntu without
  python3-venv the install says what to install instead of failing on the
  next try. `memory status` gives when the memory was last written.
- Forget is reliable while a session is open: the memory server sees
  changes made by other processes (a forget from the command line, a
  session stored by another window) and no longer writes a forgotten
  sentence back into `MEMORY.md`. Forgetting one sentence keeps the other
  facts of the same message. A sentence cut at an abbreviation ("Dr.
  Smith") is matched; the same words inside a longer message or quoted in
  an assistant reply are taken out; the copies kept beside the memory and
  the parser's saved names are cleaned; a forget made while a session is
  being stored is no longer undone by it.
- What is stored and shown as yours: rules inside a document you show
  ("look at what the docs say:", "is this right?") no longer become
  standing instructions; "Hey Claude," is no longer taken for a pasted
  letter (your own lines after it were dropped), nor is your next line after
  a sign-off; an email you were sent to reply to stays someone else's when
  it is signed with your first name; "battery", "tired of", "for now" and
  "I'm back at" no longer drop lasting facts; a paste whose source you give
  in your next message is stored as someone else's, as it was shown.
- The session-start summary: among equally supported facts the newest lead
  (it kept the oldest); at most ten standing instructions; a long block is
  cut by whole lines and keeps its rules. "About you" in `MEMORY.md` no
  longer takes "Annabel" for "Anna". Quoted sentences cannot close their
  own quotation marks.
- Storing a long pasted text with many private-key header lines no longer
  takes quadratic time (336 KB took 11 s per message).
- Dependencies are capped at their next major version, so a new release
  cannot break a fresh install; the wheel includes LICENSE and NOTICE.
- Known limit: a change said in the same session as the old fact ("I use
  Postgres" ... "we switched to SQLite") does not yet mark the old one as no
  longer true; across sessions it does.

- A new install says what is happening: while the memory installs, if the
  install failed (with its log and how to try again), when your name is
  not set, and once, while the memory is empty, what happens next.
  `sourcedrecall-memory status` shows whether the models are ready and
  what is stored; `sourcedrecall-memory last` shows the block the agent was
  last given and its size.
- The model download shows its progress and continues where it stopped
  if the connection breaks.
- Forget also erases the conversation's title and the Cursor spool, keeps
  a keyed fingerprint instead of a plain hash, and says how many places it
  erased the sentence from.
- Through MCP, an agent can no longer store a conversation dated in the
  future, and reading a whole conversation is limited to 200 turns from
  the current project. The MCP tools have short plain descriptions; the
  diagnostic ones are hidden unless `SOURCEDRECALL_ALL_TOOLS=1`.
- Stored text cannot close its own quotation marks in the block and add a
  label of its own.
- Storing a long session no longer makes other sessions wait for its
  parse.
- Typing "[MEMORY" in a message no longer drops the rest of it.
- Titles are checked for credentials before they are cut to length.
- Imports over 1 GB are refused with a message, and exports are read
  without holding a second copy in memory.
- Python 3.14 is not used until it is tested; `sourcedrecall.__version__`
  matches the package.
- When the parser has found the message a question is about, other messages
  are shown only if they are close to the question (embedding similarity
  0.5 or more), come from the same conversation, or hold a fact the parser
  ties to it. In a short history every message used to be shown, and a
  cautious reader said "I don't know" with the fact in front of it.
  Development own-material set (Qwen3-14B reader): 26 to 30 of 40 answered,
  false memories unchanged on every development set; with a second reader
  (Phi-4) about the same as before (34 and 33 of 40). `RG_MSG_CUT=off`
  shows every line.
- Claude Code capture no longer stores text you did not type: the summary
  written after /compact, background-task and subagent results, and
  messages from other sessions.
- Pasted text: an introduction that names where the text came from ("my
  boss sent me this", "forwarded", "written by") now wins over words like
  "my notes" or "my essay", and "add this to my notes" or "quote this in my
  essay" no longer make someone else's text yours. "My brother wrote this"
  is no longer read as you writing it.
- If the memory file cannot be read, it is copied aside and nothing is
  written, instead of being replaced by the new conversation.
- The credential filter no longer slows down on long hyphenated or dotted
  text (8 KB of "a-a-a-..." took 8 seconds, 100 KB would have taken
  minutes; now under 2 seconds at 100 KB). Its output is unchanged on every
  benchmark conversation and on the project's own files.
- The credential filter also removes a password given on the line after
  "my password is", "my pass is hunter2", "Authorization: Basic ...",
  `key=...` with a token-like value, PGP private key blocks, and
  "Passwort", "mot de passe", "contraseña", "senha" and "wachtwoord" with a
  value. No benchmark conversation changed.
- A list of fields in your own message ("Allergies: peanuts", "Diet:
  vegan") is no longer taken for a chat log and skipped by the parser.
  Lines like "Sam: ..." count as a chat only when a speaker speaks twice,
  one of them is "Me", or the lines have times. Pasted bookings and
  newsletters that hold such lines are now marked pasted as a whole.
- Every model setup downloads is fetched at a fixed revision and checked
  against its checksum, so a change upstream cannot change your results or
  break the install. A stalled download now times out, and a WordNet
  download that fails is reported.
- On Windows, a second process storing a conversation waits for the
  first instead of giving up after 10 seconds and writing without the
  lock (not yet run on Windows). If the lock cannot be taken at all, a
  warning is printed instead of nothing.
- The MCP tools tell the host which ones only read and which change or
  delete the memory, so it can ask you before a forget.
- Requests for advice use what you told the assistant: the memory no
  longer reads its "unknown" rule as a reason to give no advice, and puts
  the best-matching messages first. Development advice set: your earlier
  mention used in 21 of 24 answers (10 before); LongMemEval preference
  answers 16 of 30 (13 before; not significant). Found by the held-out set
  v5; no held-out number for the fix yet.
- Text you paste for the assistant (an email, a README) is shown to it as
  pasted, not as your words.
- Built-in notes models that need no server: `pip install
  'sourcedrecall[notes]'` and `sourcedrecall-setup --notes` (small, 0.5 GB)
  or `--notes standard` (1.4 GB). Qwen3 trained to write the user's lasting
  facts, run in-process on onnxruntime-genai. LoCoMo test on the release
  commit 53e0d9c: 67.8% and 70.6% (65.4% without notes, Mem0 64.6%). Before the model reads a conversation,
  pronouns are replaced by who they refer to ("my kids" from the other side
  becomes "Other's kids"), so its notes give the user fewer of the other
  person's facts. A long session is read in parts instead of cut at 12,000
  characters.
- `profile_check(claim)` and `sourcedrecall-memory check`: did the user say
  this? The verdict (said, contradicted, unconfirmed, unclear, not found),
  what is known since (no longer true, may have changed, no later change
  found) and the user's dated words.
- Trust labels screened against the benchmark: "said in passing" no longer
  marks changes of state said "today" ("They made me a senior designer
  today", "We bought a house today"), and still marks ordinary events ("I
  bought a coffee today"). "May have changed since" needs the newer
  statement to be the user's own, its change word in its own clause, and
  the same kind of state, a shared word in the values, or the same kind of
  thing in WordNet; on the coding sets it fired a quarter as often.
- Changes the user implies: a change-of-state verb in its frame ("graduated",
  "moved to", "started at", "got engaged", "made me a ..."), a contrast
  ("now", "back to", "has been ... since") or a presupposition trigger
  ("Fourth week as a paramedic", "Day ten of decaf") marks the older fact
  "may have changed since".
- A proposal the user accepts ("I'd suggest pnpm" / "yes do it") is stored as
  a decision made with the assistant; a declined or deferred one is not, and
  a later "let's switch back to npm" replaces it.
- Requests for advice ("Can you recommend...", "any tips for...") are ranked
  by embeddings, which finds what the user mentioned owning or liking.
- "Haven't set foot in the office since..." and "Summarize this paragraph
  for me" are no longer stored as standing instructions; "which errors
  should I retry", typed without a "?", is no longer stored as a fact.
- No PyTorch: the parser runs Stanza 1.14.0's English models on ONNX
  Runtime and numpy (`stanza_ort`), with the same parses (7,755 texts, every
  field). The install is about 0.9 GB instead of 1.6 GB and takes about a
  minute (73 s on an M3 Mac, from nothing). Stanza with PyTorch is the
  optional extra `[stanza]`.
- Sessions are stored automatically from Codex CLI and Gemini CLI
  (`sourcedrecall-hook session-end --agent codex|gemini`, with a matching
  `session-start`) and from the Cursor agent (`sourcedrecall-hook cursor`).
  `sourcedrecall-import codex` now reads Codex rollout files. Formats and
  hook inputs were checked against each tool's source or documentation;
  they have not been run inside the live applications.
- `sourcedrecall-import chatgpt` and `sourcedrecall-import claude` store a
  ChatGPT or Claude.ai data export, each conversation with its own date.
- A conversation's messages are parsed in batches: storing a long
  conversation or an imported history is about 3.5 times faster, with the
  same results.
- Text pasted in for the assistant to work on (an email, a README, a web
  page) is no longer read as your own words. A rule in a pasted email used
  to become one of your standing instructions.
- The line shown at session start gives each saved item's id, and lists any
  new standing instruction in full.
- "From now on always answer in British English" is recognised as a
  standing instruction.
- Optional notes written by your own local model (`SOURCEDRECALL_NOTES_URL`,
  `SOURCEDRECALL_NOTES_MODEL`): one call per stored conversation, notes kept
  with their date and conversation, shown labelled, listed in `MEMORY.md` and
  the browser, and forgettable by id. Off by default.
- Questions asking for a list ("What instruments does she play?", "What has
  he painted?") read more of your messages (LoCoMo dev multi-hop 42% to 49%).
- More standing instructions are recognised ("Keep answers terse", "Avoid
  red and green in charts").
- `MEMORY.md` lists standing instructions first.
- The plugin installer handles native Windows paths (untested on Windows).

## 0.5.2

- Coding sessions: a question typed without "?" is no longer stored as a
  fact; a sentence next to a pasted code block is read; preferences said in
  one project ("I always use tabs") are available in your other projects,
  while facts about a project stay in it.
- Standing instructions to the assistant ("never add comments to my code")
  are kept and lead the summary at the start of every session.
- A session that ends while the plugin is still installing is stored once
  the install finishes.
- The setup no longer downloads a model only the legacy tools use (install
  about 1.6 GB).

## 0.5.1

- The four legacy triple tools (`remember`, `recall`, `update`, `forget`)
  are off unless `SOURCEDRECALL_LEGACY_TOOLS=1`.
- A self-contained wheel (`tools/build_wheel.py`).
- "I left my home country" no longer marks "my grandma lives in my home
  country" as no longer true.
- Embeddings are kept on disk: with 20,000 messages, the first question
  after a session takes 0.6 s instead of about 46 s.

## 0.5.0

- Answers come from your own words: a question gets your dated messages,
  oldest first, with the question each one answered, chosen through the
  parser's facts and a search over the messages. The parser adds a note
  only where it matters ("no longer true", "said in passing", "may have
  changed since"). LoCoMo test 33% to 64% (Mem0 65%, plain retrieval 57%).
- Phrases you linked to a name ("my home country, Sweden") are noted where
  the phrase is used.

## 0.4.6 and earlier

- 0.4.6: whole-message quotes, message search, shorter blocks.
- 0.4.5: the read-only memory browser (`sourcedrecall-memory view`); the
  parser library pinned to the version its rules were built on.
- 0.4.4: changes of state outside the fixed families.
- 0.4.0-0.4.3: models run with ONNX Runtime; labelled "possibly related"
  candidates; the command line for any model; a Gemini CLI importer.
