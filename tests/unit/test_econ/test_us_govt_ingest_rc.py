"""Exit-code semantics for the US govt filings ingest.

Regression coverage for the rc-masking bug: a stream that fails DISCOVERY
outright (probe break / site redesign) must force rc=1 even when a surviving
stream had an already-ingested item — otherwise a near-total Track-B outage
reads as OK on the unattended scheduler.
"""

from scripts.econ.us.govt.ingest_filings import _compute_rc


class TestComputeRc:
    def test_progress_made_is_ok(self):
        # ingested>0, nothing failed → healthy
        assert _compute_rc(total_ok=10, total_skip=0, total_fail=0, n_discover_failures=0) == 0

    def test_all_skips_is_ok(self):
        # everything already in DB (steady-state daily run) → healthy
        assert _compute_rc(total_ok=0, total_skip=20, total_fail=0, n_discover_failures=0) == 0

    def test_progress_with_known_item_404_is_ok(self):
        # one permanent PDF 404 among progress must NOT flag (it retries next run)
        assert _compute_rc(total_ok=5, total_skip=3, total_fail=1, n_discover_failures=0) == 0

    def test_item_level_total_outage_is_fail(self):
        # failures with zero progress and zero skips → true item outage
        assert _compute_rc(total_ok=0, total_skip=0, total_fail=4, n_discover_failures=0) == 1

    def test_discover_failure_with_healthy_stream_is_fail(self):
        # THE BUG: a probe broke, but another stream had an already-ingested
        # item — must still surface as rc=1, not be masked to OK.
        assert _compute_rc(total_ok=8, total_skip=2, total_fail=0, n_discover_failures=1) == 1

    def test_discover_failure_with_only_skips_is_fail(self):
        assert _compute_rc(total_ok=0, total_skip=5, total_fail=0, n_discover_failures=3) == 1

    def test_nothing_happened_is_ok(self):
        # empty window, no failures → not an outage
        assert _compute_rc(total_ok=0, total_skip=0, total_fail=0, n_discover_failures=0) == 0
