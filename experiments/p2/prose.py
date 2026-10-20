"""Is a chat turn prose, or pasted code/terminal output?

Moved out of run_belief.py (2026-10-02). The product read/write path needed
only this helper, but importing it from run_belief also imported eight
research modules and, at import time, READ a gitignored research cache
(experiments/p2/extract_cache.jsonl) and opened it for APPENDING. A fresh
clone has no such file, so the server crashed on its first ingest -- the
new-user install test hit exactly that. run_belief re-exports it, so every
existing import keeps working.
"""
import os as _os
import re


_FIRST_PERSON = re.compile(r"^(?:i|i'm|i’m|i am|i've|i’ve|my|we|we're|we’re)\s+\w",
                           re.I)


_FENCE = re.compile(r"```.*?(?:```|$)", re.S)
_CODE_LINE = re.compile(r"^\s*(?:Traceback \(most recent|File \"[^\"]+\", line \d|"
                        r"at [\w.$<>]+\(|[\w.]+(?:Error|Exception):|\$ |>>> |"
                        r"[{}\[\]();]+\s*$|(?: {4}|\t)\S)")


def prose_only(text, owner=None, after=None):
    """The turn without fenced code blocks and code / stack-trace lines
    (2026-10-05): a developer's message is often a sentence of prose and a
    pasted snippet, and the prose can carry a preference ("I always use
    tabs ... in any code you write for me"). Pasted text written by someone
    else goes too (see _drop_pasted)."""
    t = _FENCE.sub("\n", text or "")
    keep = [ln for ln in t.splitlines() if not _CODE_LINE.match(ln)]
    t = _drop_pasted("\n".join(keep), owner, after)
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
_TO_ASSISTANT = re.compile(r"^(?:hi|hello|hey|dear|good (?:morning|afternoon))\s+"
                           r"(?:claude|chatgpt|gpt|gemini|copilot|cursor|codex|assistant|bot)\b",
                           re.I)
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


# 2026-10-09 (held-out v6: pasted claims and instructions given as the
# user's 14/17; the marker fired on 3). Development set
# bench/false_memory/cases_dev_pasted.jsonl (pasted_dev.py). Most text people
# paste is in the first person, so whether it is the user's is read from the
# introduction, never from the pasted words: it is theirs only when the
# introduction says so ("my notes", "I wrote", "my own", "it's mine").
_MAT2 = _MATERIAL + r"|cv|resume|bio|ad|advert|rota|sign|menu|blog|newsletter|chat|dm|slack|whatsapp|book"
_OWN_MARK = re.compile(
    r"\bmy own\b|\bI\s+(?:wrote|have written|'ve written|’ve written|drafted|jotted)\b|"
    r"\bwrote (?:it |this )?myself\b|\bfor myself\b|\bit'?s mine\b|\bit’s mine\b|\bnote to self\b|"
    r"\bit'?s me writing\b|\b(?:about|of) me\b|"
    # 2026-10-12 (review): not where the text goes ("add this to my notes")
    r"(?<!\bto )(?<!\bin )(?<!\binto )(?<!\bfor )(?<!\bon )(?<!\bof )"
    r"\bmy\s+(?:(?:last|own|latest|first|previous|earlier|old|new|rough)\s+)?(?:notes?|draft|journal|diary|bio|cv|resume|cover letter|essay|rules|reply|"
    r"answer|summary|post|message|email)\b(?!['’])", re.I)
# an introduction: someone else sent it, it comes from somewhere, the user
# found it, or asks for it to be translated or corrected
_RECEIVED = re.compile(
    r"(?:^|(?<=[.!?]\s)|(?<=\n))(?:[\w'’ -]{0,30}\s)?"
    r"(?:my|our|his|her|their|the|a|an)\s+(?:(?!(?:i|you|we|he|she|they|it|that|which|who)\b)[\w'’-]+\s+){0,3}?"
    r"(?:just\s+|also\s+|then\s+)?(?:sent|texted|emailed|messaged|wrote|posted|forwarded|replied|shared)\b"
    r"(?:\s+(?:me|us|to me|in the group|over|back))*"
    r"(?:\s*:[ \t]*|\s*\n\s*|\s+(?:this|the following)(?:\s*:[ \t]*|\s*\n\s*|\s+(?=(?-i:[A-Z])|[\"“'(\[])))", re.I)
_PASTING = re.compile(
    r"\b(?:pasting|pasted|copying|copied|forwarding|forwarded)\s+(?:in\s+)?"
    r"(?:my|the|a|an|his|her|their|our|this)\s+(?:[\w'’-]+\s+){0,2}?(?:" + _MAT2 + r")\b[^:\n]{0,30}[:\n]\s*", re.I)
