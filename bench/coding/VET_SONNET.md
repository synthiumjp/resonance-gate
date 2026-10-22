# Coding recall: the Sonnet vet (docs/PREREG_CODING_V1.md)

Run as a Claude Code subagent (model sonnet), not the API. Input: the
question file exported as JSON lines {n, repo, type, question, answer,
evidence}; output: {n, keep, why} per line. The prompt, verbatim (dev,
2026-10-23):

> You are vetting questions for a benchmark of coding-assistant memory.
> Read the file FILE (JSON lines: n, repo, type, question, answer,
> evidence). Read only that file; run no other commands.
>
> Scenario: a developer worked on this repository with an AI coding
> assistant over many sessions. Weeks later, starting a new session, they
> ask the assistant (which has a memory of past sessions) the question. The
> answer is the gold answer drawn from one past session; the evidence is a
> quote from that session.
>
> KEEP a question only if all of these hold:
> - it names what it is about (which test, build, command, feature, error,
>   document), so it has one right answer in a project with many of each;
> - the gold answer answers exactly that question, as a single answer (not
>   a partial list with "and others"), and the evidence supports it;
> - the gold says something the question does not already say (not a file
>   name the question already gives);
> - a developer would plausibly want to recall it (not one CSS property, a
>   generated or hash file name, or a detail only someone reading that one
>   transcript would care about).
> Otherwise DROP. Japanese questions are fine; judge them the same way. Be
> as strict as a careful reviewer would be.
>
> Write your verdicts to OUT, one JSON line per question: {"n": 1, "keep":
> true} or {"n": 2, "keep": false, "why": "short reason"}. All lines. Then
> reply with only: "KEPT: k of N".

Large files go in batches of about 120 questions, one subagent each.
