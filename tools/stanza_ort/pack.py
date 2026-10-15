"""Pack converted parser models into the archive sourcedrecall-setup installs
(2026-10-15), with a NOTICE, in a fixed order with fixed times and owners so the
same models give the same bytes (and sha256).

    python pack.py MODELS_DIR OUT.tar.gz
"""
import gzip
import hashlib
import io
import os
import sys
import tarfile

NOTICE = """sourcedrecall English parser models (UD English-EWT)

Part-of-speech tagger and dependency parser: trained for sourcedrecall on UD
English-EWT v2.18 (CC BY-SA 4.0, https://github.com/UniversalDependencies/UD_English-EWT)
with the GloVe vectors Stanza packages for English (Open Data Commons Public Domain
Dedication and License, https://nlp.stanford.edu/projects/glove/), with Stanza 1.14.0's
training code. Tokenizer, multi-word token and lemma models: Stanza's English EWT models
(Stanford NLP Group, Apache-2.0), trained on UD English-EWT.

These model weights are released under CC BY-SA 4.0
(https://creativecommons.org/licenses/by-sa/4.0/). The conversion to ONNX and the
runtime that loads them (stanza_ort) are Apache-2.0, in
https://github.com/synthiumjp/sourcedrecall.
"""


def main(src, out):
    top = os.path.basename(out).split(".tar")[0]
    files = sorted(f for f in os.listdir(src) if not f.startswith("."))
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as t:
        def add(name, data):
            ti = tarfile.TarInfo(f"{top}/{name}")
            ti.size, ti.mtime, ti.mode = len(data), 0, 0o644
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = ""
            t.addfile(ti, io.BytesIO(data))
        d = tarfile.TarInfo(top)
        d.type, d.mode, d.mtime = tarfile.DIRTYPE, 0o755, 0
        t.addfile(d)
        for f in files:
            add(f, open(os.path.join(src, f), "rb").read())
        add("NOTICE", NOTICE.encode())
    with open(out, "wb") as f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=f, mtime=0) as g:
            g.write(buf.getvalue())
    h = hashlib.sha256(open(out, "rb").read()).hexdigest()
    print(out, os.path.getsize(out), "bytes, sha256", h)


if __name__ == "__main__":
    main(*sys.argv[1:3])