_FROM_SOURCE = re.compile(
    r"(?:^|(?<=[.!?]\s)|(?<=\n))(?:(?:(?:a|an|the)\s+)?(?:[\w-]+\s+){0,2}?(?:" + _MAT2 + r")\s+)?"
    r"from\s+(?!me\b|myself\b)[^:\n.?!]{1,40}?(?::[ \t]*|\s*\n)\s*", re.I)
_TRANSFORM_INTRO = re.compile(
    r"\b(?:translate|proofread|summari[sz]e|tl;?dr|rewrite|reword|paraphrase|tighten|"
    r"shorten|tidy(?: up)?|clean up|help me (?:reply|respond|answer)|draft a reply|"
    r"what (?:does|do) (?:this|these|it) (?:mean|say))\b[^:\n]{0,80}?(?::[ \t]*|\n\s*)", re.I)
_FOUND = re.compile(r"(?:^|(?<=\n)|(?<=[,.;!?]\s))(?:i\s+)?(?:found|saw|came across|spotted|read|got|look at|"
                    r"check out|have a look at|take a look at)\s+this\b"
                    r"[^:\n]{0,60}(?::[ \t]*|\n\s*|$)", re.I)
_OTHERS_MAT = re.compile(
    r"^(?:[^\n]{0,40}\s)?(?:my|our|his|her|their)\s+[\w-]+['’]s\s+(?:[\w-]+\s+){0,2}?(?:" + _MAT2 +
    r")\b[^:\n]{0,50}(?::[ \t]*|\n\s*)", re.I)
_THEIRS = (r"e-?mails?|messages?|texts?|letters?|articles?|reviews?|ad|advert|job ad|listing|"
           r"posting|newsletter|policy|contract|cv|resume|bio|guide|readme|blog|announcement")
_MAT_COLON = re.compile(r"^(?:[^\s:.!?\n]+\s+){0,6}?(?:" + _THEIRS + r")\b(?:\s+[^\s:.!?\n]+){0,6}\s*:[ \t]*\n?",
                        re.I)
_CHAT = re.compile(r"^\s*\[\d{1,2}/\d{1,2}(?:/\d{2,4})?,?\s+\d{1,2}:\d{2}(?:\s?[AP]M)?\]\s*[^:\n]{1,30}:|"
                   r"^\s*[A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+)?\s{1,3}\d{1,2}:\d{2}\s?(?:[AaPp][Mm])?\s*$",
                   re.M)
_QUOTE_SPAN = re.compile(r"(?:^|(?<=[\s(:,]))(?:[\"“]([^\"”\n]{20,})[\"”]|'([^'\n]{20,})')(?![\w])")
# a quoted sentence someone said: first person or an instruction, not a title
_SAID = re.compile(r"\b(?:I|I'm|I’m|I've|I’ve|my|me|we|our)\b|^\W*(?:always|never|don'?t|do not|please|"
                   r"you must|you should)\b", re.I)
_SELF_QUOTE = re.compile(r"\bI\s+(?:said|wrote|told\s+\w+|always say|keep saying)\b[^.?!]{0,20}$", re.I)
_GREET_INLINE = re.compile(r"^(?:hi|hello|hey|dear)\s+(?:mr|mrs|ms|dr)?\.?\s*[A-Z][\w.'’-]*"
                           r"(?:\s+[A-Z][\w.'’-]*)?\s*,", re.I)
_SIGN_INLINE = re.compile(r"\b(?i:regards|thanks|cheers|best|sincerely|love|thank you|"
                          r"best wishes)\s*,?\s+[A-Z][a-z]+\.?(?=\s*(?:\n|$|[a-z]))")
_REPLYISH = re.compile(r"\b(?:repl(?:y|ies)|respond|what (?:do|should|can) i (?:say|write|tell)|"
                       r"how (?:do|should) i (?:answer|respond))\b", re.I)
_EVAL_Q = re.compile(r"^(?=[^\n]{0,100}\b(?:this|these|that|it)\b)(?:is|are|does|do|who|what|would|should|how|can)\b"
                     r"[^\n]{0,80}(?:advice|true|legit|real|accurate|scam|fair|reasonable|believable|"
                     r"correct|serious|sign-?offs?|phrase|idiom|mean|say about|tell about|the speaker|"
                     r"the writer|the author|written|wrote|like this)\b", re.I)


# 2026-10-10 (held-out v7: the 10 pasted items missed had introductions on a
# line of their own before a blank line, or after the paste, worded in ways
# the patterns above do not list; second development set
# cases_dev_pasted2.jsonl: those patterns found 6 of 40). Read the message's
# shape instead: a short paragraph of the user's (before or after) and a
# block. The block is someone else's when it is shaped like someone else's
# text, or the user's paragraph says where it came from; it is the user's
# when their paragraph claims it.
_GREETING_LINE = re.compile(r"^\s*(?:hi|hello|hey|dear|to whom it (?:may )?concerns?|good (?:morning|afternoon|evening))\b"
                            r"[^\n.,!]{0,40}(?:[.,!]|$)", re.I)
