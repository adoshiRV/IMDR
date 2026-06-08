"""Tests for Phase 4 embed-side concurrency guards.

* :func:`_sleep_with_jitter` adds 0-30s uniform jitter to the base sleep,
  so concurrent 429 retries from multiple vendors don't synchronise.
* :func:`_get_embed_semaphore` lazy-instantiates a per-loop semaphore
  honoring ``IMDR_RESEARCH_EMBED_CONCURRENCY``.

See docs/admin/development/parallel_vendor_ingest.md Phase 4.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest import embed as _embed_mod  # noqa: E402


def test_sleep_with_jitter_passes_base_plus_random(monkeypatch):
    """``_sleep_with_jitter(65)`` must call asyncio.sleep with 65 + uniform(0,30)."""
    captured_sleeps: list[float] = []

    async def fake_sleep(s):
        captured_sleeps.append(s)

    # Pin random so the expected value is determinable.
    monkeypatch.setattr(_embed_mod.random, "uniform", lambda a, b: 17.5)
    monkeypatch.setattr(_embed_mod.asyncio, "sleep", fake_sleep)

    asyncio.run(_embed_mod._sleep_with_jitter(65.0))
    assert captured_sleeps == [65.0 + 17.5]


def test_sleep_with_jitter_two_calls_spread(monkeypatch):
    """Two back-to-back calls must produce DIFFERENT total sleeps
    (the whole point of jitter — anti-retry-storm)."""
    captured: list[float] = []

    async def fake_sleep(s):
        captured.append(s)

    # Real random.uniform — should yield two distinct values w.h.p.
    monkeypatch.setattr(_embed_mod.asyncio, "sleep", fake_sleep)

    async def _two_calls():
        await _embed_mod._sleep_with_jitter(65.0)
        await _embed_mod._sleep_with_jitter(65.0)

    asyncio.run(_two_calls())
    assert len(captured) == 2
    # Probability of exact equality with uniform(0,30) is ~0; if it
    # ever fails by chance, increase precision or seed control.
    assert captured[0] != captured[1], (
        f"jitter produced identical sleeps {captured} — retry storm risk"
    )
    # Both must be in [65, 95].
    for s in captured:
        assert 65.0 <= s <= 95.0


def test_embed_semaphore_lazy_per_loop():
    """Semaphore is created once per loop and reused."""
    async def _runner():
        sem1 = _embed_mod._get_embed_semaphore()
        sem2 = _embed_mod._get_embed_semaphore()
        assert sem1 is sem2, "semaphore must be reused within the same loop"
        return sem1

    # Fresh loop so the ContextVar starts clean.
    sem = asyncio.run(_runner())
    assert isinstance(sem, asyncio.Semaphore)


def test_prime_in_parent_shares_semaphore_across_gather_tasks(monkeypatch):
    """The production cross-vendor cap pattern.

    Parent task calls prime_embed_semaphore(); gather spawns N child
    tasks, each calls _get_embed_semaphore() and must see the SAME
    instance (otherwise the cross-vendor cap is silently inoperative
    — see review of Phase 4/5/6).
    """
    # Reset ContextVar so the prime call actually creates a fresh sem.
    monkeypatch.setattr(_embed_mod, "_embed_sem_var",
                        type(_embed_mod._embed_sem_var)(
                            "_embed_sem", default=None))

    async def _child():
        return _embed_mod._get_embed_semaphore()

    async def _runner():
        # Parent eagerly primes before gather.
        primed = _embed_mod.prime_embed_semaphore()
        sems = await asyncio.gather(_child(), _child(), _child())
        return primed, sems

    primed, sems = asyncio.run(_runner())
    assert primed is sems[0] is sems[1] is sems[2], (
        f"all children must share the primed semaphore; got distinct "
        f"identities: parent={id(primed)} children={[id(s) for s in sems]}"
    )


def test_unprimed_gather_children_get_distinct_semaphores(monkeypatch):
    """Regression test: WITHOUT priming, each child task creates its own
    semaphore (the bug Phase 4 review caught). This test pins the
    failure mode — if the contextvars semantics ever change in Python
    such that children DO share unprimed state, this test fails loudly
    and we can simplify prime_embed_semaphore.
    """
    monkeypatch.setattr(_embed_mod, "_embed_sem_var",
                        type(_embed_mod._embed_sem_var)(
                            "_embed_sem", default=None))

    async def _child():
        return _embed_mod._get_embed_semaphore()

    async def _runner():
        # NO prime call. Each child must create its own.
        return await asyncio.gather(_child(), _child(), _child())

    sems = asyncio.run(_runner())
    # All three must be distinct objects (proves the bug exists & priming
    # is necessary).
    assert len({id(s) for s in sems}) == 3, (
        "unprimed gather children unexpectedly share a semaphore — "
        "verify whether prime_embed_semaphore is still needed"
    )


def test_embed_semaphore_honors_env_var(monkeypatch):
    monkeypatch.setenv("IMDR_RESEARCH_EMBED_CONCURRENCY", "2")
    # Clear the ContextVar so re-init reads the new env.
    monkeypatch.setattr(_embed_mod, "_embed_sem_var",
                        type(_embed_mod._embed_sem_var)(
                            "_embed_sem", default=None))

    async def _runner():
        sem = _embed_mod._get_embed_semaphore()
        # Probe the cap by acquiring twice (should succeed) and a third
        # time which would block — use a tiny timeout to detect.
        await sem.acquire()
        await sem.acquire()
        try:
            await asyncio.wait_for(sem.acquire(), timeout=0.05)
            return False  # third acquire shouldn't succeed
        except asyncio.TimeoutError:
            return True
        finally:
            sem.release()
            sem.release()

    assert asyncio.run(_runner()) is True


def test_embed_semaphore_falls_back_to_default_on_empty_env(monkeypatch):
    """Empty env var must not crash; default (4) is used."""
    monkeypatch.setenv("IMDR_RESEARCH_EMBED_CONCURRENCY", "")
    monkeypatch.setattr(_embed_mod, "_embed_sem_var",
                        type(_embed_mod._embed_sem_var)(
                            "_embed_sem", default=None))

    async def _runner():
        sem = _embed_mod._get_embed_semaphore()
        # Default = 4: 4 acquires succeed, 5th blocks.
        for _ in range(4):
            await sem.acquire()
        try:
            await asyncio.wait_for(sem.acquire(), timeout=0.05)
            return False
        except asyncio.TimeoutError:
            return True
        finally:
            for _ in range(4):
                sem.release()

    assert asyncio.run(_runner()) is True
