"""Is a chat turn prose, or pasted code/terminal output?

Moved out of run_belief.py (2026-10-02). The product read/write path needed
only this helper, but importing it from run_belief also imported eight
research modules and, at import time, READ a gitignored research cache
(experiments/p2/extract_cache.jsonl) and opened it for APPENDING. A fresh
clone has no such file, so the server crashed on its first ingest -- the
new-user install test hit exactly that. run_belief re-exports it, so every
existing import keeps working.
"""
import re


_FIRST_PERSON = re.compile(r"^(?:i|i'm|i’m|i am|i've|i’ve|my|we|we're|we’re)\s+\w",
                           re.I)


_FENCE = re.compile(r"```.*?(?:```|$)", re.S)
_CODE_LINE = re.compile(r"^\s*(?:Traceback \(most recent|File \"[^\"]+\", line \d|"
                        r"at [\w.$<>]+\(|[\w.]+(?:Error|Exception):|\$ |>>> |"
                        r"[{}\[\]();]+\s*$|(?: {4}|\t)\S)")


def prose_only(text):
    """The turn without fenced code blocks and code / stack-trace lines
    (2026-10-05): a developer's message is often a sentence of prose and a
    pasted snippet, and the prose can carry a preference ("I always use
    tabs ... in any code you write for me"). Pasted text written by someone
    else goes too (see _drop_pasted)."""
    t = _FENCE.sub("\n", text or "")
    keep = [ln for ln in t.splitlines() if not _CODE_LINE.match(ln)]
    t = _drop_pasted("\n".join(keep))
    return re.sub(r"[ \t]+", " ", t).strip()


# 2026-10-05: "Can you summarise this email?" + the email. The email's "Never
# send drafts to the client directly" was stored as the user's own standing
# instruction, and a pasted README's "Never skip the checksum step" too.
# Pasted text is someone else's words; a document could plant an instruction
# that leads every later session. The message itself is still stored and
# searchable -- only the parser no longer reads the pasted part as the
# user's own statements.
_MATERIAL = (r"e-?mails?|messages?|texts?|docs?|documents?|readme|articles?|"
             r"(?:web)?pages?|websites?|posts?|threads?|comments?|reviews?|"
             r"letters?|transcripts?|logs?|output|errors?|notes?|memos?|"
             r"policy|contract|spec|ticket|issue|description|prompt|"
             r"paragraphs?|passages?|excerpts?|snippets?|sections?|reports?|"
             r"tweets?|instructions|guide|"
             r"manual|announcement|newsletter|summary|draft|job ad|listing")
_PASTE_INTRO = re.compile(
    r"\b(?:this|these|the following|following|below|attached|"
    r"here(?:'s|’s| is| are)|pasted|copied|from (?:a|an|the|my|his|her|their|"
    r"our|some|this))\b[^.?!\n]{0,40}?\b(?:" + _MATERIAL + r")\b", re.I)
_GREETING = re.compile(r"^(?:hi|hello|hey|dear|good (?:morning|afternoon))\b"
                       r"[^.!?]{0,40},?\s*$", re.I)
_SIGNOFF = re.compile(r"^(?:thanks|thank you|many thanks|regards|best|cheers|"
                      r"sincerely|kind regards|best regards|warm regards)\b"
                      r"[^.!?]{0,40}$", re.I)
_ASK = re.compile(r"\b(?:can you|could you|would you|please|summari[sz]e|translate|"
                  r"proofread|rewrite|reword|explain|check|review|fix|reply to|"
                  r"respond to|answer|what does|what do|help me with|tl;?dr)\b", re.I)
_OWN_LAST = re.compile(r"^(?:i|i'm|i’m|i've|i’ve|my|we|can|could|would|what|"
                       r"how|why|where|which|is|are|does|do|so|ok|okay|thanks)\b",
                       re.I)


def _drop_pasted(text):
    lines = text.split("\n")
    # an email-shaped block (greeting line ... sign-off line) after the
    # message's first line: a letter the user pasted, not one to the assistant
    for i, ln in enumerate(lines):
        if i and _GREETING.match(ln.strip()):
            end = next((j for j in range(i + 1, len(lines))
                        if _SIGNOFF.match(lines[j].strip())), None)
            if end is not None:
                lines[i:end + 2] = [""]
                break
    text = "\n".join(lines)
    # an introduction ("this email", "here's the README", "from a webpage")
    # followed by a colon in the same line, or by more paragraphs: what comes
    # after it is the pasted material
    m = _PASTE_INTRO.search(text)
    if not m:
        return text
    rest = text[m.end():]
    colon = re.match(r"[^.?!\n]*?:[ \t]*\S", rest)
    if colon:
        return text[:m.end() + colon.end() - 1]
    para = re.search(r"\n\s*\n", rest)
    line = text[text.rfind("\n", 0, m.start()) + 1:m.end()] + rest.split("\n", 1)[0]
    if para and not (line.rstrip().endswith(":") or _ASK.search(line)):
        para = None     # "I loved this article.\n\nI live in Leeds." is not a paste
    if not para:
        # a line ending in ":" followed by lines (no blank line)
        nl = re.match(r"[^\n]*:[ \t]*\n", rest)
        if not nl:
            return text
        head, pasted = text[:m.end() + nl.end()], rest[nl.end():]
    else:
        head, pasted = text[:m.end() + para.start()], rest[para.end():]
    paras = [p for p in re.split(r"\n\s*\n", pasted) if p.strip()]
    # a closing line of the user's own after the pasted part ("I already
    # tried reinstalling.", "What does step 2 mean?")
    tail = ""
    if len(paras) >= 2:
        last = paras[-1].strip()
        if ("\n" not in last and len(last) < 300
                and (_OWN_LAST.match(last) or last.endswith("?"))):
            tail = "\n\n" + last
    return head + tail


def _is_prose(text):
    """False if the turn is dominated by pasted code/terminal/telemetry rather
    than first-person prose. Real user data (entry 60) is full of pasted vm_stat/
    logs/code that the extractors misread as personal facts; those turns carry no
    life-fact and are skipped. Conversational prose (LongMemEval, personal chat)
    passes untouched. 2026-10-05: judged on prose_only(text) -- a message of
    prose plus a fenced snippet used to be skipped whole."""
    if "```" in text:
        text = prose_only(text)
        if not text:
            return False
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return True
    codey = 0
    for ln in lines:
        s = ln.strip()
        nonalnum = sum(1 for c in s if not c.isalnum() and not c.isspace())
        digits = sum(1 for c in s if c.isdigit())
        L = max(1, len(s))
        # 2026-10-02: "I'm 34." is 2 digits in 7 characters and read as
        # telemetry, so the user's age never reached the parser. A line that
        # opens like a first-person sentence is prose if it has at most three
        # digits. Review 2026-10-02: "My PIN is 4821 5512 9930 1123" opens
        # like a sentence too, and a PIN must not reach the memory.
        if _FIRST_PERSON.match(s) and digits <= 3:
            continue
        # symbol-heavy, digit-heavy, or a "label: number" telemetry/config line
        # ("Swapins:  1245194", "pageins: 342...") -- command output, not prose.
        if (nonalnum / L > 0.30 or digits / L > 0.22
                or re.match(r"^[\w./+-]+\s*[:=]\s*[\d,]", s)):
            codey += 1
    return codey / len(lines) < 0.40