_SIGNOFF_TAIL = re.compile(r"(?:^|\n)\s*(?:(?:kind |best |warm |many )?regards|thanks|thank you|cheers|best|"
                           r"sincerely|yours(?: sincerely| faithfully| truly)?|love|xx+|-+\s*signed|signed)\b"
                           r"[^\n]{0,40}(?:\n\s*[^\n]{1,40})?\s*$", re.I)
_CHAT_LINE = re.compile(r"^\s*(?:\[?\d{1,2}[:/.]\d{1,2}[^\]\n]{0,25}\]?\s*[-–]?\s*[^:\n]{1,30}:|<[\w.-]{1,20}>\s|"
                        r"[A-Z][A-Z .'’-]{1,25}:\s|"
                        r"[A-Z][\w .'’-]{0,30},?\s+\d{1,2}:\d{2}\s?(?:[AaPp][Mm])?\s*$|"
                        r"(?!(?:From|To|Sent|Subject|Cc|Bcc|Date|Re|Fwd|Note|Update|Edit|PS|P\.S)\b)"
                        r"[A-Z][\w'’-]+(?: [A-Z][\w'’-]+)?:\s+\S)", re.M)
# 2026-10-12 (review 3.18: "Allergies: peanuts\nDiet: vegan\nCity: Leeds", the
# user's own field list, was dropped as a chat log). A "Name: text" line with
# no time stamp is a speaker's only when some speaker speaks twice or one is
# "Me"; field labels are all different. On the dev sets every such list
# without a repeat was a CV, a booking or a form, never a chat.
_NAME_LINE = re.compile(r"^\s*([A-Z][\w'’-]+(?: [A-Z][\w'’-]+)?):\s+\S", re.M)


def _chat_lines(text):
    """-> the _CHAT_LINE matches that are a chat's lines (see above)."""
    ms = list(_CHAT_LINE.finditer(text))
    names = [n.group(1) for m in ms for n in [_NAME_LINE.match(m.group(0))] if n]
    if len(names) == len(set(names)) and "Me" not in names:
        ms = [m for m in ms if not _NAME_LINE.match(m.group(0))]
    return ms
_DOC_HEAD = re.compile(r"^\s*(?:(?-i:[A-Z][A-Z0-9&'’.,-]+(?:\s+[A-Z0-9&'’.,()-]+){1,8})\s*(?:[-–:][^\n]*)?$|"
                       r"(?:posted by|u/\w+|[★☆]{3,}|verified (?:purchase|buyer)|\d+ people found)\b[^\n]*$|"
                       r"(?:profile|about me|bio|summary|subject|from|to|section \d+|bylaw|notice|"
                       r"thread \d|@\w+)\b[^\n]*$|"
                       r"\[[^\]\n]{3,40}(?:export|transcript|log)\])", re.I | re.M)
_RULE_LIST = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+(?:always|never|don'?t|do not|make sure|please|you must|"
                        r"you should|no )\b", re.I | re.M)
_CODE_COMMENT = re.compile(r"^\s*(?:#|//|/\*|\*)\s*\S", re.M)
_ASKED_ME = (r"\b(?:asked|asking|wants|wanted|needs) me to (?:check|look at|look over|read|"
             r"proofread|go over|review|have a look)\b|\blet me read\b")
_FRAME_SOURCE = re.compile(
    r"\b(?:sent|received|landed|showed up|turned up|(?:came|comes|coming) (?:in|through)|going around|forwarded|"
    r"posted|shared|pasting|pasted|copying|copied|inherited)\b|"
    r"\b(?:got|found|saw|spotted) (?:this|that|these|it)\b|(?<!\bi )\bwrote\b|"
    r"(?:^\W*|\b(?:this|that|it|these|which)(?:'s|’s| is| was| are)?\s+(?:\w+\s+){0,3}|"
    r"\b(?:" + _MAT2 + r")\s+)from (?:the|my|a|an|her|his|their|our|some|this|that)\b|"
    r"\b(?:written|posted|sent|shared) by (?:a|an|the|my|her|his|their|some)\b|"
    r"\bnot mine\b|^\W*(?:for )?context\b|\bcontext (?:below|above|first)\b|^\s*\^|\(\s*[\w\s'’]+['’]s [\w\s]+\)|"
    r"\b(?:her|his|their|[\w-]+['’]s) (?:" + _MAT2 + r")\b|"
    # 2026-10-13 (cases_dev_own2): "Tom's toast", "her statement for uni",
    # "asked me to look at", "let me read her diary page"
    r"\b(?:her|his|their|[\w-]+['’]s) (?:[\w-]+ )?(?:toast|speech|statement|profile|diary|journal|"
    r"essay|story|column|application|poem)\b|" + _ASKED_ME + r"|"
    r"\b(?:second|2nd|next|last|final|other) (?:bit|part|half|go|page)\b|\brest of it\b", re.I)
