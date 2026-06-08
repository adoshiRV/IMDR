"""Console-encoding helpers for the research ingest scripts.

Why this module exists
----------------------
On Windows, when a Python script's stdout is piped (e.g. into
``Tee-Object`` for logging), Python defaults stdout's text encoding to
the user's ANSI code page — typically **cp1252**. Any ``print()`` of a
character outside that table (e.g. ``→`` U+2192, ``ô``/``Ö`` from
mojibake'd vendor titles, em-dashes, smart quotes) then raises
``UnicodeEncodeError``, which inside an ``asyncio`` orchestrator
aborts the whole event loop — silently killing every vendor that
hadn't run yet.

This module exposes one function, ``force_utf8_stdout()``, that every
long-running research script calls once at startup. It reconfigures
stdout/stderr to UTF-8 with ``errors="replace"`` so a truly
un-encodable byte degrades to ``?`` rather than crashing the run.
"""
from __future__ import annotations

import sys


def force_utf8_stdout() -> None:
    """Reconfigure ``sys.stdout`` / ``sys.stderr`` to UTF-8.

    Idempotent — safe to call multiple times, safe to call after the
    user has set ``PYTHONIOENCODING=utf-8`` in their environment.

    Uses ``errors="replace"`` so a future encoding edge case never
    crashes the script; the operator just sees ``?`` for the offending
    char in the log.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            # line_buffering=True is critical for parallel-vendor mode:
            # without it, stdout is block-buffered when piped (e.g. via
            # Tee-Object), so prints from one vendor pile up in the
            # buffer while another vendor's prints stream through, and
            # the operator sees scrambled order. Line buffering flushes
            # on every '\n', giving deterministic per-line interleave.
            stream.reconfigure(
                encoding="utf-8", errors="replace", line_buffering=True,
            )
        except (AttributeError, ValueError):
            # AttributeError: stream isn't a TextIOWrapper (e.g. a
            # pytest capture wrapper, or stdout already wrapped).
            # ValueError: stream already closed.
            # Either way nothing to do — best-effort.
            pass


__all__ = ["force_utf8_stdout"]
