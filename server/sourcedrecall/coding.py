"""Coding history (2026-10-22, docs/PLAN_GAPS_2026-10-22.md G1): what a
coding session did, read from its tool calls, so a later session can ask
"what did we try for this error last time", "how are the tests run here",
"why did we drop that library". Native memory keeps the conclusions the
model chose to write down; this keeps the record, with no model call.

From a Claude Code transcript it keeps, per session:
  * episodes: a test, build or run command that failed, the error line, the
    files edited after it, and whether the same command passed later
    ("fixed") or not by the end of the session ("unresolved"), with the
    assistant's own explanation where it gave one;
  * commands that worked (tests, builds, installs, runs), not exploration
    (ls, cat, grep ...);
  * commits, with their messages;
  * decisions, from what the user or the assistant said ("let's use X
    instead of Y", "don't add Z");
  * the session itself: its first request, branch and files edited;
  * excerpts (2026-10-23, from the coding recall dev set: the answer to
    "why did we ..." is usually in the assistant's own explanation): the
    session as short searchable passages, what the user and the assistant
    said and each tool call by its command or file, a failed command with
    up to three lines of its output that name the problem (300 characters).

Tool output is untrusted text: only the command (written by the assistant),
its status and a few error lines (cut short, secrets scrubbed) are kept, never
whole outputs, and none of it becomes a fact about the user. Each record is
one line of text with its kind, date, project and session id.
"""
import json
import os
import re

from sourcedrecall.secrets import scrub

