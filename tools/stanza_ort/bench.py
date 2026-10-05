"""Speed: ms per message, one-at-a-time and bulk(64), for stanza_ort (torch-free venv) or Stanza (reference venv).
   python bench.py ort|ref [N=200] [passes=2]"""
import os, sys, json, random, time, resource
HERE = os.path.dirname(os.path.abspath(__file__)); HOME = os.path.expanduser("~")
which = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 200; passes = int(sys.argv[3]) if len(sys.argv) > 3 else 2
d = json.load(open(os.path.join(HOME, "jpwork/locomo10.json"))); texts = []
for c in d:
    for k, v in c["conversation"].items():
        if isinstance(v, list): texts += [t["text"].strip() for t in v if t.get("text")]
random.seed(7); texts = [t for t in texts if len(t) > 3]; random.shuffle(texts); texts = texts[:N]
if which == "ref":
    os.environ.setdefault("STANZA_RESOURCES_DIR", os.path.join(HOME, "jpwork/stanza_resources_114"))
    import torch, stanza
    torch.set_num_threads(int(os.environ.get("THREADS", "4")))
    nlp = stanza.Pipeline("en", dir=os.environ["STANZA_RESOURCES_DIR"], processors="tokenize,pos,lemma,depparse", use_gpu=False,
                          logging_level="ERROR", download_method=stanza.DownloadMethod.REUSE_RESOURCES)
    Doc = stanza.Document
else:
    sys.path.insert(0, HERE)
    import stanza_ort
    nlp = stanza_ort.Pipeline(os.path.join(HERE, os.environ.get("STANZA_ORT_MODELS", "models")), threads=int(os.environ.get("THREADS", "4")))
    Doc = stanza_ort.Document
    assert "torch" not in sys.modules
for t in texts[:8]: nlp(t)
rss = lambda: resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20
print(which, "N", N, "rss after warmup MB", round(rss()), flush=True)
for p in range(passes):
    t0 = time.time(); ns = 0
    for t in texts: ns += len(nlp(t).sentences)
    es = time.time() - t0
    t0 = time.time()
    for i in range(0, len(texts), 64):
        nlp.bulk_process([Doc([], text=t) for t in texts[i:i + 64]])
    eb = time.time() - t0
    print(f"{which} pass {p}: one-at-a-time {1000*es/N:.1f} ms/msg ({ns} sentences, {1000*es/ns:.1f} ms/sent); bulk64 {1000*eb/N:.1f} ms/msg; maxrss MB {rss():.0f}", flush=True)
