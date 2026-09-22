# tests/conftest.py
"""Shared fixtures for the unit test suite.

Every test runs against ``respx`` mocks, so the suite needs no credentials and
runs in CI. Integration tests have their own conftest.
"""

from __future__ import annotations

import httpx
import pytest

from sbsys import SbsysClient, SbsysSettings

BASE_URL = "https://sbsys.test.local"
"""Base URL every mocked route is registered against."""

TOKEN_URL = "https://auth.test.local/token"
"""Token endpoint every mocked auth flow is registered against."""


@pytest.fixture
def settings() -> SbsysSettings:
    """Settings pointing at the mocked hosts.

    ``max_retries`` is lowered to 2 so retry behaviour can be asserted without
    the suite spending seconds in backoff.

    Returns:
        Settings for a client under test.
    """
    return SbsysSettings(
        base_url=BASE_URL,
        token_url=TOKEN_URL,
        client_id="test-client",
        client_secret="test-secret",
        username="test-user",
        password="test-password",
        max_retries=2,
    )


@pytest.fixture
def token_route(respx_mock):
    """Mock the token endpoint so authentication always succeeds.

    Returns:
        The mocked route, so a test can assert how often a token was fetched.
    """
    return respx_mock.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "token-1", "expires_in": 3600})
    )


@pytest.fixture
def client(settings, token_route):
    """A client wired to the mocked hosts, closed after the test.

    Yields:
        A ready :class:`~sbsys.SbsysClient`.
    """
    with SbsysClient(settings) as c:
        yield c
