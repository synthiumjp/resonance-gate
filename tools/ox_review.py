#!/usr/bin/env python3
"""Ask a long-context external model to red-team a bundle of our files.

NOT a judge. Keep this off the eval path -- RG pipeline judging/eval stays on
local GGUFs. This is for design review, gap-finding and adversarial critique
of our REASONING. Anything it says is a lead to VERIFY against the tree, never
a result to apply on trust.

PRIVACY: `stealth/*` models on OpenRouter are free because prompts are logged
and shared with the upstream lab. Do not send anything you would not publish.
Pass --model with a paid slug if that matters for a given bundle.

KEY, in precedence order:
  $OPENROUTER_API_KEY
  ~/rg_private/openrouter.env   (a line `OPENROUTER_API_KEY=sk-or-...`)

USAGE
  # the default p2 red-team bundle + prompt
  python3 tools/ox_review.py

  # your own question over your own files
  python3 tools/ox_review.py --ask "Where does this retry logic deadlock?" \
      --files src/queue.py src/worker.py --out queue_review.md

  # see exactly what would be sent, send nothing
  python3 tools/ox_review.py --dry-run
"""
import argparse, json, os, pathlib, sys, urllib.error, urllib.request

ROOT = pathlib.Path(os.environ.get("OX_ROOT", "/home/jp/rg"))
KEY_FILE = pathlib.Path.home() / "rg_private" / "openrouter.env"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

# default bundle: the claims (docs) plus the code that implements them, so a
# reviewer can catch drift between what we say and what runs.
DEFAULT_FILES = [
    "docs/HANDOVER_EXTRACTION.md",
    "docs/EXPERIMENT_LEDGER.md",
    "docs/OVERVIEW.md",
    "docs/ROADMAP.md",
    "docs/product-p2-prereg.md",
    "rgx/__init__.py",
    "rgx/check.py",
    "rgx/facts.py",
    "rgx/parse.py",
    "experiments/p2/memory_api.py",
    "experiments/p2/halumem_run.py",
]

# Wrapped around any --ask so a custom question still gets an adversarial
# reviewer rather than an agreeable one.
ASK_FRAME = """You are red-teaming a working ML systems research project. \
Find what is WRONG or MISSING; do not summarise, do not encourage. Assume the \
authors are competent and have thought of the obvious -- earn your keep on \
the non-obvious.

Cite the file and the specific claim or line you are attacking. If you are \
speculating, say so in the same sentence. Rank everything by how much it \
would change what we do next. If a concern is real but cheap to dismiss, give \
the one command that dismisses it. Being agreeable is a failure mode.

THE QUESTION:
{ask}

=== PROJECT FILES ===
"""

DEFAULT_PROMPT = """You are red-teaming an ML systems research project before \
it spends 11 GPU-hours on its next measurement. Your job is to find what is \
WRONG or MISSING, not to summarise or encourage. Assume the authors are \
competent and have already thought of the obvious; earn your keep on the \
non-obvious.

THE PROJECT. A deterministic (zero-model-call) memory extractor for \
conversational agents, `rgx`, evaluated on the HaluMem benchmark against a \
prompted 14B baseline. It parses dialogue with Stanza/UD and applies a \
person-shift transformation plus filters. Downstream it feeds a memory store \
that answers questions non-generatively (it joins stored fact values verbatim; \
it never prompts a model to compose).

THE IMMEDIATE DECISION you are reviewing:
The next queued change is "labeled hearsay in the QA context". Assistant \
claims about the user (evidential=report) are already segregated into a \
separate `hearsay` tier that never corroborates facts. That tier is returned \
by recall() but both answer surfaces currently ignore it. The plan is to \
surface hearsay candidates, labeled as hearsay, appended after non-hearsay \
candidates -- then re-judge BOTH arms in one 11-hour cycle, which will \
measure this change AND a previously-committed context-renderer bug fix \
(e248) TOGETHER, confounded.

DELIVER, in this order:

1. THE CONFOUND. Is running labeled-hearsay and the e248 renderer fix in one \
cycle defensible, or does it destroy attribution? If the combined number \
moves the wrong way, what exactly could and could not be concluded? Is there \
a cheap design (ablation on saved verdicts, a subset, a deterministic \
pre-check) that recovers attribution WITHOUT a second 11h cycle?

2. VALIDITY GAPS. Go after the measurement, hard. The docs record a history \
of instrument defects that flattered results (head-biased sampling, a recall \
definition mismatch, a token-overlap proxy that was barred). Given that \
track record, what defect is MOST LIKELY still live and undetected in the \
numbers as they now stand? Be specific about which reported number it would \
move and in which direction. Read the code, not just the prose -- flag any \
place the code does not do what the docs claim.

3. THE BLIND SPOT. What is this project not measuring at all that would \
change its conclusions? Consider: what "labeled hearsay" does to a judge that \
was never told hearsay exists; whether a non-generative answer surface is \
being scored by rubrics that assume a composed answer; whether the \
deterministic extractor's wins transfer off HaluMem's synthetic dialogue; \
generalisation from 2 held-out users.

4. THE BACKLOG CALL. Queued behind this: an updating/evolution-linking \
mechanism, plural agreement under owner possessives, a second user through \
the product path, and missed frame patterns. Is that the right order given \
the reported numbers (updating 12.6% vs LLM 4.3% -- both terrible in \
absolute terms)? What would you do instead and why?

RULES. Cite the file and the specific claim you are attacking. If you are \
speculating, say so in the same sentence. Do not restate our numbers back to \
us. Rank everything by how much it would change what we do on Monday. If a \
concern is real but cheap to dismiss, say how to dismiss it in one command. \
Being agreeable here is a failure mode -- if the plan is sound, say so in \
two sentences and spend your effort on 2 and 3.

=== PROJECT FILES ===
"""