# naming the material ("the tripadvisor review", "this email"): an
# introduction only after the block, or before it ending in a colon ("I
# loved this article about rowing.\n\nI row every Sunday." is the user's)
_FRAME_MAT = re.compile(r"\b(?:the|a|an|this|that|these|those) (?:[\w-]+ ){0,2}(?:" + _THEIRS + r")\b", re.I)
_FRAME_OWN = re.compile(
    _OWN_MARK.pattern + r"|\bwhat i wrote\b|(?:^\W*|[.!?,;:]\s*|\bi\s+)wrote (?:this|it)\b|\b(?:that|it|this)(?:'?s| is) mine\b|"
    r"\bi'?m (?:sending|posting|writing|submitting|about to send)\b|\b(?:about|going) to (?:send|post)\b|"
    r"\b(?:going|goes) on my\b|\bfor my (?:own )?(?:site|page|profile|speech|blog)\b|\bmy (?:speech|poem|post|ad|letter|reply)\b|"
    # 2026-10-11 (held-out v9: 4 of 20 own texts taken for pasted): "draft
    # email to my landlord, sending tonight", "reply I posted on the forum"
    r"^\W*(?:(?:a|my|the)\s+)?(?:rough\s+|first\s+|quick\s+)?draft\b(?![^.\n]{0,40}\b(?:from|by|sent|they|he|she)\b)|"
    r"\bi\s+(?:just\s+|already\s+|also\s+)?(?:posted|sent|replied|answered|put up|gave|read out|delivered)\b|"
    r"\b(?:sending|posting|send|post|submit|submitting)\s+(?:it\s+|this\s+)?(?:tonight|today|tomorrow|later|soon|now|in a bit)\b|"
    r"\bi'?m (?:doing|giving|reading|delivering) (?:it|this)\b|"
    # 2026-10-12 (dev own-material set, 40): "my song lyric for the band",
    # "wrote the chorus last night", "pls check my grammar, this is a reply"
    # 2026-10-12 (review): not where the text is going ("add this to my
    # notes", "help me quote this in my essay", "sent me this for my review")
    r"(?<!\bto )(?<!\bin )(?<!\binto )(?<!\bfor )(?<!\bon )(?<!\bof )"
    # 2026-10-13 (held-out v11: 6 of 30 own texts taken for pasted, the
    # facts dropped; dev set cases_dev_own2): "my blog post", "my about
    # section", "column ..., I write it every month"
    r"\bmy (?:own )?(?:[\w-]+ ){0,2}?(?:song|lyrics?|chorus|verse|toast|eulogy|bio|cv|resume|cover letter|essay|story|"
    r"listing|review|notes?|diary|journal|draft|post|statement|speech|column|application|ad|profile|"
    r"section|entry|piece|blurb|newsletter|bit|part|paragraph|attempt|version|take)\b(?!['’])|"
    r"(?:^|[.!?,;:]\s*|\bi\s+)wrote\s+(?:the|a|my)\b|"
    r"\bi (?:write|draft) (?:it|this|these|them|one)\b|"
    r"\b(?:check|fix|correct|improve|proofread)\s+my\s+(?:grammar|spelling|wording|writing|english|punctuation)\b",
    re.I | re.M)


# 2026-10-12 (review: "my boss sent me this for my review:", "summarise this
# article for my notes:" made a pasted letter the user's own): an
# introduction that says the text came from someone else is not outweighed
# by an own cue in the same introduction
_FROM_OTHER = re.compile(
    _ASKED_ME + r"|"
    r"\b(?:sent|forwarded|passed on|passed along|emailed|texted|messaged)\s+(?:me|us)\b|"
    r"\b(?:forwarded|received)\b|\bwritten by (?!me\b)|\bnot mine\b|"
    r"\b(?:got|found|saw|spotted|came across) (?:this|that|it|these)\b|"
    r"\b(?:article|post|email|letter|message|review|thread|comment)\s+(?:from|by)\s+(?!me\b|myself\b)\w|"
    r"\b(?:this|that|it)(?:'s|’s| is| was)? from (?:my|the|a|an|her|his|their|our)\s+(?!own\b)\w", re.I)


