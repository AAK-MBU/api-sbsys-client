# src/sbsys/testing/__init__.py
"""Helpers for testing code that uses this client.

Shipped with the package on purpose: consuming projects should not each invent
their own way of mocking it. Import only from tests — nothing here is part of
the production path.
"""

from sbsys.testing.fake import FakeSbsysClient

__all__ = ["FakeSbsysClient"]
