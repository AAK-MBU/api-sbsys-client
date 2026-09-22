# src/sbsys/_transport/redact.py
"""Masking of sensitive values before anything reaches a log.

CPR numbers, bearer tokens and passwords must never be written to a log.
Every log statement in this package passes through :func:`redact`, and
consumers are encouraged to use it for their own logging too.
"""

from __future__ import annotations

import re

_CPR = re.compile(r"\b(\d{6})-?(\d{4})\b")
_BEARER = re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE)
_SECRETISH = re.compile(
    r'("(?:password|client_secret|access_token|refresh_token)"\s*:\s*")[^"]*(")',
    re.IGNORECASE,
)


def redact(text: str) -> str:
    """Replace CPR numbers, bearer tokens and passwords with placeholders.

    The birth-date part of a CPR number is kept and the four significant
    digits are masked, which leaves enough to correlate log lines during
    debugging without the log itself holding an identifier.

    Args:
        text: Arbitrary text, typically a response body or a header value.

    Returns:
        The same text with sensitive values replaced. Safe to log.
    """
    text = _CPR.sub(r"\1-XXXX", text)
    text = _BEARER.sub(r"\1<token>", text)
    return _SECRETISH.sub(r"\1<redacted>\2", text)
