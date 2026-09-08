"""The judge-verdict cache (2026-09-09), tested without a judge.

WHY IT EXISTS. `evaluation.py` checkpoints a user only when that user is
finished, so the reboot at 07:41 on 2026-09-07 discarded six hours of an
accuracy pass that was 88% done. And an extraction VARIANT re-asks the judge
the same question about every record it did not change -- 3,934 of them on
user 0 -- at ~5.5s each.

Both are the same fix: cache the verdict, keyed on (model, call shape, exact
prompt). These tests stub the OpenAI client so they need no GPU, no judge and
no network, and they assert the two properties that matter -- a hit costs no
call, and a hit survives a process restart (a fresh import reads the shard
files off disk).
"""
import importlib
import json
import os
import sys

import pytest

_OFFICIAL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "halumem_official")


class _Msg:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class _Resp:
    def __init__(self, content):
        self.choices = [_Msg(content)]


class _FakeCompletions:
    """Counts calls, so 'was the judge asked?' is a number, not a guess."""

    def __init__(self, content):
        self.content = content
        self.calls = 0

    def create(self, **kw):
        self.calls += 1
        return _Resp(self.content)


def _load(cache_dir, monkeypatch, content='```json\n{"score": 2}\n```',
          model="test-judge", cache="1"):
    """Import llms fresh under a given cache dir, with a stubbed client.

    `model` and `cache` are parameters rather than fixed values because the
    first version of this helper hardcoded both and silently overrode what
    two of the tests below were trying to vary -- they failed against correct
    code. An instrument that overwrites its own independent variable.
    """
    for k, v in (("OPENAI_BASE_URL", "http://127.0.0.1:9/v1"),
                 ("OPENAI_API_KEY", "x"), ("OPENAI_MODEL", model),
                 ("RETRY_TIMES", "1"), ("WAIT_TIME_LOWER", "1"),
                 ("WAIT_TIME_UPPER", "2"), ("RG_JUDGE_CACHE_DIR", str(cache_dir)),
                 ("RG_JUDGE_CACHE", cache), ("RG_NO_THINK", "0"),
                 ("RG_PREFIX_NO_THINK", "0")):
        monkeypatch.setenv(k, v)
    if _OFFICIAL not in sys.path:
        sys.path.insert(0, _OFFICIAL)
    sys.modules.pop("llms", None)
    mod = importlib.import_module("llms")
    fake = _FakeCompletions(content)
    mod.client.chat.completions = fake
    return mod, fake


@pytest.fixture(autouse=True)
def _no_leak():
    """`llms` is imported by the real harness too; do not leave a stub behind."""
    yield
    sys.modules.pop("llms", None)


def test_a_repeated_prompt_costs_no_judge_call(tmp_path, monkeypatch):
    mod, fake = _load(tmp_path, monkeypatch)
    a = mod.llm_request_for_json("score this memory")
    b = mod.llm_request_for_json("score this memory")
    assert a == b == {"score": 2}
    assert fake.calls == 1, "the second ask reached the judge"


def test_a_different_prompt_still_costs_a_call(tmp_path, monkeypatch):
    mod, fake = _load(tmp_path, monkeypatch)
    mod.llm_request_for_json("memory one")
    mod.llm_request_for_json("memory two")
    assert fake.calls == 2


def test_a_verdict_survives_a_process_restart(tmp_path, monkeypatch):
    """The crash-resume property: a fresh import reads the shards off disk."""
    mod, fake = _load(tmp_path, monkeypatch)
    mod.llm_request_for_json("score this memory")
    assert fake.calls == 1

    mod2, fake2 = _load(tmp_path, monkeypatch)      # simulates the re-run
    assert mod2.llm_request_for_json("score this memory") == {"score": 2}
    assert fake2.calls == 0, "a cached verdict was re-asked after a restart"


def test_a_different_model_never_hits(tmp_path, monkeypatch):
    """A verdict belongs to the judge that gave it."""
    mod, _ = _load(tmp_path, monkeypatch)
    mod.llm_request_for_json("score this memory")

    mod2, fake2 = _load(tmp_path, monkeypatch, model="a-different-judge")
    mod2.llm_request_for_json("score this memory")
    assert fake2.calls == 1, "a verdict from another model was reused"


def test_the_plain_string_call_is_cached_too(tmp_path, monkeypatch):
    mod, fake = _load(tmp_path, monkeypatch, content="an answer")
    assert mod.llm_request("a question") == "an answer"
    assert mod.llm_request("a question") == "an answer"
    assert fake.calls == 1


def test_the_two_call_shapes_do_not_share_an_entry(tmp_path, monkeypatch):
    """llm_request returns a str and llm_request_for_json a dict: one prompt
    must not serve both, or a caller gets the wrong type."""
    mod, fake = _load(tmp_path, monkeypatch, content='```json\n{"score": 1}\n```')
    mod.llm_request_for_json("same text")
    out = mod.llm_request("same text")
    assert isinstance(out, str) and fake.calls == 2


def test_the_cache_can_be_switched_off(tmp_path, monkeypatch):
    mod, fake = _load(tmp_path, monkeypatch, cache="0")
    mod.llm_request_for_json("score this memory")
    mod.llm_request_for_json("score this memory")
    assert fake.calls == 2
    assert not list(tmp_path.glob("*.jsonl")), "wrote a shard while disabled"


def test_a_torn_line_is_a_miss_not_a_crash(tmp_path, monkeypatch):
    """A shard written by a process that died mid-line must not break a run."""
    mod, fake = _load(tmp_path, monkeypatch)
    mod.llm_request_for_json("score this memory")
    shard = next(iter(tmp_path.glob("*.jsonl")))
    with open(shard, "a") as fh:
        fh.write('{"k": "abc", "v": {"sco')       # killed mid-write

    mod2, fake2 = _load(tmp_path, monkeypatch)
    assert mod2.llm_request_for_json("score this memory") == {"score": 2}
    assert fake2.calls == 0


def test_the_shard_is_one_json_object_per_line(tmp_path, monkeypatch):
    mod, _ = _load(tmp_path, monkeypatch)
    mod.llm_request_for_json("one")
    mod.llm_request_for_json("two")
    shard = next(iter(tmp_path.glob("*.jsonl")))
    rows = [json.loads(l) for l in open(shard) if l.strip()]
    assert len(rows) == 2 and all(set(r) == {"k", "v"} for r in rows)
