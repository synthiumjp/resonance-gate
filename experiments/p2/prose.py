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


# 2026-10-09 (adversarial review). Missed: an email introduced without a
# noun ("what do you make of this" + From:/Subject: lines), quoted replies
# ("> ..."), "Can you summarise this?" + a paragraph. Wrongly taken: the
# user's own material ("Here are my notes: I'm vegan...", "Following my last
# message: I live in Leeds"), and first-person text after an introduction
# that asks for nothing ("Quick question on this thread: my manager said...").
_HEADER = re.compile(r"^(?:from|to|subject|sent|date|cc|reply-to)\s*:\s*\S", re.I)
_ASK_THIS = re.compile(
    r"\b(?:summari[sz]e|translate|proofread|rewrite|reword|tidy(?: up)?|clean up|"
    r"check|review|reply to|respond to|explain|make of|think of|thoughts on)\s+"
    r"(?:this|the following|it)\b[^\n]*(?:\n\s*\n|:\s*\S)", re.I)
_OWN_MATERIAL = re.compile(r"(?<!from )\bmy\s+(?:\w+\s+){0,2}?(?:" + _MATERIAL + r")\b|"
                           r"\b(?:summary|notes|bio|description) (?:of|about) me\b", re.I)
# a request to work on someone else's text, not about the user's own problem
_TRANSFORM = re.compile(r"\b(?:summari[sz]e|translate|proofread|rewrite|reword|"
                        r"reply to|respond to|tl;?dr|tidy|clean up|shorten|edit)\b", re.I)
# the introduction names another author: "My partner sent this text:"
_OTHER_AUTHOR = re.compile(r"\b(?:sent|wrote|written|forwarded|received|posted|said|"
                           r"replied|messaged|texted|emailed|from (?!my\b)\w+|by (?!me\b)\w+)\b",
                           re.I)
_FIRST = re.compile(r"\b(?:i|i'm|i’m|i've|i’ve|i'd|my|me|mine)\b", re.I)


def _first_person_heavy(text):
    words = re.findall(r"[\w'’]+", text)
    return bool(words) and len(_FIRST.findall(text)) * 10 >= len(words)


def _drop_pasted(text):
    lines = text.split("\n")
    # quoted reply lines and an email's header block are someone else's
    if any(l.lstrip().startswith(">") for l in lines[1:] + lines[:1]):
        lines = [l for l in lines if not l.lstrip().startswith(">")]
    hdr = next((i for i, l in enumerate(lines) if i and _HEADER.match(l.strip())), None)
    if hdr is not None:
        lines = lines[:hdr]
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
    if m:
        m_start, m_end, intro_text = m.start(), m.end(), m.group(0)
    else:
        a = _ASK_THIS.search(text)
        if not a:
            return text
        t = re.search(r"\b(?:this|the following|it)\b", a.group(0), re.I)
        m_start, m_end, intro_text = a.start(), a.start() + t.end(), a.group(0)[:t.end()]
    if _OWN_MATERIAL.search(intro_text):
        return text
    rest = text[m_end:]
    colon = re.match(r"[^.?!\n]*?:[ \t]*\S", rest)
    if colon:
        intro = text[text.rfind("\n", 0, m_start) + 1:m_end + colon.end() - 1]
        pasted = text[m_end + colon.end() - 1:]
        if (_first_person_heavy(pasted) and not _TRANSFORM.search(intro)
                and not _OTHER_AUTHOR.search(intro)):
            return text
        return text[:m_end + colon.end() - 1]
    para = re.search(r"\n\s*\n", rest)
    line = text[text.rfind("\n", 0, m_start) + 1:m_end] + rest.split("\n", 1)[0]
    if para and not (line.rstrip().endswith(":") or _ASK.search(line)):
        para = None     # "I loved this article.\n\nI live in Leeds." is not a paste
    if not para:
        # a line ending in ":" followed by lines (no blank line)
        nl = re.match(r"[^\n]*:[ \t]*\n", rest)
        if not nl:
            return text
        head, pasted = text[:m_end + nl.end()], rest[nl.end():]
    else:
        head, pasted = text[:m_end + para.start()], rest[para.end():]
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
