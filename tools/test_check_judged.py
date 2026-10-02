"""tools/check_judged.py: a dead judge must not produce a passing row."""
import json
import os
import time

import check_judged as CJ


def _row(tmp_path, version, n=100, none=0, stale=False):
    d = tmp_path / f"rgp2-{version}"
    d.mkdir()
    src = d / "rgp2_eval_results.jsonl"
    stat = d / "rgp2_eval_stat_result.json"
    rows = ([{"memory_integrity_score": None}] * none
            + [{"memory_integrity_score": 2}] * (n - none))
    if stale:
        stat.write_text(json.dumps({"memory_integrity_records": rows}))
        time.sleep(0.02)
        src.write_text("{}\n")
    else:
        src.write_text("{}\n")
        time.sleep(0.02)
        stat.write_text(json.dumps({"memory_integrity_records": rows}))
    return str(tmp_path)


def test_a_healthy_row_passes(tmp_path):
    assert CJ.check("v", results=_row(tmp_path, "v", none=1)) == []


def test_a_row_of_none_scores_fails(tmp_path):
    """evaluation.py records None for every judge exception and aggregates."""
    out = CJ.check("v", results=_row(tmp_path, "v", none=40))
    assert out and "the judge failed" in out[0]


def test_a_stat_file_older_than_its_input_fails(tmp_path):
    """A tmp2 checkpoint re-aggregated after a re-compose is a stale result."""
    out = CJ.check("v", results=_row(tmp_path, "v", stale=True))
    assert any("OLDER" in p for p in out)


def test_a_missing_stat_file_fails(tmp_path):
    (tmp_path / "rgp2-v").mkdir()
    assert CJ.check("v", results=str(tmp_path))