def load_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key.strip()
    if KEY_FILE.exists():
        for line in KEY_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    sys.exit(f"no key: set $OPENROUTER_API_KEY or put one in {KEY_FILE}")


def build_bundle(files):
    parts, missing = [], []
    for rel in files:
        p = pathlib.Path(rel)
        if not p.is_absolute():
            p = ROOT / rel
        if not p.exists():
            missing.append(str(rel))
            continue
        parts.append(f"\n\n----- FILE: {rel} -----\n{p.read_text()}")
    if missing:
        print(f"WARNING: missing from bundle: {missing}", file=sys.stderr)
    if not parts:
        sys.exit("bundle is empty -- nothing to review")
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser(
        description="Adversarial external review of a file bundle.")
    ap.add_argument("--model", default="stealth/ox-alpha",
                    help="OpenRouter slug (default: stealth/ox-alpha -- free, "
                         "1M ctx, PROMPTS ARE LOGGED)")
    ap.add_argument("--ask", help="your question; wrapped in the adversarial "
                                  "frame. omit for the default p2 red-team")
    ap.add_argument("--prompt-file", help="read the full prompt from a file, "
                                          "used verbatim (overrides --ask)")
    ap.add_argument("--files", nargs="+", default=None,
                    help="paths to bundle, relative to $OX_ROOT or absolute")
    ap.add_argument("--out", default="ox_review_out.md")
    ap.add_argument("--dry-run", action="store_true",
                    help="write the payload to ox_payload.txt, send nothing")
    args = ap.parse_args()

    if args.prompt_file:
        head = pathlib.Path(args.prompt_file).read_text()
    elif args.ask:
        head = ASK_FRAME.format(ask=args.ask)
    else:
        head = DEFAULT_PROMPT

    content = head + build_bundle(args.files or DEFAULT_FILES)
    print(f"bundle: {len(content)} chars, ~{len(content)//4} tokens",
          file=sys.stderr)

    if args.dry_run:
        pathlib.Path("ox_payload.txt").write_text(content)
        print("dry run -- wrote ox_payload.txt, sent nothing", file=sys.stderr)
        return

    key = load_key()
    body = json.dumps({"model": args.model,
                       "messages": [{"role": "user", "content": content}]}).encode()
    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"})
    print(f"calling {args.model} ...", file=sys.stderr)
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:2000]}")

    if "choices" not in data:
        sys.exit(f"unexpected response: {json.dumps(data)[:2000]}")
    text = data["choices"][0]["message"]["content"]
    pathlib.Path(args.out).write_text(text)
    print(f"usage: {data.get('usage', {})}", file=sys.stderr)
    print(f"wrote {args.out} ({len(text)} chars)", file=sys.stderr)


if __name__ == "__main__":
    main()