# What a command is, from its program and subcommand (not a text search over
# the line: "-vf scale" is not "lint", "Matte-Black" is not "black").
_PROGS = {
    "test": {"pytest", "py.test", "tox", "nox", "jest", "vitest", "mocha", "karma",
             "rspec", "phpunit", "ctest", "unittest", "playwright"},
    "build": {"cmake", "tsc", "webpack", "esbuild", "rollup", "bazel"},
    "lint": {"ruff", "flake8", "pylint", "mypy", "pyright", "eslint", "prettier",
             "black", "isort", "golangci-lint", "shellcheck", "biome", "stylelint"},
}
_SUBS = {   # program -> {subcommand: kind}
    "go": {"test": "test", "build": "build", "vet": "lint", "get": "install", "mod": "install", "run": "run"},
    "cargo": {"test": "test", "build": "build", "check": "build", "clippy": "lint",
              "add": "install", "run": "run", "fmt": "lint"},
    "swift": {"test": "test", "build": "build", "run": "run"},
    "dotnet": {"test": "test", "build": "build", "run": "run", "restore": "install"},
    "mix": {"test": "test", "compile": "build", "deps.get": "install"},
    "deno": {"test": "test", "run": "run", "lint": "lint", "check": "build"},
    "bun": {"test": "test", "build": "build", "install": "install", "add": "install", "run": None},
    "npm": {"test": "test", "t": "test", "install": "install", "i": "install", "ci": "install",
            "run": None, "exec": None},
    "yarn": {"test": "test", "add": "install", "install": "install", "build": "build",
             "lint": "lint", "run": None},
    "pnpm": {"test": "test", "add": "install", "install": "install", "i": "install",
             "build": "build", "lint": "lint", "run": None},
    "make": {"test": "test", "check": "test", "tests": "test", "lint": "lint"},
    "mvn": {"test": "test", "verify": "test", "package": "build", "install": "build", "compile": "build"},
    "gradle": {"test": "test", "check": "test", "build": "build", "assemble": "build"},
    "gradlew": {"test": "test", "check": "test", "build": "build", "assemble": "build"},
    "docker": {"build": "build", "compose": "run", "run": "run"},
    "vite": {"build": "build"},
    "pip": {"install": "install"}, "pip3": {"install": "install"},
    "uv": {"add": "install", "sync": "install", "pip": "install", "build": "build"},
    "poetry": {"add": "install", "install": "install", "build": "build"},
    "brew": {"install": "install"}, "apt": {"install": "install"},
    "apt-get": {"install": "install"}, "conda": {"install": "install"},
    "gem": {"install": "install"}, "bundle": {"install": "install"},
    "git": {k: "git" for k in ("commit", "push", "pull", "merge", "rebase", "checkout",
                                "switch", "reset", "revert", "cherry-pick", "stash", "tag")},
}
_SCRIPT_KIND = re.compile(r"^(test|tests|e2e|spec|check)(:|$)|^(build|compile)(:|$)|^lint(:|$)")
_RUNNERS = {"python", "python3", "node", "ruby", "java", "bash", "sh", "zsh", "perl", "php"}
# exploration and status checks: never a record, and their non-zero exits
# ("disabled", grep finding nothing) are not failures
_READ_ONLY = {
    "ls", "ll", "cat", "bat", "head", "tail", "less", "more", "grep", "rg", "egrep", "fgrep",
    "ag", "find", "fd", "pwd", "cd", "echo", "printf", "wc", "which", "type", "whereis",
    "file", "stat", "du", "df", "tree", "awk", "sort", "uniq", "diff", "cmp", "date",
    "whoami", "id", "hostname", "uname", "env", "printenv", "history", "true", "false",
    "sleep", "clear", "readlink", "realpath", "basename", "dirname", "journalctl", "ps",
    "pgrep", "lsof", "top", "uptime", "free", "jq", "yq", "test", "[", "command", "xxd",
    "od", "strings", "md5sum", "sha256sum", "shasum", "nproc", "sysctl", "ip", "ifconfig",
    "ping", "dig", "nslookup", "tput", "column", "cut", "tr", "tee", "xargs", "seq",
    "source", ".", "export", "set", "unset", "alias", "pushd", "popd", "wait", "kill",
    "pkill", "open", "xdg-open", "code", "ssh", "scp", "curl", "wget", "gh", "mkdir",
    "touch", "cp", "mv", "rm", "ln", "chmod", "chown", "tar", "zip", "unzip", "sed",
}
_READ_ONLY_SUBS = {
    "git": {"status", "log", "diff", "show", "branch", "remote", "rev-parse", "blame",
            "ls-files", "grep", "fetch", "describe", "config", "shortlog", "reflog", "add"},
    "systemctl": None, "docker": {"ps", "logs", "images", "inspect", "exec"},
    "kubectl": {"get", "describe", "logs"}, "npm": {"ls", "view", "outdated", "config"},
    "pip": {"show", "list", "freeze"}, "pip3": {"show", "list", "freeze"},
    "brew": {"list", "info", "search"}, "conda": {"list", "info", "env"},
    "pacman": {"-Q", "-Qi", "-Ql", "-Ss", "-Si"}, "dpkg": {"-l", "-L", "-s"},
}
_PRIORITY = ["test", "build", "lint", "install", "git", "run", "other"]
_LOOP = re.compile(r"^(for|while|until|if|case|select|function)\b|^\{|^\(")


def _split(cmd):
    """A shell line -> its commands, split at && || ; | and newlines outside
    quotes, $( ) and backticks; a loop or condition stays whole."""
    parts, cur, q, depth, i = [], [], None, 0, 0
    while i < len(cmd):
        c = cmd[i]
        if q:
            cur.append(c)
            if c == "\\" and q == '"' and i + 1 < len(cmd):
                cur.append(cmd[i + 1])
                i += 1
            elif c == q:
                q = None
        elif c in "'\"`":
            q = c
            cur.append(c)
        elif cmd.startswith("$(", i):
            depth += 1
            cur.append("$(")
            i += 1
        elif c == ")" and depth:
            depth -= 1
            cur.append(c)
        elif depth == 0 and (cmd.startswith("&&", i) or cmd.startswith("||", i)):
            parts.append("".join(cur))
            cur = []
            i += 1
        elif depth == 0 and c in ";|\n":
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    parts.append("".join(cur))
    parts = [p.strip() for p in parts if p.strip()]
    if any(_LOOP.match(p) for p in parts):
        return [" ".join(cmd.split())]
    return parts


_WRAPPERS = {"sudo", "time", "nice", "nohup", "exec", "timeout", "caffeinate", "stdbuf", "env"}
_LAUNCH = [("uv", "run"), ("poetry", "run"), ("pipenv", "run"), ("pdm", "run"), ("hatch", "run"),
           ("rye", "run"), ("bun", "x"), ("pnpm", "exec"), ("pnpm", "dlx"), ("yarn", "dlx"),
           ("npm", "exec"), ("conda", "run")]


