"""Security and privacy fixes from the adversarial review of 2026-10-09
(docs/REVIEW_2026-10-09.md, section B)."""
import http.client
import json
import os
import socket
import stat

import pytest

from sourcedrecall.secrets import scrub, MARK


# ---- secrets: env-style names, truncated key blocks; counts kept ----------

@pytest.mark.parametrize("text", [
    "DB_PASSWORD=hunter2", "DATABASE_PASSWORD: s3cretvalue", "MYSQL_ROOT_PASSWORD=rootpw",
    "STRIPE_SECRET_KEY=abcdef0123", "client_secret = 'Zx9Qw8Er7'",
    "OPENAI_API_KEY=abcdefABCDEF123456", "SECRET=hunter22", "MY_TOKEN=839201",
    "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\nabcdef",
])
def test_secrets_in_config_form_are_removed(text):
    assert MARK in scrub(text) and "hunter" not in scrub(text)


@pytest.mark.parametrize("text", ["max_tokens: 512", "tokens: 512 max", "token_count = 30000",
                                  "I keep a secret diary.", "The password manager is great."])
def test_ordinary_text_is_kept(text):
    assert scrub(text) == text


# ---- titles are scrubbed ---------------------------------------------------

def test_a_conversation_title_is_scrubbed(tmp_path, monkeypatch):
    monkeypatch.setenv("RG_MEMORY_DIR", str(tmp_path))
    monkeypatch.setenv("RG_NLI", "0")
    import sourcedrecall.profile_memory as pm
    pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                      "uncached_turns": None, "transcripts": None})
    pm.profile_ingest([{"role": "user", "content": "I moved to Leeds."}],
                      conversation_id="a", title="AWS key is AKIAIOSFODNN7EXAMPLE ok",
                      owner_name="Dana Cole", date="2026-03-02")
    raw = open(os.path.join(tmp_path, "conversations.json")).read()
    assert "AKIAIOSFODNN7EXAMPLE" not in raw


# ---- private folders and files ---------------------------------------------

def test_the_memory_folder_is_private(tmp_path, monkeypatch):
    from sourcedrecall import paths
    d = tmp_path / "state"
    d.mkdir(mode=0o755)
    os.chmod(d, 0o755)
    monkeypatch.setenv("SOURCEDRECALL_STATE", str(d))
    monkeypatch.delenv("RG_MEMORY_DIR", raising=False)
    mem = paths.default_memory_dir()
    for p in (d, mem):
        assert stat.S_IMODE(os.stat(p).st_mode) & 0o077 == 0


