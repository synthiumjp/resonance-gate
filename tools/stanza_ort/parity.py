"""Parity of stanza_ort (torch-free venv) against Stanza 1.14.0 on PyTorch (reference venv).

  python parity.py build                      -> corpus.json
  python parity.py ref single|bulk [N]        (reference venv: torch + stanza)    -> ref_<mode>.pkl
  python parity.py ort single|bulk [N]        (torch-free venv: numpy+onnxruntime) -> ort_<mode>.pkl
  python parity.py compare single|bulk        (either venv)
bulk = bulk_process on chunks of 64 texts (same chunks on both sides).
"""
import os, sys, json, pickle, time, random, ast, glob, resource, collections

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
sys.path.insert(0, HERE)
TAG = os.environ.get("PARITY_TAG", "")
CORPUS = os.path.join(HERE, os.environ.get("PARITY_CORPUS", "corpus.json"))
CHUNK = 64


# ------------------------------------------------------------------ corpus
def odd_inputs():
    L = []
    A = L.append
    A("")
    A(" ")
    A("\n\n")
    A("a")
    A("?")
    A("Hello")
    A("hello world")
    A("- apples\n- oranges\n- a very long item that goes on and on, with commas, and more commas\n- bananas")
    A("1. first thing\n2. second thing\n3. third thing")
    A("Shopping list:\n* milk\n* eggs\n* bread (whole grain)\n* butter")
    A("TODO:\n- fix the parser\n- write tests\n- ship it")
    A("Here's the call:\n```python\nsession.mount('https://', HTTPAdapter(max_retries=Retry(total=3)))\nr = session.get(url, timeout=10)\n```\nCan you check it?")
    A("The ingest worker keeps dying with `OSError: [Errno 24] Too many open files` in /srv/ingest/worker.py. Also, we are not on Kubernetes.")
    A("def f(x):\n    return x + 1\n\nprint(f(2))")
    A("cargo build is failing:\n```\nerror[E0382]: borrow of moved value: `reading`\n  --> src/feed.rs:41:22\n```\nCan you look?")
    A("SELECT name, COUNT(*) FROM users WHERE age > 30 GROUP BY name ORDER BY 2 DESC; -- top names")
    A("I love pizza \U0001F355 and sushi \U0001F363!! So good \U0001F60D\U0001F60D\U0001F60D")
    A("\U0001F389\U0001F389\U0001F389")
    A("Great job \U0001F44D\U0001F3FD, see you at 5pm ❤️")
    A("She said “I’ll be there at 6” and left. He replied ‘fine’ — then silence…")
    A("“Quoted at the start,” he said, “and ‘nested’ here.”")
    A("It’s John’s book, isn’t it? They’re here and we’ve got it. I’d say you’ll like it.")
    A("don't can't won't shouldn't I'm you're we're they've I'll she'd gonna wanna gotta cannot")
    A("DON'T SHOUT AT ME, I'M NOT DEAF!!!")
    A("lol idk what ur talking about tbh, im not even sure thats how it works")
    A("Visit https://www.example.com/path?x=1&y=2 or email john.doe@example.co.uk for details.")
    A("www.example.org is down; also try example.com/foo and foo@bar.baz.")
    A("Call me at (713) 571-9571 or 713-654-0365 ext x365 on 28/10/2004 or November 5, 1999 for $62,500.00.")
    A("Fax: 555-1234\nCell: 555-9876\nJob Group: Engineering\nNotice Regarding: Layoffs")
    A("Mr. Smith went to Washington D.C. on Jan. 5th at 3 p.m. with Dr. Jones, Ph.D.")
    A("e.g. this, i.e. that, etc. and so on... wait what?! really?? yes!!")
    A("What?!?! No way!!!! Seriously???")
    A("a" * 250)
    A("This has a very long token " + "x" * 300 + " in the middle of a sentence.")
    A("word " * 400)
    A(("I went to the store and bought some milk, then I came home and made dinner for the kids. " * 30).strip())
    A(("I went to the store and bought some milk. Then I came home and made dinner for the kids.\n\n") * 30)
    A(("Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua " * 40))
    A("x" * 1200)
    A("Line one\nLine two\nLine three\n\nParagraph two starts here\nand continues.\n\n\n\nParagraph three.")
    A("   leading and trailing spaces   ")
    A("tabs\tinside\tthis\ttext")
    A("Multiple    spaces     between      words.")
    A("Non-breaking space and zero​width and \u0097 control char here.")
    A("Café naïve façade über résumé Zürich Österreich Ångström")
    A("Bonjour, je m'appelle Marie et j'habite à Paris depuis 2010.")
    A("今天天气很好，我想去公园。")
    A("مرحبا بالعالم")
    A("Привет, мир! Как дела?")
    A("3.14159 is pi; 1,000,000 is a million; 2.5e10 is big; 10:30am; 5-3=2; 100% sure; #hashtag @mention")
    A("I paid $5.99 for 3 items (50% off) at 7:45 p.m.; total: €12,50 or £9.99.")
    A("A/B testing, and/or, he/she, 24/7, w/o, b/w, c/o")
    A("Well... I don't know... maybe? Perhaps - or not - who knows.")
    A("Hi!!! How are you??? I'm good!!!! Thanks...")
    A("(Parenthetical remark.) [Bracketed text.] {Braced text.} <Angle> text.")
    A("He said: \"Go!\" She said: 'No.' They said: \"Maybe 'later'.\"")
    A("I'm moving to Bristol. Actually no, I'm staying in Leeds. Or maybe not.")
    A("Yes.")
    A("No")
    A("OK, thanks!")
    A("Thanks a lot :)  see you soon ;-) xoxo :D :( :/ <3")
    A("CamelCaseIdentifier and snake_case_identifier and kebab-case-identifier in file_name.py")
    A("I have 2 cats, 3 dogs and 14 fish; my sister has none.")
    A("It's 5 o'clock somewhere, y'all. Ain't nobody got time for that. 'Twas the night before Christmas.")
    A("The U.S.A. and the U.K. signed an agreement. NASA's budget grew 3.5%.")
    A("ok so basically what happened was i went there and like nobody was there so i left")
    A("WHAT ARE YOU DOING HERE")
    A("what are you doing here")
    A("one.two.three.four. five six. seven;eight;nine,ten,eleven")
    A("end of sentence with no punctuation but a newline\n")
    A("\nstarts with a newline")
    A("Ends with two newlines.\n\n")
    A("She’s my friend.\n\nHe isn’t.\n")
    A("First sentence. Second sentence! Third sentence? Fourth sentence... Fifth.")
    A("Tom's dog's bone; the dogs' bones; James's book; the boss's car")
    A("I would've, could've, should've, might've, must've.")
    A("The quick brown fox jumps over the lazy dog. " * 3)
    A("Hello, my name is Inigo Montoya. You killed my father. Prepare to die.")
    return L