def _words(part):
    """A command's words after VAR=value, wrappers (sudo, nice -n 10, timeout
    60) and launchers (uv run, npx --yes, python -m): ["pytest", "tests/a.py", ...]."""
    w = part.split()
    while w:
        if re.match(r"^\w+=", w[0]):
            w = w[1:]
        elif w[0] in _WRAPPERS:
            w = w[1:]
            while w and (w[0].startswith("-") or re.fullmatch(r"\d+[smh]?", w[0])):
                w = w[1:]
        elif w[0] in ("npx", "bunx", "pnpx"):
            w = w[1:]
            while w and w[0].startswith("-"):
                w = w[1:]
        elif len(w) > 1 and (w[0], w[1]) in _LAUNCH:
            w = w[2:]
            while w and w[0].startswith("-"):
                w = w[1:]
        elif len(w) > 2 and w[0] in ("python", "python3") and w[1] == "-m":
            w = w[2:]
        else:
            break
    if w:
        w[0] = os.path.basename(w[0]) if "/" in w[0] and not w[0].startswith("./") else w[0]
    return w


def _part_kind(part):
    w = _words(part)
    if not w:
        return None
    prog, sub = w[0], (w[1] if len(w) > 1 else "")
    if prog in _READ_ONLY_SUBS and (_READ_ONLY_SUBS[prog] is None or sub in _READ_ONLY_SUBS[prog]):
        return None
    for kind, progs in _PROGS.items():
        if prog in progs:
            return kind
    if prog in _SUBS:
        if sub in _SUBS[prog]:
            k = _SUBS[prog][sub]
            if k is None and len(w) > 2:          # npm run test:unit, yarn run build
                m = _SCRIPT_KIND.match(w[2])
                return ("test" if m.group(1) else "build" if m.group(3) else "lint") if m else "run"
            return k or "run"
        if prog in ("npm", "yarn", "pnpm", "bun") and _SCRIPT_KIND.match(sub):
            m = _SCRIPT_KIND.match(sub)
            return "test" if m.group(1) else "build" if m.group(3) else "lint"
        if prog == "make":
            return "build"
        if prog == "git":
            return None
    if prog in _READ_ONLY:
        return None
    if prog in _RUNNERS or prog.startswith("./"):
        return "run"
    return "other"


def _main_part(cmd):
    """-> (kind, part): the command in the line that matters most."""
    best = (None, None)
    for p in _split(cmd):
        k = _part_kind(p) if not _LOOP.match(p) else _loop_kind(p)
        if k and (best[0] is None or _PRIORITY.index(k) < _PRIORITY.index(best[0])):
            best = (k, p)
    return best


def _loop_kind(p):
    inner = [x for x in re.split(r";|\bdo\b|\bthen\b|\bdone\b|\bfi\b", p)[1:] if x.strip()]
    kinds = [k for k in (_part_kind(x.strip()) for x in inner) if k]
    return min(kinds, key=_PRIORITY.index) if kinds else None


def _core(cmd):
    """The command that matters in a compound line: "cd x && FOO=1 pytest -q
    2>&1 | tail -5" -> "pytest -q"."""
    kind, part = _main_part(cmd)
    if part is None:
        parts = _split(cmd)
        part = parts[-1] if parts else cmd
    part = re.sub(r"^(\w+=\S+\s+)+", "", part)
    return re.sub(r"\s+[12]?>&[12]$|\s+2>/dev/null$", "", part).strip()


def kind_of(cmd):
    return _main_part(cmd)[0]


def _key(cmd):
    """Commands that count as the same run: "uv run pytest tests/a.py -x" and
    "pytest tests/a.py" -> "pytest tests/a.py"; "npx tsc --strict x.ts" and
    "bun x tsc x.ts" -> "tsc x.ts"."""
    w = [t for t in _words(_core(cmd)) if not t.startswith("-")]
    return " ".join(w[:3])


