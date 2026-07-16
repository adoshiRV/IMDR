"""Unit tests for the shared dual-track daily runner plumbing.

Only ``run_pipelines`` is unit-tested here (it drives real subprocesses with
no DB); ``filings_snapshot`` / ``track_a_snapshot`` are thin DB wrappers
exercised end-to-end by the orchestrators.
"""

from __future__ import annotations

import sys

from scripts.econ._daily_snapshots import run_pipelines


class TestRunPipelines:
    def test_success_and_failure_rc_and_names(self) -> None:
        out = run_pipelines(
            [
                [sys.executable, "-m", "this_module_does_not_exist_xyz"],  # rc != 0
                [sys.executable, "-c", "print('ok')"],                     # rc 0
            ]
        )
        results = out["results"]
        assert len(results) == 2
        # name = the token after `-m`, else the last arg.
        assert results[0]["name"] == "this_module_does_not_exist_xyz"
        assert results[0]["rc"] != 0
        assert results[1]["name"] == "print('ok')"
        assert results[1]["rc"] == 0
        assert out["failed"] == ["this_module_does_not_exist_xyz"]

    def test_timing_and_timestamps_present(self) -> None:
        out = run_pipelines([[sys.executable, "-c", "pass"]])
        assert out["duration_s"] >= 0
        assert out["completed_at"] >= out["started_at"]
        assert out["failed"] == []

    def test_empty_pipeline_list(self) -> None:
        out = run_pipelines([])
        assert out["results"] == []
        assert out["failed"] == []
