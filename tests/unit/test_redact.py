# tests/unit/test_redact.py
"""CPR numbers, tokens and passwords must never reach a log."""

from __future__ import annotations

from sbsys._transport.redact import redact


def test_cpr_maskeres():
    """CPR numbers are masked, with or without a hyphen."""
    assert redact("Borger 010101-1234 fejlede") == "Borger 010101-XXXX fejlede"
    assert redact("cpr=0101011234") == "cpr=010101-XXXX"


def test_token_maskeres():
    """Bearer tokens are replaced with a placeholder."""
    assert redact("Authorization: Bearer eyJhbGci.abc-1") == "Authorization: Bearer <token>"


def test_kodeord_maskeres():
    """Passwords and client secrets are redacted in JSON bodies."""
    assert '"password": "<redacted>"' in redact('{"password": "hemmeligt"}')
    assert '"client_secret": "<redacted>"' in redact('{"client_secret": "abc123"}')