# the user's paragraph is a request to the assistant or a question
_ASKS = re.compile(r"\?\s*(?:[\w' ]{0,20})?$|^\W*(?:can|could|would|will|what|how|is|are|does|do|should|"
                   r"tell|check|help|thoughts|translate|proofread|summari[sz]e|tidy|fix|make|write|draft|"
                   r"reply|explain|rate|review)\b", re.I)
# asking to improve a text: the user's own draft
_IMPROVE = re.compile(r"\b(?:add|change|improve|sound|sounds|ok to send|okay to send|too \w+|tone|edit|"
                      r"tweak|polish|better|work\b|flow|shorten|tighten|is it ok|does it read)\b", re.I)


def _other_voice(block):
    lines = [l for l in block.split("\n") if l.strip()]
    if not lines:
        return False
    return bool(_GREETING_LINE.match(lines[0]) or _SIGNOFF_TAIL.search(block)
                or len(_chat_lines(block)) >= 2 or _DOC_HEAD.search(lines[0])
                or (len(lines) > 1 and _DOC_HEAD.search(lines[1]))
                or len(_RULE_LIST.findall(block)) >= 2 or len(_CODE_COMMENT.findall(block)) >= 2)


def _structure_span(text):
    """-> (start, end) of a block someone else wrote, "own", or None, from
    the message's paragraphs (see above)."""
    paras = [m for m in re.finditer(r"[^\n](?:.|\n(?!\s*\n))*", text) if m.group(0).strip()]
    if len(paras) < 2:
        return None
    short = lambda m: len(m.group(0).split()) <= 45 and m.group(0).count("\n") <= 2  # noqa: E731
    head = paras[0] if short(paras[0]) else None
    tail = paras[-1] if short(paras[-1]) else None
    if not head and not tail:
        return None
    if head and tail and len(paras) == 2:
        # two short paragraphs: the user's is the one that says where the
        # other came from or that it is theirs, else the shorter
        cue = lambda m: bool(_FRAME_SOURCE.search(m.group(0)) or _FRAME_OWN.search(m.group(0)))  # noqa: E731
        ask = lambda m: bool(_ASKS.search(m.group(0).strip()))  # noqa: E731
        if ask(head) != ask(tail):
            head, tail = (head, None) if ask(head) else (None, tail)
        elif cue(head) != cue(tail):
            head, tail = (head, None) if cue(head) else (None, tail)
        elif len(head.group(0)) <= len(tail.group(0)):
            tail = None
        else:
            head = None
    frame = " ".join(m.group(0) for m in (head, tail) if m)
    start = paras[1].start() if head else paras[0].start()
    end = paras[-2].end() if tail else paras[-1].end()
    if end <= start:
        return None
    block = text[start:end]
    # a head shaped like the pasted text's own first line (a review's title)
    if head and _DOC_HEAD.search(head.group(0)) and not _FRAME_OWN.search(head.group(0)):
        start, frame = paras[0].start(), (tail.group(0) if tail else "")
    if _FRAME_OWN.search(_QUOTE_SPAN.sub(" ", frame)) and not _FROM_OTHER.search(frame):
        return "own"
    named = ((tail is not None and _FRAME_MAT.search(tail.group(0)))
             or (head is not None and _FRAME_MAT.search(head.group(0))
                 and head.group(0).rstrip().endswith(":")))
    if _FRAME_SOURCE.search(frame) or named:
        return start, end
    if _other_voice(block):
        lines = [l for l in block.split("\n") if l.strip()]
        if (lines and _GREETING_LINE.match(lines[0]) and _IMPROVE.search(frame)
                and not _REPLYISH.search(frame)):
            return "own"
        return start, end
    return None


def _own_tail(text):
    """Where a closing remark of the user's own starts in `text` (after a
    paste): a last sentence that is a question or a reply request."""
    m = re.search(r"(?:(?<=[.!?])|(?<=lol)|\n)\s*([^.!?\n]{2,120}\?|(?:what|any|how|thoughts|"
                  r"ideas|should|can|could|is|does)\b[^.!?\n]{0,120})\s*$", text, re.I)
    if m and (m.group(1)[:1].islower() or _OWN_LAST.match(m.group(1)) or _REPLYISH.search(m.group(1))):
        return m.start(1)
    return len(text)


# 2026-10-13 (real-email dev set 2, cases_dev_real2: 9 of 10 misses were an
# email pasted on its own, where it came from said in the user's next
# message: "it's from a client", "was cc'd on it", "found this in my dad's
# old files", "this is the email my friend got")
_LATER_OTHER = re.compile(
    r"\b(?:cc'?d|bcc'?d|cc'ed|cc’d)\b|"
    r"\b(?:it'?s|its|it’s|this is|that'?s|that’s|that was|this was) (?:an?|the) (?:[\w'’-]+ ){0,3}?"
    r"(?:e-?mail|letter|message|memo|note|chain|newsletter|circular|announcement)\b", re.I)


