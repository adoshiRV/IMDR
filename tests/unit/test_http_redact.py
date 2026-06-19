from __future__ import annotations

from imdr.connectors.http import _redact_params


class TestRedactParams:
    def test_none_and_empty_pass_through(self) -> None:
        assert _redact_params(None) is None
        assert _redact_params({}) == {}

    def test_dict_masks_sensitive_keys(self) -> None:
        out = _redact_params({"api_key": "secret", "slug": "fed"})
        assert out == {"api_key": "***REDACTED***", "slug": "fed"}

    def test_dict_masking_is_case_insensitive(self) -> None:
        out = _redact_params({"Authorization": "Bearer x"})
        assert out == {"Authorization": "***REDACTED***"}

    def test_list_of_tuples_does_not_raise(self) -> None:
        # Regression: httpx accepts a list of (key, value) tuples for repeated
        # keys (e.g. multiple `slug` params). _redact_params must not assume a
        # dict — previously raised AttributeError("'list' object has no
        # attribute 'items'") and broke every chunked Polymarket /events poll.
        params = [("slug", "fed"), ("slug", "cpi"), ("closed", "false")]
        assert _redact_params(params) == params

    def test_list_of_tuples_masks_sensitive_keys(self) -> None:
        params = [("token", "abc"), ("slug", "fed")]
        assert _redact_params(params) == [("token", "***REDACTED***"), ("slug", "fed")]
