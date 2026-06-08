"""Tests for filelock-guarded LLM classifier cache writes.

Two threads writing different cache keys must both persist —
last-writer-wins on the cache dict is exactly the bug filelock guards
against. See docs/admin/development/parallel_vendor_ingest.md Phase 4.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.classifiers import llm as _llm  # noqa: E402


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    """Redirect the LLM cache path to tmp_path."""
    cache = tmp_path / "llm_classify_cache.json"
    lock = cache.with_suffix(cache.suffix + ".lock")
    monkeypatch.setattr(_llm, "_CACHE_PATH", cache)
    monkeypatch.setattr(_llm, "_CACHE_LOCK_PATH", lock)
    return cache


def test_single_write_persists(isolated_cache):
    _llm._cache_update_locked("k1", {"asset_class": "MACRO"})
    data = json.loads(isolated_cache.read_text(encoding="utf-8"))
    assert data == {"k1": {"asset_class": "MACRO"}}


def test_two_threads_different_keys_both_persist(isolated_cache):
    """Race-recreate the exact failure mode the filelock guards against.

    Two threads write different keys nearly-simultaneously. Without the
    lock, both load_cache() into a fresh dict, both save_cache() with
    only their own key, second wipes first. With the lock, the second
    waits for the first's read-modify-write to complete, then merges.
    """
    barrier = threading.Barrier(2)

    def _worker(key: str, value: dict):
        barrier.wait()
        _llm._cache_update_locked(key, value)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_worker, "alpha", {"asset_class": "MACRO"}),
            pool.submit(_worker, "beta", {"asset_class": "RATES"}),
        ]
        for f in as_completed(futures):
            f.result()

    data = json.loads(isolated_cache.read_text(encoding="utf-8"))
    assert data == {
        "alpha": {"asset_class": "MACRO"},
        "beta": {"asset_class": "RATES"},
    }, f"both keys must persist, got {data}"


def test_eight_threads_eight_keys_all_persist(isolated_cache):
    """Higher contention — 8 threads, 8 distinct keys."""
    barrier = threading.Barrier(8)

    def _worker(i: int):
        barrier.wait()
        _llm._cache_update_locked(f"key_{i:02d}", {"i": i})

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_worker, i) for i in range(8)]
        for f in as_completed(futures):
            f.result()

    data = json.loads(isolated_cache.read_text(encoding="utf-8"))
    assert len(data) == 8, f"expected 8 keys, got {len(data)}: {sorted(data)}"
    for i in range(8):
        assert f"key_{i:02d}" in data
        assert data[f"key_{i:02d}"] == {"i": i}


def test_load_cache_returns_empty_when_file_missing(isolated_cache):
    assert _llm._load_cache() == {}


def test_load_cache_returns_empty_on_corrupt_json(isolated_cache):
    isolated_cache.parent.mkdir(parents=True, exist_ok=True)
    isolated_cache.write_text("not json {", encoding="utf-8")
    assert _llm._load_cache() == {}