def _later_says_other(after):
    """The user's next message says the text before it came from someone
    else, and does not say it is theirs."""
    a = " ".join((after or "").split())
    if not a or len(a.split()) > 40 or _FRAME_OWN.search(a):
        return False
    return bool(_FROM_OTHER.search(a) or _FRAME_SOURCE.search(a) or _LATER_OTHER.search(a))


def _alone_paste(text):
    """A message that is only a block of text, not a request: several
    lines, no code, the first line not a question or request."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    if len(lines) < 3 or len(text.split()) < 40 or "```" in text:
        return False
    return not _ASKS.search(lines[0])


def _paste_span(text, owner=None, after=None):
    """(start, end) of the text the user pasted in from someone else, or
    None. Read from the introduction and the text's shape, not its person.
    A text signed with the owner's first name, or in which the writer gives
    it ("I'm Callum, Tomasz's brother"), is the owner's own (2026-10-11).
    `after`: the user's next message, which may be the introduction."""
    sp = _paste_span0(text, owner)
    if sp is None and after and _alone_paste(text) and _later_says_other(after):
        sp = (0, len(text))
    # 2026-10-13 (held-out v12: a third of the pasted texts in shapes the
    # rules do not read): what the rules leave unmarked goes to a small
    # learned model (paste_clf.py); RG_PASTE_CLF=0 turns it off
    if sp is None and _os.environ.get("RG_PASTE_THIRD", "1") != "0":
        import paste_clf
        sp = paste_clf.third_party_span(text, owner, after)
    if sp is None and _os.environ.get("RG_PASTE_CLF", "1") != "0":
        import paste_clf
        b = paste_clf.best_span(text, owner, after)
        if b:
            sp = (b[0], b[1])
    first = ((owner or "").split() or [""])[0]
    # 2026-10-21 (review): "Reply to this please:" ... "Thanks\nAmara" was
    # taken for the owner Amara's own text; an intro that says the text came
    # to the user (to reply to, sent, from someone) keeps it someone else's
    if isinstance(sp, tuple) and len(first) > 1 and not _INCOMING.search(text[:sp[0]]):
        rest = text[sp[0]:]
        last = [l.strip() for l in rest.strip().splitlines() if l.strip()][-1:] or [""]
        # the signature may carry the surname ("Yours faithfully, Wanjiru Kamau")
        sur = "|".join(re.escape(w) for w in (owner or "").split()[1:]) or "(?!)"
        # 2026-10-12 (review): the initial is the owner's surname initial,
        # not any letter; "it's Thabo's turn" does not introduce Thabo
        ini = "".join(w[0] for w in (owner or "").split()[1:2]) or "(?!)"
        if (re.match(rf"(?:[\w ,!.'’-]{{0,25}}[,\s])?{re.escape(first)}\b(?:\s+(?:{sur}|(?-i:{re.escape(ini.upper())})\.?))?\W*(?:x+)?\W*$",
                     last[0], re.I)
                or re.search(rf"\b(?:i'?m|i’m|i am|my name is|this is|it'?s)\s+{re.escape(first)}\b(?!['’]s\b)", rest, re.I)):
            return "own"
    return sp


_INCOMING = re.compile(r"(?i)\b(?:reply(?:ing)? to|respond(?:ing)? to|answer(?:ing)? this|"
                       r"sent (?:me|us|this)|forwarded|received|got this|from (?:my|our|the|a|an|his|her|their)\b)")


