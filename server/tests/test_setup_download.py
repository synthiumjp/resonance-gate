"""Review 2026-10-12 (4.2) and the launch review: the model download shows
progress and a broken one resumes where it stopped."""
import hashlib
import http.server
import io
import os
import tarfile
import threading

import pytest


@pytest.fixture
def install_archive(monkeypatch):
    """setup_models turns network access on at import; keep that out of the
    rest of the test run (as test_setup_notes does)."""
    for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        monkeypatch.setenv(k, os.environ.get(k, "1"))
    from sourcedrecall.setup_models import install_archive
    return install_archive


def _archive():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for name, data in (("m/config.json", b"{}"), ("m/weights.bin", os.urandom(300_000))):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _server(blob, seen):
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            rng = self.headers.get("Range")
            seen.append(rng)
            start = int(rng.split("=")[1].split("-")[0]) if rng else 0
            body = blob[start:]
            self.send_response(206 if rng else 200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    httpd = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def test_a_broken_download_resumes_and_installs(tmp_path, capsys, install_archive):
    blob = _archive()
    seen = []
    httpd = _server(blob, seen)
    dest = str(tmp_path / "parser-models")
    (tmp_path / "parser-models.download").write_bytes(blob[:len(blob) // 2])
    url = f"http://127.0.0.1:{httpd.server_address[1]}/a.tar.gz"
    out = install_archive(url, hashlib.sha256(blob).hexdigest(), dest, "config.json", "parser")
    httpd.shutdown()
    assert os.path.exists(os.path.join(out, "config.json"))
    assert seen == [f"bytes={len(blob) // 2}-"]          # only the rest was fetched
    assert not (tmp_path / "parser-models.download").exists()
    assert "resuming parser download" in capsys.readouterr().out


def test_a_corrupt_partial_is_not_kept(tmp_path, install_archive):
    blob = _archive()
    httpd = _server(blob, [])
    dest = str(tmp_path / "parser-models")
    (tmp_path / "parser-models.download").write_bytes(b"x" * 1000)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/a.tar.gz"
    with pytest.raises(RuntimeError, match="sha256"):
        install_archive(url, hashlib.sha256(blob).hexdigest(), dest, "config.json", "parser")
    httpd.shutdown()
    assert not (tmp_path / "parser-models.download").exists()