def build_corpus():
    texts, src = [], []
    def add(t, s):
        texts.append(t); src.append(s)
    d = json.load(open(os.path.join(HOME, "jpwork/locomo10.json")))
    for c in d:
        for k, v in c["conversation"].items():
            if isinstance(v, list):
                for t in v:
                    if t.get("text"):
                        add(t["text"], "locomo")
    fm = os.path.join(HOME, "jpwork/sdr/bench/false_memory")
    for f in sorted(glob.glob(os.path.join(fm, "cases*.jsonl"))):
        for line in open(f):
            case = json.loads(line)
            for conv in case.get("conversations", []):
                for turn in conv.get("turns", []):
                    if turn.get("role") == "user" and turn.get("content"):
                        add(turn["content"], "cases")
    for line in open(os.path.join(fm, "distractors_code.jsonl")):
        case = json.loads(line)
        for turn in case.get("turns", []):
            if turn.get("role") == "user" and turn.get("content"):
                add(turn["content"], "distractors_code")
    tree = ast.parse(open(os.path.join(HOME, "jpwork/sdr-dev/rgx/test_parse.py")).read())
    seen = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            s = node.value
            if len(s) >= 4 and " " in s and s not in seen:
                seen.add(s)
                add(s, "test_parse")
    for t in odd_inputs():
        add(t, "odd")
    rnd = random.Random(11)
    loc = [t for t, s in zip(texts, src) if s == "locomo"]
    # long messages: several real turns joined (spaces, newlines, blank lines, lists)
    for i in range(60):
        n = rnd.choice([8, 15, 30, 60])
        parts = rnd.sample(loc, n)
        sep = rnd.choice([" ", "\n", "\n\n", " - ", "\n- "])
        add(sep.join(parts), "long_mixed")
    # perturbed real turns: lowercased / uppercased / punctuation stripped / spacing noise
    for i in range(150):
        t = rnd.choice(loc)
        kind = i % 5
        if kind == 0: t = t.lower()
        elif kind == 1: t = t.upper()
        elif kind == 2: t = "".join(ch for ch in t if ch not in ".,!?;:")
        elif kind == 3: t = t.replace(" ", "  ").replace(".", " .")
        else: t = t.replace("'", "’").replace('"', "“")
        add(t, "perturbed")
    json.dump({"texts": texts, "src": src}, open(CORPUS, "w"), ensure_ascii=False)
    c = collections.Counter(src)
    print(len(texts), "texts", dict(c))