def _paste_span0(text, owner=None):
    # a chat log or transcript (two or more speaker or time-stamped lines),
    # wherever it sits in the message
    chat = _chat_lines(text)
    if len(chat) >= 2:
        start = chat[0].start()
        after = text[chat[-1].start():]
        nl = re.search(r"\n\s*\n|\n(?=[^\n]*$)", after)
        end = chat[-1].start() + (nl.start() if nl else len(after))
        intro = text[:start]
        if _FRAME_OWN.search(_QUOTE_SPAN.sub(" ", intro)) and not _FROM_OTHER.search(intro):
            return "own"
        return start, end
    # "^ that's from my landlord": what is above the caret line is pasted
    car = re.search(r"(?m)^\s*[\^↑]+\s*\S", text)
    if car and car.start() > 0:
        if _FRAME_OWN.search(text[car.start():]) and not _FROM_OTHER.search(text[car.start():]):
            return "own"
        return 0, car.start()
    # a letter addressed to the user by name ("Hi Thabo, Mr Eze here")
    first = ((owner or "").split() or [""])[0]
    if first and re.match(rf"\s*(?:hi|hello|hey|dear|morning|evening)\s+{re.escape(first)}\b", text, re.I):
        st = _structure_span(text)
        return st if isinstance(st, tuple) else (0, len(text))
    st = _structure_span(text)
    if st is not None:
        return st
    # a chat log ("[12/03, 18:22] Sasha: ...", "Dana Whitfield  10:42 AM")
    m = _CHAT.search(text)
    if m:
        end = len(text)
        para = re.search(r"\n\s*\n", text[m.start():])
        if para:
            end = m.start() + para.start()
        return m.start(), end
    for pat in (_PASTING, _RECEIVED, _OTHERS_MAT, _FROM_SOURCE, _TRANSFORM_INTRO, _FOUND, _MAT_COLON):
        m = pat.search(text)
        if not m or not text[m.end():].strip():
            continue
        # the clause next to the pasted text decides ("ignore my own bio,
        # read this CV:" introduces someone else's)
        intro = re.split(r"[.;!?]\s|,\s(?=\w+\s+(?:this|the|my|it)\b)", text[:m.end()])[-1]
        if _OWN_MARK.search(intro):
            return "own"
        if pat is _MAT_COLON and re.search(r"\b(?:question|update|context|issue|problem)\b", intro, re.I):
            continue
        rest = text[m.end():]
        q = _QUOTE_SPAN.match(rest.strip())
        start = m.end()
        return start, start + _own_tail(rest)
    # a letter on one line, addressed to someone, signed by someone else,
    # that the user asks how to answer
    g = _GREET_INLINE.match(text)
    if g:
        s = _SIGN_INLINE.search(text)
        end = s.end() if s else (text.find("\n\n") if "\n\n" in text else len(text))
        after = text[end:]
        if _REPLYISH.search(after) and not _OWN_MARK.search(after):
            return 0, end
        if _OWN_MARK.search(after):
            return "own"
        return _letter_span(text, owner)
    # quoted sentences ("'I always eat breakfast at 6.' what does this mean")
    for q in _QUOTE_SPAN.finditer(text):
        body = q.group(1) or q.group(2)
        if (len(body.split()) >= 5 and len(q.group(0)) < 0.8 * len(text.strip()) and _SAID.search(body)
                and not re.search(r"\b(?:called|named|titled)\W*$", text[:q.start()], re.I)
                and not _OWN_MARK.search(text[:q.start()])
                and not _SELF_QUOTE.search(text[:q.start()])):
            return q.start(), q.end()
    # text, a blank line, then a question about it ("is this bad advice?")
    paras = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if len(paras) >= 2 and _EVAL_Q.match(paras[-1].strip()):
        cut = text.rstrip().rfind(paras[-1].strip())
        return 0, cut
    return _letter_span(text, owner)


# 2026-10-13 (real emails, cases_dev_real.jsonl: the rules above found 6 of
# 30). A real email is seldom set off by a blank line or introduced in the
# same message; the user says "should I say yes to this?" in the next one,
# or nothing. What gives it away is that it is written TO someone: several
# lines that open by addressing a person by name ("Lee,", "Hi, Jan!",
# "Joao -"), or close with a name ("Bill"), that is not the owner's. A
# message signed with the owner's name stays theirs (_paste_span). Several
# lines: a chat turn like "Hey Mel! How are you?" is one line.
_NOT_ADDRESSEE = {w.lower() for w in """
    I Hi Hey Hello Dear Morning Evening Afternoon Thanks Thank Cheers Okay Ok OK Yes Yeah Yep No Nope Sure
    So Well Also Anyway Actually Basically Honestly Seriously Really Sorry Please Hmm Ugh Wow Great Cool
    Right Alright Fine Good Nice Perfect Awesome Today Tonight Tomorrow Yesterday Now Then Again Here There
    This That These Those It My Our We You They He She Note Update Context Question Quick Background
    Summary First Firstly Second Finally Lastly However Btw FYI PS Edit Meanwhile Otherwise Unfortunately
    Fortunately Luckily Sadly Apparently Obviously Clearly Personally Ideally Agreed Done Noted Correct True
    Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July
    August September October November December Weekend Update Reminder Attention Team All Everyone Folks
    Guys Sir Madam Regards Best Love Sincerely Warmly Kind Many Subject From To Sent Date
    Claude ChatGPT GPT Gemini Codex Copilot Cursor Assistant Bard Siri Alexa Bot
    """.split()}   # the last line: people address the assistant by name too
_TITLE = r"(?:(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s+)?"
_NAME = r"(?-i:[A-Z][a-z'’]+)(?:\s+(?-i:[A-Z][a-z'’]+))?"
# "Lee,", "Hi, Jan!", "Dear Mr. Lay,", "Joao -", "Juan......", "Hey, AC!";
# a name and a colon only alone on its line ("Flutter: ..." is a label)
_ADDRESS = re.compile(r"^\W*(?:(?:(?:hi|hello|hey|dear|good\s+(?:morning|afternoon|evening))[\s,]+)" + _TITLE
                      + r"(" + _NAME + r"|(?-i:[A-Z]{2,3}))|" + _TITLE + r"(" + _NAME + r"))"
                      r"\s*(?:[,!]|\s-+(?:\s|$)|-+\s*$|\.{3,}|:\s*$)", re.I)
