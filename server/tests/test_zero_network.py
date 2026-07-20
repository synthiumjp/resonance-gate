"""The server must never phone home. Patch the socket layer to flag ANY
outbound (non-loopback) connection, then run a full write+recall cycle
(which loads/uses the MiniLM encoder from the local cache). Zero non-loopback
connections are allowed."""

import socket


def _install_guard(monkeypatch):
    attempts = []
    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex
    loopback = ("127.0.0.1", "::1", "localhost", "0.0.0.0")

    def _host(address):
        return address[0] if isinstance(address, tuple) else str(address)

    def guard_connect(self, address):
        h = _host(address)
        attempts.append(h)
        if h not in loopback:
            raise AssertionError(f"outbound connection attempted to {address!r}")
        return orig_connect(self, address)

    def guard_connect_ex(self, address):
        h = _host(address)
        attempts.append(h)
        if h not in loopback:
            raise AssertionError(f"outbound connect_ex to {address!r}")
        return orig_connect_ex(self, address)

    monkeypatch.setattr(socket.socket, "connect", guard_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guard_connect_ex)
    return attempts


def test_no_outbound_connections_on_write_and_recall(tmp_path, monkeypatch):
    from sourcedrecall.service import MemoryService
    attempts = _install_guard(monkeypatch)
    svc = MemoryService(str(tmp_path / "state"))
    # novel strings -> forces the MiniLM encoder to embed (from local cache)
    r = svc.remember("Novelperson Uniquename", "works at", "Distinctorg Systems")
    assert r["stored"] is True
    out = svc.recall("Novelperson Uniquename")
    assert out["resolved"] is True
    # any recorded connect targets must all be loopback
    nonlocal_hits = [a for a in attempts
                     if a not in ("127.0.0.1", "::1", "localhost", "0.0.0.0")]
    assert nonlocal_hits == [], f"non-loopback connections: {nonlocal_hits}"


def test_offline_env_is_set(tmp_path):
    import os
    from sourcedrecall.service import MemoryService  # noqa: F401 (import sets env)
    assert os.environ.get("HF_HUB_OFFLINE") == "1"
    assert os.environ.get("TRANSFORMERS_OFFLINE") == "1"