def test_the_cursor_spool_is_scrubbed_and_private(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCEDRECALL_STATE", str(tmp_path))
    from sourcedrecall import cursor_hooks as C
    C._append("conv1", "user", "my DB_PASSWORD=hunter2 and I live in Leeds")
    p = C.spool_path("conv1")
    assert "hunter2" not in open(p).read()
    assert stat.S_IMODE(os.stat(p).st_mode) & 0o077 == 0


def test_offline_mode_is_set_by_the_entry_points():
    import importlib
    os.environ.pop("SOURCEDRECALL_SETUP", None)
    import sourcedrecall.paths as P
    importlib.reload(P)
    assert os.environ["HF_HUB_OFFLINE"] == "1"


# ---- the memory browser ----------------------------------------------------

def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _get(port, path, host=None, cookie=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Host": host or f"127.0.0.1:{port}"}
    if cookie:
        headers["Cookie"] = cookie
    c.request("GET", path, headers=headers)
    r = c.getresponse()
    body = r.read().decode("utf-8", "replace")
    return r.status, dict(r.getheaders()), body


def test_the_browser_needs_its_key_and_a_loopback_host(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCEDRECALL_STATE", str(tmp_path))
    monkeypatch.setenv("RG_MEMORY_DIR", str(tmp_path / "mem"))
    os.makedirs(tmp_path / "mem", exist_ok=True)
    from sourcedrecall import browser
    port = _free_port()
    httpd = browser.start_browser(None, port)
    try:
        url = open(browser.url_file()).read().strip()
        token = url.split("t=", 1)[1]
        assert _get(port, "/")[0] == 403                                   # no key
        assert _get(port, f"/?t={token}", host="attacker.example")[0] == 403  # rebinding
        status, headers, _ = _get(port, f"/?t={token}")
        assert status == 303 and "sdr=" in headers.get("Set-Cookie", "")
        cookie = headers["Set-Cookie"].split(";")[0]
        status, headers, _ = _get(port, "/", cookie=cookie)
        assert status == 200
        assert "default-src 'none'" in headers["Content-Security-Policy"]
        assert headers["X-Frame-Options"] == "DENY"
        assert _get(port, "/", host="attacker.example", cookie=cookie)[0] == 403
    finally:
        httpd.shutdown()


# ---- several processes writing at once ------------------------------------

_WRITER = r'''
import os, sys
sys.path.insert(0, sys.argv[2])
import sourcedrecall.profile_memory as pm
class _Stub:
    _world = {}
    def extract_turn(self, *a, **k): return []
    def prefetch(self, *a, **k): pass
pm._get_extractor = lambda owner: _Stub()
for i in range(5):
    pm.profile_ingest([{"role": "user", "content": f"message {sys.argv[1]}-{i} about Leeds"}],
                      conversation_id=f"c{sys.argv[1]}-{i}", owner_name="Dana Cole",
                      date="2026-03-02")
'''


def test_processes_writing_at_once_lose_nothing(tmp_path):
    import subprocess
    import sys
    script = tmp_path / "w.py"
    script.write_text(_WRITER)
    server = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, RG_MEMORY_DIR=str(tmp_path / "mem"), RG_NLI="0",
               SOURCEDRECALL_NOTES="off")
    procs = [subprocess.Popen([sys.executable, str(script), str(n), server], env=env)
             for n in range(4)]
    assert all(p.wait(timeout=600) == 0 for p in procs)
    convs = json.load(open(tmp_path / "mem" / "conversations.json"))
    assert len(convs) == 20


# ---- forget erases, and stays forgotten ------------------------------------

@pytest.fixture
def pmem(tmp_path, monkeypatch):
    monkeypatch.setenv("RG_MEMORY_DIR", str(tmp_path))
    monkeypatch.setenv("RG_NLI", "0")
    monkeypatch.setenv("SOURCEDRECALL_NOTES_MODELS", str(tmp_path / "no-notes-model"))
    import sourcedrecall.profile_memory as pm
    pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                      "uncached_turns": None, "transcripts": None})
    return pm


def _all_files_text(d):
    out = ""
    for root, _dirs, files in os.walk(d):
        for f in files:
            if f.endswith((".json", ".jsonl", ".md")):
                out += open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
    return out


def test_forget_erases_the_sentence_everywhere_and_it_stays_forgotten(pmem, tmp_path, monkeypatch):
    pm = pmem
    from sourcedrecall import notes as N
    monkeypatch.setenv("SOURCEDRECALL_NOTES_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("SOURCEDRECALL_NOTES_MODEL", "fake")
    monkeypatch.setattr(N, "_call", lambda prompt, timeout=600: "\n".join(
        l for l in ("Dana Cole lives in Fitzroy.", "Dana Cole works at Acme.")
        if l.split()[-1].rstrip(".") in prompt))
    turns = [{"role": "user", "content": "I live in Fitzroy and my dog is called Biscuit. "
                                         "I work at Acme."}]
    pm.profile_ingest(turns, conversation_id="a", owner_name="Dana Cole", date="2026-03-02")
    hit = next(f for f in pm.profile_recall("Where do I live?")["ranked"]
               if "Fitzroy" in (f.get("said") or ""))
    pm.profile_forget(hit["id"])
    assert "Fitzroy" not in _all_files_text(tmp_path)
    assert "Fitzroy" not in pm.profile_context("Where do I live?")["block"]
    assert "Acme" in pm.profile_context("Where do I work?")["block"]
    # a resumed session re-sends the whole transcript
    pm.profile_ingest(turns + [{"role": "assistant", "content": "Noted."},
                               {"role": "user", "content": "I also like hiking."}],
                      conversation_id="a", owner_name="Dana Cole", date="2026-03-02")
    assert "Fitzroy" not in _all_files_text(tmp_path)
    assert not any("Fitzroy" in n["text"] for n in pm._load_notes())
