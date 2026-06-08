"""Unit tests for the research-auth email dispatcher.

All paths are mocked — no real Outlook COM call. The tests cover:

* the email_enabled / recipient gates
* email_anomaly_to → email_to fallback
* unknown-kind handling
* render failure handling (never raises)
* dry-run prints without sending
* importance flag on critical kinds
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from imdr.research.auth import notify as notify_mod


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _stub_settings(
    *,
    email_enabled: bool = True,
    email_to: str = "ops@example.com",
    email_anomaly_to: str = "",
):
    return SimpleNamespace(
        email_enabled=email_enabled,
        email_to=email_to,
        email_anomaly_to=email_anomaly_to,
    )


def _stub_get_settings(settings) -> "patch":
    return patch(
        "imdr.config.settings.get_settings",
        return_value=settings,
    )


def _stub_send_outlook(return_value: bool = True):
    """Patch the send_outlook_email symbol at its source."""
    return patch(
        "imdr.notifications.email.send_outlook_email",
        return_value=return_value,
    )


def _stub_send_outlook_raises(exc: Exception):
    return patch(
        "imdr.notifications.email.send_outlook_email",
        side_effect=exc,
    )


def _stub_formatters() -> "patch":
    """Replace the formatter dispatch dict with no-Jinja stubs."""

    def fake_factory():
        def subj_validate(**kw):
            return f"[stub] validate {kw.get('n_pass', 0)}/{kw.get('n_total', 0)}"

        def body_validate(**_kw):
            return "<html>validate body</html>"

        def subj_login(**kw):
            return f"[stub] login failed {kw.get('vendor', '?')}"

        def body_login(**_kw):
            return "<html>login failed body</html>"

        def subj_human(**kw):
            return f"[stub] needs human n={len(kw.get('outcomes') or [])}"

        def body_human(**_kw):
            return "<html>needs human body</html>"

        return {
            "validate_summary": (subj_validate, body_validate),
            "login_failed": (subj_login, body_login),
            "needs_human": (subj_human, body_human),
        }

    return patch.object(notify_mod, "_formatters", new=fake_factory)


# ---------------------------------------------------------------------
# Gate: email_enabled
# ---------------------------------------------------------------------

def test_returns_false_when_email_disabled():
    s = _stub_settings(email_enabled=False)
    with _stub_get_settings(s), _stub_send_outlook() as send:
        ok = notify_mod.send_auth_email(kind="validate_summary")
    assert ok is False
    send.assert_not_called()


# ---------------------------------------------------------------------
# Gate: recipient
# ---------------------------------------------------------------------

def test_returns_false_when_no_recipient():
    s = _stub_settings(email_to="", email_anomaly_to="")
    with _stub_get_settings(s), _stub_send_outlook() as send:
        ok = notify_mod.send_auth_email(kind="validate_summary")
    assert ok is False
    send.assert_not_called()


def test_prefers_anomaly_recipient():
    """email_anomaly_to wins over email_to when both are set."""
    s = _stub_settings(
        email_to="ops@example.com",
        email_anomaly_to="alerts@example.com",
    )
    with _stub_get_settings(s), _stub_formatters(), _stub_send_outlook() as send:
        ok = notify_mod.send_auth_email(kind="validate_summary", n_pass=0, n_total=0)
    assert ok is True
    send.assert_called_once()
    kwargs = send.call_args.kwargs
    assert kwargs["to"] == "alerts@example.com"


def test_falls_back_to_email_to_when_anomaly_empty():
    s = _stub_settings(
        email_to="ops@example.com",
        email_anomaly_to="",
    )
    with _stub_get_settings(s), _stub_formatters(), _stub_send_outlook() as send:
        ok = notify_mod.send_auth_email(kind="validate_summary", n_pass=0, n_total=0)
    assert ok is True
    assert send.call_args.kwargs["to"] == "ops@example.com"


# ---------------------------------------------------------------------
# Dispatch by kind
# ---------------------------------------------------------------------

def test_unknown_kind_returns_false():
    s = _stub_settings()
    with _stub_get_settings(s), _stub_send_outlook() as send:
        ok = notify_mod.send_auth_email(kind="does_not_exist")
    assert ok is False
    send.assert_not_called()


def test_dispatches_login_failed_to_correct_formatter():
    s = _stub_settings()
    with _stub_get_settings(s), _stub_formatters(), _stub_send_outlook() as send:
        ok = notify_mod.send_auth_email(
            kind="login_failed", vendor="ubs", error_type="LoginFailedError",
        )
    assert ok is True
    assert "ubs" in send.call_args.kwargs["subject"]


def test_dispatches_needs_human_to_correct_formatter():
    s = _stub_settings()
    outcomes = [{"vendor": "bnp", "mode": "profile_only",
                 "healthcheck_url": "x", "detail": "y"}]
    with _stub_get_settings(s), _stub_formatters(), _stub_send_outlook() as send:
        ok = notify_mod.send_auth_email(kind="needs_human", outcomes=outcomes)
    assert ok is True
    assert "needs human n=1" in send.call_args.kwargs["subject"]


# ---------------------------------------------------------------------
# Robustness: never raises
# ---------------------------------------------------------------------

def test_swallows_send_outlook_failure():
    s = _stub_settings()
    with _stub_get_settings(s), _stub_formatters(), \
         _stub_send_outlook_raises(RuntimeError("Outlook not running")):
        ok = notify_mod.send_auth_email(kind="validate_summary", n_pass=0, n_total=0)
    assert ok is False  # but no exception leaked


def test_returns_false_when_settings_unavailable():
    """If get_settings itself raises, we degrade gracefully."""
    with patch(
        "imdr.config.settings.get_settings",
        side_effect=RuntimeError("env malformed"),
    ), _stub_send_outlook() as send:
        ok = notify_mod.send_auth_email(kind="validate_summary")
    assert ok is False
    send.assert_not_called()


def test_returns_false_when_formatter_render_raises():
    """A broken formatter doesn't propagate — auth flows keep working."""
    s = _stub_settings()

    def bad_factory():
        def boom_subj(**_kw):
            raise ValueError("bad context")

        def boom_body(**_kw):
            raise ValueError("bad context")
        return {"validate_summary": (boom_subj, boom_body)}

    with _stub_get_settings(s), \
         patch.object(notify_mod, "_formatters", new=bad_factory), \
         _stub_send_outlook() as send:
        ok = notify_mod.send_auth_email(kind="validate_summary")
    assert ok is False
    send.assert_not_called()


