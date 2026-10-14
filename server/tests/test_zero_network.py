"""The server must never phone home. Patch the socket layer to flag ANY
outbound (non-loopback) connection, then store a conversation and answer
questions from it through the profile tools (parser, retrieval models and
conflict checker, all from the local cache). Zero non-loopback connections
are allowed.

2026-10-14: this used to exercise the rg-1.1 triple tools only, which no
user had by default; it now runs the path every user takes."""

import os
import socket

import pytest

LOOPBACK = ("127.0.0.1", "::1", "localhost", "0.0.0.0")


def _install_guard(monkeypatch):
    attempts = []
    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex

    def _host(address):
        return address[0] if isinstance(address, tuple) else str(address)

    def guard_connect(self, address):
        h = _host(address)
        attempts.append(h)
        if h not in LOOPBACK:
            raise AssertionError(f"outbound connection attempted to {address!r}")
        return orig_connect(self, address)

    def guard_connect_ex(self, address):
        h = _host(address)
        attempts.append(h)
        if h not in LOOPBACK:
            raise AssertionError(f"outbound connect_ex to {address!r}")
        return orig_connect_ex(self, address)

    monkeypatch.setattr(socket.socket, "connect", guard_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guard_connect_ex)
    return attempts


@pytest.fixture
def pm(tmp_path, monkeypatch):
    monkeypatch.setenv("RG_MEMORY_DIR", str(tmp_path))
    monkeypatch.delenv("SOURCEDRECALL_OWNER", raising=False)
    import sourcedrecall.profile_memory as mod

    def _reset():
        mod._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                           "uncached_turns": None, "transcripts": None})
        mod._ingest_state.update({"extractor": None, "owner": None})

    _reset()
    yield mod
    _reset()


def test_no_outbound_connections_on_store_and_answer(pm, monkeypatch):
    pytest.importorskip("onnxruntime")
    attempts = _install_guard(monkeypatch)
    turns = [{"role": "user", "content": "I work as a nurse at St Vincent's and I live in Fitzroy."},
             {"role": "assistant", "content": "Got it."},
             {"role": "user", "content": "Big news, I moved to Brunswick last weekend."}]
    try:
        res = pm.profile_ingest(turns, conversation_id="c1", owner_name="Dana Cole",
                                date="2026-10-02")
    except (ImportError, RuntimeError, FileNotFoundError) as e:   # no parser installed here
        pytest.skip(f"parser not available: {e}")
    assert res["facts"] >= 2 and res["model_calls"] == 0
    block = pm.profile_context("Where do I live?")["block"]
    assert "Brunswick" in block
    pm.profile_recall("Where does Dana work?")
    pm.profile_conflicts()
    nonlocal_hits = [a for a in attempts if a not in LOOPBACK]
    assert nonlocal_hits == [], f"non-loopback connections: {nonlocal_hits}"


def test_offline_env_is_set():
    import sourcedrecall.paths  # noqa: F401 (import sets the env)
    assert os.environ.get("HF_HUB_OFFLINE") == "1"
    assert os.environ.get("TRANSFORMERS_OFFLINE") == "1"
