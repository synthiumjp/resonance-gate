# Changelog

Numbers are from the benchmarks in `bench/` (same local reader and judge for
every system; see `bench/REPRODUCE.md`). The research notebook (`notebook.md`)
has the details behind each change.

## Unreleased

- The parser can run without PyTorch: `stanza_ort` runs Stanza 1.14.0's
  English models on ONNX Runtime and numpy, with the same parses (7,755
  texts, every field). Setup installs its models when they can be
  downloaded and falls back to Stanza with PyTorch otherwise.
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