# ---------------------------------------------------------------------
# dry_run
# ---------------------------------------------------------------------

def test_dry_run_returns_true_without_sending(capsys):
    s = _stub_settings()
    with _stub_get_settings(s), _stub_formatters(), _stub_send_outlook() as send:
        ok = notify_mod.send_auth_email(
            kind="validate_summary", dry_run=True, n_pass=0, n_total=0,
        )
    assert ok is True
    send.assert_not_called()
    out = capsys.readouterr().out
    assert "dry-run" in out.lower()
    assert "validate body" in out


def test_dry_run_works_when_email_disabled():
    """dry_run bypasses the email_enabled gate so operators can preview
    the HTML even on a machine without email configured."""
    s = _stub_settings(email_enabled=False)
    with _stub_get_settings(s), _stub_formatters(), _stub_send_outlook() as send:
        ok = notify_mod.send_auth_email(
            kind="validate_summary", dry_run=True, n_pass=0, n_total=0,
        )
    assert ok is True
    send.assert_not_called()


# ---------------------------------------------------------------------
# Importance flag — critical kinds get high importance
# ---------------------------------------------------------------------

def test_login_failed_uses_high_importance():
    s = _stub_settings()
    with _stub_get_settings(s), _stub_formatters(), _stub_send_outlook() as send:
        notify_mod.send_auth_email(kind="login_failed", vendor="ubs")
    assert send.call_args.kwargs["importance"] == 2


def test_needs_human_uses_high_importance():
    s = _stub_settings()
    with _stub_get_settings(s), _stub_formatters(), _stub_send_outlook() as send:
        notify_mod.send_auth_email(kind="needs_human", outcomes=[])
    assert send.call_args.kwargs["importance"] == 2


def test_validate_summary_uses_normal_importance():
    s = _stub_settings()
    with _stub_get_settings(s), _stub_formatters(), _stub_send_outlook() as send:
        notify_mod.send_auth_email(kind="validate_summary", n_pass=0, n_total=0)
    assert send.call_args.kwargs["importance"] == 1
