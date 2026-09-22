# tests/integration/conftest.py
"""Fixtures for the integration suite, which talks to a real SBSYS environment."""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from sbsys import SbsysClient

load_dotenv()

PAAKRAEVEDE = [
    "SBSYS_BASE_URL",
    "SBSYS_TOKEN_URL",
    "SBSYS_CLIENT_ID",
    "SBSYS_CLIENT_SECRET",
    "SBSYS_USERNAME",
    "SBSYS_PASSWORD",
]


@pytest.fixture(scope="session")
def live_client():
    """A client against a real SBSYS environment, shared by the whole session.

    Skips every integration test when credentials are absent, so the suite is
    safe to run on a laptop without a .env file.

    Yields:
        A ready :class:`~sbsys.SbsysClient`.
    """
    manglende = [k for k in PAAKRAEVEDE if not os.environ.get(k)]
    if manglende:
        pytest.skip(f"Mangler miljøvariable: {', '.join(manglende)}")
    with SbsysClient.from_env() as client:
        yield client