# ------------------------------------------------------------------ runners
def run(which, mode, limit):
    from canon import canon
    C = json.load(open(CORPUS))
    texts = C["texts"][:limit] if limit else C["texts"]
    if which == "ref":
        os.environ.setdefault("STANZA_RESOURCES_DIR", os.path.join(HOME, "jpwork/stanza_resources_114"))
        import torch, stanza
        torch.set_num_threads(4)
        nlp = stanza.Pipeline("en", dir=os.environ["STANZA_RESOURCES_DIR"], processors="tokenize,pos,lemma,depparse",
                              use_gpu=False, logging_level="ERROR", download_method=stanza.DownloadMethod.REUSE_RESOURCES)
        Doc = stanza.Document
        call, bulk = nlp, nlp.bulk_process
    else:
        import stanza_ort
        nlp = stanza_ort.Pipeline(os.path.join(HERE, os.environ.get("STANZA_ORT_MODELS", "models")))
        Doc = stanza_ort.Document
        call, bulk = nlp, nlp.bulk_process
        assert "torch" not in sys.modules
    res = [None] * len(texts)
    t0 = time.time()
    if mode == "single":
        for i, t in enumerate(texts):
            try:
                res[i] = canon(call(t))
            except Exception as e:
                res[i] = ("error", repr(e))
            if i % 500 == 0:
                print(which, mode, i, len(texts), round(time.time() - t0), "s", flush=True)
    else:
        for i in range(0, len(texts), CHUNK):
            chunk = texts[i:i + CHUNK]
            try:
                docs = bulk([Doc([], text=t) for t in chunk])
                for j, d in enumerate(docs):
                    res[i + j] = canon(d)
            except Exception as e:
                for j in range(len(chunk)):
                    res[i + j] = ("error", repr(e))
            if (i // CHUNK) % 10 == 0:
                print(which, mode, i, len(texts), round(time.time() - t0), "s", flush=True)
    el = time.time() - t0
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20   # MB on macOS
    out = os.path.join(HERE, f"{which}_{mode}{TAG}.pkl")
    pickle.dump({"res": res, "seconds": el, "maxrss_mb": rss, "n": len(texts)}, open(out, "wb"))
    print("done", which, mode, len(texts), "texts", round(el, 1), "s", "maxrss MB", round(rss), flush=True)


# ------------------------------------------------------------------ compare
WORD_FIELDS = ["text", "upos", "xpos", "feats", "lemma", "head", "deprel", "deps", "misc", "start_char", "end_char", "parent", "id", "sent_ok"]


def compare(mode, ref_name=None, ort_name=None, show=12):
    C = json.load(open(CORPUS))
    ref = pickle.load(open(os.path.join(HERE, ref_name or f"ref_{mode}{TAG}.pkl"), "rb"))["res"]
    ort = pickle.load(open(os.path.join(HERE, ort_name or f"ort_{mode}{TAG}.pkl"), "rb"))["res"]
    n = min(len(ref), len(ort))
    src = C["src"][:n]
    by = collections.defaultdict(lambda: collections.Counter())
    tot = collections.Counter()
    diffs = []
    for i in range(n):
        a, b, s = ref[i], ort[i], src[i]
        by[s]["texts"] += 1
        by["ALL"]["texts"] += 1
        if isinstance(a, tuple) or isinstance(b, tuple):
            same = (isinstance(a, tuple) and isinstance(b, tuple) and a[0] == b[0] == "error")
            by[s]["errors_both" if same else "error_mismatch"] += 1
            by["ALL"]["errors_both" if same else "error_mismatch"] += 1
            if not same:
                diffs.append((i, "error", str(a)[:120], str(b)[:120]))
            else:
                by[s]["identical"] += 1; by["ALL"]["identical"] += 1
            continue
        text_ok = True
        def bump(k, ok, S=s):
            by[S][k + ("_ok" if ok else "_bad")] += 1
            by["ALL"][k + ("_ok" if ok else "_bad")] += 1
        # sentence & token boundaries
        sa = [[(t[1], t[3], t[4]) for t in x["tokens"]] for x in a["sents"]]
        sb = [[(t[1], t[3], t[4]) for t in x["tokens"]] for x in b["sents"]]
        ok = sa == sb; bump("tokens_and_sentence_split", ok); text_ok &= ok
        ok = [x["text"] for x in a["sents"]] == [x["text"] for x in b["sents"]]; bump("sentence_text", ok); text_ok &= ok
        ok = ([x["tokens"] for x in a["sents"]] == [x["tokens"] for x in b["sents"]]); bump("token_records", ok); text_ok &= ok
        ok = (a["num_tokens"], a["num_words"], a["text"]) == (b["num_tokens"], b["num_words"], b["text"]); bump("doc_counts", ok); text_ok &= ok
        ok = [(x["index"], x["sent_id"], x["deps"], x["tok_sent_ok"]) for x in a["sents"]] == [(x["index"], x["sent_id"], x["deps"], x["tok_sent_ok"]) for x in b["sents"]]
        bump("sent_meta_and_dependencies", ok); text_ok &= ok
        wa = [w for x in a["sents"] for w in x["words"]]
        wb = [w for x in b["sents"] for w in x["words"]]
        if len(wa) != len(wb):
            by[s]["word_count_mismatch"] += 1; by["ALL"]["word_count_mismatch"] += 1
            text_ok = False
        else:
            for x, y in zip(wa, wb):
                for f in WORD_FIELDS:
                    ok = x[f] == y[f]
                    by[s]["w_" + f + ("_ok" if ok else "_bad")] += 1
                    by["ALL"]["w_" + f + ("_ok" if ok else "_bad")] += 1
                    if not ok:
                        text_ok = False
                by[s]["words"] += 1; by["ALL"]["words"] += 1
        if text_ok:
            by[s]["identical"] += 1; by["ALL"]["identical"] += 1
        else:
            diffs.append((i, "diff"))
    print(f"== {mode}: {n} texts; reference {ref_name or ''} vs {ort_name or ''}")
    for s in ["ALL"] + sorted(k for k in by if k != "ALL"):
        c = by[s]
        words = c["words"]
        fields = " ".join(f"{f}={c['w_'+f+'_ok']}/{words}" for f in WORD_FIELDS if words)
        print(f"[{s}] texts={c['texts']} identical={c['identical']} ({100*c['identical']/max(1,c['texts']):.3f}%) words={words} errors_both={c['errors_both']} err_mismatch={c['error_mismatch']} wc_mismatch={c['word_count_mismatch']}")
        print("   ", fields)
        print("    tokens/ssplit %d/%d token_records %d/%d sent_text %d/%d doc_counts %d/%d sent_meta+deps %d/%d" % (
            c["tokens_and_sentence_split_ok"], c["texts"] - c["errors_both"], c["token_records_ok"], c["texts"] - c["errors_both"],
            c["sentence_text_ok"], c["texts"] - c["errors_both"], c["doc_counts_ok"], c["texts"] - c["errors_both"],
            c["sent_meta_and_dependencies_ok"], c["texts"] - c["errors_both"]))
    print("differing texts:", len(diffs))
    for d in diffs[:show]:
        i = d[0]
        print("--- text", i, C["src"][i], repr(C["texts"][i][:200]))
        if d[1] == "error":
            print("   ", d[2], "|", d[3]); continue
        a, b = ref[i], ort[i]
        wa = [(w["text"], w["upos"], w["xpos"], w["feats"], w["lemma"], w["head"], w["deprel"]) for x in a["sents"] for w in x["words"]]
        wb = [(w["text"], w["upos"], w["xpos"], w["feats"], w["lemma"], w["head"], w["deprel"]) for x in b["sents"] for w in x["words"]]
        shown = 0
        for k, (x, y) in enumerate(zip(wa, wb)):
            if x != y and shown < 4:
                print("   word", k, "ref", x, "ort", y); shown += 1
        if len(wa) != len(wb):
            print("   word counts", len(wa), len(wb))
        if wa == wb:
            print("   words equal; other record differs")
    return diffs


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        build_corpus()
    elif cmd in ("ref", "ort"):
        run(cmd, sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else None)
    elif cmd == "compare":
        compare(sys.argv[2], *(sys.argv[3:5]))