_LETTER_OPEN = re.compile(r"^\W*(?:how are you(?: doing)?\b|i hope (?:you|your|this|all|everyone)\b[^.\n]{0,40}\bwell\b|"
                          r"hope (?:you(?:'|’)re|you are|all is) (?:well|doing well|good)\b)", re.I)
# a formal sign-off ends a letter (not "thanks": people end requests to an
# assistant with it), alone or before the name
# (2026-10-17: this was also named _SIGNOFF and replaced the compiled
# pattern above, so _drop_pasted_old crashed on any message with a greeting
# line after its first; LongMemEval found it)
_SIGNOFF_WORDS = (r"(?:(?:with\s+)?(?:best|kind|warm(?:est)?)\s+(?:regards|wishes)|regards|sincerely|respectfully|"
                  r"yours(?:\s+(?:truly|sincerely|faithfully))?|best\s+wishes|all\s+the\s+best|later|love)")
_SIGNOFF_ALONE = re.compile(r"^" + _SIGNOFF_WORDS + r"\W*$", re.I)
_SIGNATURE = re.compile(r"^(?:[-–—]\s*)?(?:" + _SIGNOFF_WORDS + r"[,!.]?\s+)?"
                        r"((?-i:[A-Z][a-z'’]+)(?:\s+(?-i:[A-Z][a-z'’.]+)){0,2}|(?-i:[A-Z])\.?)\W*$", re.I)


def _letter_span(text, owner):
    if "```" in (text or "") or re.search(r"`[^`\n]+`", text or ""):
        return None                      # code: a coding message, not a letter
    paras = [m for m in re.finditer(r"\S(?:.|\n(?!\s*\n))*", text or "")]
    if not paras:
        return None
    first = ((owner or "").split() or [""])[0].lower()

    def other(name):
        w = ((name or "").split() or [""])[0].lower().rstrip(".")
        return bool(w) and w not in _NOT_ADDRESSEE and w != first

    def addressed(line):
        a = _ADDRESS.match(line)
        return bool(a and other(a.group(1) or a.group(2))) or bool(_LETTER_OPEN.match(line))

    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if len(lines) < 3:
        return None
    sig = _SIGNATURE.match(lines[-1])
    signed = (sig and other(sig.group(1)) and len(lines[-1]) <= 40) or _SIGNOFF_ALONE.match(lines[-1])
    if addressed(lines[0]) or signed:
        return 0, len(text)
    # a short introduction, then the letter ("Is this sensible?\n\nJeff, ...")
    for m in paras[1:]:
        body = m.group(0)
        if addressed(body.splitlines()[0].strip()) and len(body.splitlines()) >= 2:
            return m.start(), len(text)
    return None


def _drop_pasted(text, owner=None, after=None):
    sp = _paste_span(text or "", owner, after)
    if sp == "own":
        return text
    if sp:
        s, e = sp
        head, tail = text[:s].rstrip(), text[e:].strip()
        return (head + ("\n\n" + tail if tail else "")) if (head or tail) else ""
    return _drop_pasted_old(text)


def _drop_pasted_old(text):
    lines = text.split("\n")
    # quoted reply lines and an email's header block are someone else's
    if any(l.lstrip().startswith(">") for l in lines[1:] + lines[:1]):
        lines = [l for l in lines if not l.lstrip().startswith(">")]
    hdr = next((i for i, l in enumerate(lines) if i and _HEADER.match(l.strip())), None)
    if hdr is not None:
        lines = lines[:hdr]
    # an email-shaped block (greeting line ... sign-off line) after the
    # message's first line: a letter the user pasted, not one to the assistant
    # 2026-10-21 (review): "Hey Claude," to the assistant is not a letter
    # (the user's own lines after it were dropped), and the line after the
    # sign-off goes only when it is the signature, not the user's next line
    for i, ln in enumerate(lines):
        if i and _GREETING.match(ln.strip()) and not _TO_ASSISTANT.match(ln.strip()):
            end = next((j for j in range(i + 1, len(lines))
                        if _SIGNOFF.match(lines[j].strip())), None)
            if end is not None:
                sig = (end + 1 < len(lines) and not _SIGNATURE.match(lines[end].strip())
                       and _SIGNATURE.match(lines[end + 1].strip()))
                lines[i:end + (2 if sig else 1)] = [""]
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