def _prog(key):
    return key.split(" ")[0] if key else ""


_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\[[0-9;]{1,6}m")
_ERROR_LINE = re.compile(
    r"^\s*(?:E\s+)?("
    r"[A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt|Warning)\b.*"
    r"|FAILED\b.*|FAIL\b.*|ERROR\b.*|error(?:\[\w+\])?:.*|fatal:.*|panic:.*"
    r"|npm ERR!.*|Traceback \(most recent call last\).*"
    r"|.*command not found.*|.*No such file or directory.*"
    r"|.*Permission denied.*|.*Segmentation fault.*|Killed\b.*"
    r"|.*\b\d+ failed\b.*)", re.M)
_EXIT = re.compile(r"\bExit code (\d+)\b")
_CANCELLED = "Sibling tool call errored"
_EXPLAIN = re.compile(
    r"\b(because|caused by|the (problem|issue|bug|cause|culprit|failure|error) "
    r"(is|was)|root cause|that's why|fails? (since|when)|the fix (is|was))\b", re.I)
# the assistant's sentences count only in these forms; "instead of" in its
# reports is mostly description ("the card fills 45% instead of 31%")
_ASSISTANT_DECISION = re.compile(
    r"\b(let'?s|we('ll| will| should| decided to)|i('ll| will)|i'm going to)\s+"
    r"(use|go with|switch to|stick with|move to|drop|avoid|replace|stop using)\b"
    r"|\b(decided|we agreed)\b", re.I)
_DECISION = re.compile(
    r"\b(let'?s|we('ll| will| should| decided to)?|i('ll| will)|going to|switch(ed|ing)? to)\s+"
    r"(use|go with|switch to|stick with|move to|drop|keep|avoid|replace|remove|"
    r"try|pin|stop using)\b"
    r"|\binstead of\b|\brather than\b"
    r"|\b(don'?t|do not|never|stop|no more)\s+(use|add|run|commit|push|call|import|"
    r"touch|change|edit|delete|install|depend on)\b"
    r"|\b(decided|we agreed|the decision)\b", re.I)
_SENT = re.compile(r"(?<=[.!?])\s+|\n+")
_ENV_SECRET = re.compile(
    r"\b([A-Z0-9_]*(KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD|CREDENTIALS?|AUTH)[A-Z0-9_]*)="
    r"(\"[^\"]*\"|'[^']*'|\S+)", re.I)
_HEADER_SECRET = re.compile(r"(?i)(authorization|x-api-key|api-key|cookie)\s*:\s*[^\"'\n]+")
_EDIT_TOOLS = ("Edit", "MultiEdit", "Write", "NotebookEdit")
_MAX_CMD = 200
_MAX_ERR = 160


def _unsecret(cmd):
    cmd = " ".join(str(cmd or "").split())
    cmd = _ENV_SECRET.sub(lambda m: f"{m.group(1)}=[removed]", cmd)
    return _HEADER_SECRET.sub(lambda m: f"{m.group(1)}: [removed]", cmd)


def _clean_command(cmd):
    """The command as shown: secrets in VAR=value and headers removed, then
    the same scrub as messages (a key pasted as an argument), cut short."""
    cmd = scrub(_unsecret(cmd))
    return cmd if len(cmd) <= _MAX_CMD else cmd[:_MAX_CMD - 3] + "..."


def error_line(output):
    """The line of a failed command's output that says what went wrong: the
    last exception line of a traceback, a FAILED test, an "error:" line."""
    text = _ANSI.sub("", str(output or ""))
    hits = [m.group(1).strip() for m in _ERROR_LINE.finditer(text)]
    hits = [h for h in hits if not h.startswith("Traceback")]
    if not hits:
        lines = [l.strip() for l in text.splitlines()
                 if l.strip() and not _EXIT.fullmatch(l.strip())]
        if not lines:
            return None
        hits = [lines[-1]]
    # the exception that ended a traceback, else an "error:" line, else the
    # first failure named
    exc = [h for h in hits if re.match(r"[A-Za-z_][\w.]*(Error|Exception)\b", h)]
    err = [h for h in hits if re.match(r"(?i)(error(\[\w+\])?|fatal|panic):", h)]
    line = exc[-1] if exc else err[0] if err else hits[0]
    line = scrub(" ".join(line.split()))
    return line if len(line) <= _MAX_ERR else line[:_MAX_ERR - 3] + "..."


_PROBLEM = re.compile(
    r"(?i)\b(error|errors|warning|warn|failed|failure|exceeds|expected|cannot|"
    r"can't|unable|missing|undefined|not found|unexpected|invalid)\b")
_NO_PROBLEM = re.compile(r"(?i)\b(0|no) (errors?|warnings?|failures?|problems?)\b")
_FAIL_LINES, _FAIL_CHARS = 3, 300


def failure_lines(output):
    """What a failed command's output says went wrong, for excerpts: the
    error line, then up to two more lines that name a problem (a linter's
    "file:line error ..." lines, a type checker's), at most 300 characters."""
    first = error_line(output)
    if not first:
        return None
    seen, out = {first}, [first]
    for l in _ANSI.sub("", str(output or "")).splitlines():
        l = scrub(" ".join(l.split()))
        if len(out) >= _FAIL_LINES:
            break
        if l and l not in seen and _PROBLEM.search(l) and not _NO_PROBLEM.search(l) \
                and not _EXIT.fullmatch(l):
            seen.add(l)
            out.append(l if len(l) <= _MAX_ERR else l[:_MAX_ERR - 3] + "...")
    t = " | ".join(out)
    return t if len(t) <= _FAIL_CHARS else t[:_FAIL_CHARS - 3] + "..."


def _rel(path, cwd):
    p = str(path or "")
    if cwd and p.startswith(cwd.rstrip("/") + "/"):
        return p[len(cwd.rstrip("/")) + 1:]
    return os.path.basename(p) if os.path.isabs(p) else p


def _commit_message(cmd):
    m = re.search(r"git commit\b.*?\s-a?m\s*(\"(?:[^\"\\]|\\.)*\"|'[^']*')", cmd, re.S)
    if not m:
        return None
    lines = [l.strip() for l in m.group(1)[1:-1].splitlines() if l.strip()]
    if lines and lines[0].startswith("$(cat <<"):      # -m "$(cat <<'EOF' ... EOF )"
        lines = lines[1:]
    first = next((l for l in lines if l not in ("EOF", ")")), "")
    first = scrub(first)
    return first[:160] or None


def _sentences(text, rx, limit=2):
    out = []
    for s in _SENT.split(str(text or "")):
        s = " ".join(re.sub(r"\*\*|__|^\s*(?:[-*+]|\d+\.)\s+", "", s).split())
        if 4 <= len(s.split()) <= 60 and rx.search(s) and "`" not in s[:1]:
            out.append(scrub(s))
            if len(out) >= limit:
                break
    return out


def _explanation(text):
    """The assistant's first sentence that explains a failure. One that only
    announces it ("I found the root cause.", "It was caused by:") gives way
    to the sentence after it, where the cause is."""
    sents = [" ".join(re.sub(r"\*\*|__|^\s*(?:[-*+]|\d+\.)\s+", "", x).split())
             for x in _SENT.split(str(text or ""))]
    sents = [x for x in sents if x]
    for i, t in enumerate(sents):
        if not _EXPLAIN.search(t):
            continue
        if t.endswith(":") or len(t.split()) < 6:
            t = sents[i + 1] if i + 1 < len(sents) else ""
        if 4 <= len(t.split()) <= 60 and not t.startswith("`"):
            return scrub(t)
    return None


def events(path, classify):
    """-> [event] in transcript order. classify(line_obj) -> (role, text) or
    None is the hook's own filter for what the person typed and the
    assistant's visible text (claude_hooks._classify), so nothing it skips is
    read here as speech. Tool events: {"tool", "input", "output", "error",
    "ts"}; a tool call is paired with its result by id."""
    out, pending = [], {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if o.get("isSidechain") or o.get("isMeta"):
                continue
            ts = o.get("timestamp")
            content = (o.get("message") or {}).get("content")
            if o.get("type") == "assistant" and isinstance(content, list):
                for it in content:
                    if isinstance(it, dict) and it.get("type") == "tool_use":
                        ev = {"tool": it.get("name"), "input": it.get("input") or {},
                              "output": None, "error": None, "ts": ts}
                        pending[it.get("id")] = ev
                        out.append(ev)
            if o.get("type") == "user" and isinstance(content, list):
                for it in content:
                    if isinstance(it, dict) and it.get("type") == "tool_result":
                        ev = pending.pop(it.get("tool_use_id"), None)
                        if ev is None:
                            continue
                        c = it.get("content")
                        if isinstance(c, list):
                            c = "\n".join(x.get("text", "") for x in c
                                          if isinstance(x, dict))
                        ev["output"] = str(c or "")
                        if _CANCELLED in ev["output"][:200]:
                            # Claude Code cancelled it when a parallel call failed:
                            # it never ran, so it neither failed nor worked
                            ev["cancelled"] = True
                        m = _EXIT.search(ev["output"][:200])
                        ev["error"] = bool(it.get("is_error")) or bool(m and m.group(1) != "0")
            said = classify(o)
            if said:
                out.append({"say": said[0], "text": said[1], "ts": ts})
    return out


def records(evs, cwd=None, branch=None):
    """-> [{"kind", "text"}] for one session (see the module note)."""
    recs, open_eps, edited, worked, seen = [], {}, [], {}, set()
    title = next((e["text"] for e in evs if e.get("say") == "user"), None)

    def add(kind, text):
        if text and (kind, text) not in seen:
            seen.add((kind, text))
            recs.append({"kind": kind, "text": text})

    for e in evs:
        if e.get("cancelled"):
            continue
        if "say" in e:
            for ep in open_eps.values():
                if e["say"] == "assistant" and not ep["why"]:
                    ep["why"] = _explanation(e["text"])
                if e["say"] == "user" and not ep["user"]:
                    ep["user"] = " ".join(e["text"].split())[:160]
            who = "the user" if e["say"] == "user" else "the assistant"
            rx = _DECISION if e["say"] == "user" else _ASSISTANT_DECISION
            for s in _sentences(e["text"], rx):
                add("decision", f"{who} said: {s}")
            continue
        name, inp = e["tool"], e["input"]
        if name in _EDIT_TOOLS:
            f = _rel(inp.get("file_path") or inp.get("notebook_path"), cwd)
            if f:
                if f not in edited:
                    edited.append(f)
                for ep in open_eps.values():
                    if f not in ep["files"]:
                        ep["files"].append(f)
            continue
        if name != "Bash" or e["output"] is None:
            continue
        full = _unsecret(inp.get("command"))
        kind = kind_of(full)
        cmd = _clean_command(_core(full))
        if kind is None or not re.match(r"[\w./~]", cmd):   # a fragment the split could not place
            continue
        if kind == "git":
            msg = _commit_message(str(inp.get("command") or ""))
            if msg and not e["error"]:
                add("commit", f"committed: {msg}")
            continue
        key = _key(full)
        if e["error"]:
            err = error_line(e["output"]) or "no error line"
            ep = open_eps.get(key)
            if ep is None:
                open_eps[key] = {"cmd": cmd, "kind": kind, "errors": [err], "files": [],
                                 "why": None, "user": None}
            elif err not in ep["errors"]:
                ep["errors"].append(err)
            continue
        worked[key] = (kind, cmd)
        ep = open_eps.pop(key, None)
        if ep is None:   # the same program passing with other arguments or launcher
            # (tests, builds and linters only: "tool --version" failing is not
            # fixed by "tool perf" passing)
            same = [k for k in open_eps if kind in ("test", "build", "lint")
                    and _prog(k) == _prog(key) and open_eps[k]["kind"] == kind]
            ep = open_eps.pop(same[0]) if same else None
        if ep is not None:
            add("fixed", _episode(ep, cmd, fixed=True))
    for ep in open_eps.values():
        add("unresolved", _episode(ep, None, fixed=False))
    for kind, cmd in worked.values():
        if kind not in ("run", "other"):
            add("command", f"{kind} command that worked: `{cmd}`")
    if title:
        t = " ".join(scrub(title).split())
        t = t if len(t) <= 160 else t[:157] + "..."
        files = ", ".join(edited[:8]) + (f" and {len(edited) - 8} more" if len(edited) > 8 else "")
        add("session", f"session: \"{t}\""
            + (f" on branch {branch}" if branch else "")
            + (f"; files edited: {files}" if edited else ""))
    return recs


def _episode(ep, fixed_cmd, fixed):
    errs = [e for e in ep["errors"] if e != "no error line"] or ep["errors"]
    s = f"`{ep['cmd']}` failed" + (f" with \"{errs[0]}\"" if errs[0] != "no error line" else "")
    if len(errs) > 1:
        s += "; then with " + "; then with ".join(f"\"{x}\"" for x in errs[1:3])
    if fixed:
        s += "; it passed after editing " + (", ".join(ep["files"][:6]) if ep["files"]
                                              else "nothing (rerun or environment)")
        if fixed_cmd and fixed_cmd != ep["cmd"]:
            s += f", run as `{fixed_cmd}`"
    else:
        s += "; still failing when the session ended" + (
            f" (files edited meanwhile: {', '.join(ep['files'][:6])})" if ep["files"] else "")
    if ep["why"]:
        s += f". The assistant's explanation: {ep['why'].rstrip('.')}"
    if ep["user"]:
        s += f". The user said meanwhile: {ep['user']}"
    return s


def branch_and_cwd(path):
    """The git branch and working directory Claude Code recorded."""
    branch = cwd = None
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                branch = branch or o.get("gitBranch") or None
                cwd = cwd or o.get("cwd") or None
                if branch and cwd:
                    break
    except OSError:
        pass
    return branch, cwd


_EXCERPT_CHARS = 1200
_SAY_CHARS = 800
# the start of a command's output in excerpts; 0 (the default) keeps none.
# A dev experiment (coding recall v1), not a setting for users yet.
_OUTPUT_CHARS = int(os.environ.get("SOURCEDRECALL_EXCERPT_OUTPUT", "0") or 0)


def excerpts(evs, cwd=None, size=_EXCERPT_CHARS):
    """-> [{"kind": "excerpt", "text"}]: the session in passages of about
    `size` characters, one line per thing said or done. Tool output is not
    kept, except what a failed command's output says went wrong."""
    lines = []
    for e in evs:
        if e.get("cancelled"):
            continue
        if "say" in e:
            t = " ".join(scrub(e["text"]).split())
            if t:
                who = "USER" if e["say"] == "user" else "ASSISTANT"
                lines.append(f"{who}: " + (t if len(t) <= _SAY_CHARS else t[:_SAY_CHARS - 3] + "..."))
            continue
        inp = e["input"] or {}
        if e["tool"] == "Bash":
            what = _clean_command(inp.get("command"))
        else:
            what = (_rel(inp.get("file_path") or inp.get("notebook_path"), cwd)
                    or scrub(" ".join(str(inp.get("pattern") or inp.get("url")
                                          or inp.get("description") or "").split()))[:_MAX_CMD])
        if not what:
            continue
        line = f"TOOL {e['tool']}: {what}"
        if e["error"]:
            line += f" -> failed: {failure_lines(e['output']) or 'no error line'}"
        elif _OUTPUT_CHARS and e["tool"] == "Bash" and e["output"]:
            o = " ".join(scrub(_ANSI.sub("", e["output"])).split())
            line += " -> " + (o if len(o) <= _OUTPUT_CHARS else o[:_OUTPUT_CHARS - 3] + "...")
        lines.append(line)
    out, cur = [], ""
    for line in lines:
        if cur and len(cur) + len(line) > size:
            out.append(cur.rstrip())
            cur = ""
        cur += line + "\n"
    if cur.strip():
        out.append(cur.rstrip())
    return [{"kind": "excerpt", "text": t} for t in out]


def session_records(path, classify, cwd=None):
    branch, rec_cwd = branch_and_cwd(path)
    cwd = cwd or rec_cwd
    evs = events(path, classify)
    return records(evs, cwd=cwd, branch=None if branch in (None, "HEAD") else branch) \
        + excerpts(evs, cwd=cwd)
