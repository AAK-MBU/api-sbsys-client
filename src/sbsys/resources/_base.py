# src/sbsys/resources/_base.py
"""Shared base class and validation helpers for the resource layer."""

from __future__ import annotations

import re

from sbsys._transport.http import Transport
from sbsys.errors import SbsysValidationError

_CPR_RE = re.compile(r"^(\d{6})-?(\d{4})$")


class Resource:
    """Base class for a resource.

    A resource owns one domain area and does nothing but build requests and
    parse responses. All HTTP concerns belong to the transport.
    """

    def __init__(self, transport: Transport) -> None:
        """Bind the resource to a transport.

        Args:
            transport: The shared transport owned by the client. Resources do
                not own the connection pool and must not close it.
        """
        self._t = transport


def normaliser_cpr(cpr: str) -> str:
    """Validate a CPR number and normalise it to ``DDMMYY-NNNN``.

    SBSYS is inconsistent about the hyphen across endpoints, so normalise once
    here rather than at each call site. This checks the format only; it does
    not verify the modulus-11 check digit or that the person exists.

    Args:
        cpr: A CPR number with or without a hyphen.

    Returns:
        The number with a hyphen between the date and the four final digits.

    Raises:
        SbsysValidationError: If the format is wrong. The message deliberately
            does not include the value, since it is personal data that would
            end up in logs and tracebacks.
    """
    match = _CPR_RE.match(cpr.strip())
    if not match:
        raise SbsysValidationError("Invalid CPR number (expected DDMMYY-NNNN)")
    return f"{match.group(1)}-{match.group(2)}"
