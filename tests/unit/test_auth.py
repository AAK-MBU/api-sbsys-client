# tests/unit/test_auth.py
"""Token handling: caching, refresh, and the retry on a rejected token."""

from __future__ import annotations

import httpx
import pytest
import respx

from sbsys import SbsysAuthError, SbsysClient
from tests.conftest import BASE_URL, TOKEN_URL


@respx.mock
def test_token_hentes_en_gang_og_genbruges(settings):
    """Two requests share one token — the cache actually caches."""
    token = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "abc", "expires_in": 3600})
    )
    respx.get(f"{BASE_URL}/api/sag/1").mock(
        return_value=httpx.Response(200, json={"Id": 1, "SagsTitel": "Test"})
    )
    respx.get(f"{BASE_URL}/api/sag/2").mock(
        return_value=httpx.Response(200, json={"Id": 2, "SagsTitel": "Test"})
    )

    with SbsysClient(settings) as client:
        client.sager.hent(1)
        client.sager.hent(2)

    assert token.call_count == 1


@respx.mock
def test_token_sendes_som_bearer(settings):
    """The token is attached as an Authorization: Bearer header."""
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "abc", "expires_in": 3600})
    )
    route = respx.get(f"{BASE_URL}/api/sag/1").mock(
        return_value=httpx.Response(200, json={"Id": 1})
    )

    with SbsysClient(settings) as client:
        client.sager.hent(1)

    assert route.calls.last.request.headers["Authorization"] == "Bearer abc"


@respx.mock
def test_401_udloeser_fornyelse_og_gentagelse(settings):
    """A rejected token is refreshed once and the request replayed with the new one."""
    respx.post(TOKEN_URL).mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "gammel", "expires_in": 3600}),
            httpx.Response(200, json={"access_token": "ny", "expires_in": 3600}),
        ]
    )
    route = respx.get(f"{BASE_URL}/api/sag/1").mock(
        side_effect=[
            httpx.Response(401, json={"error": "expired"}),
            httpx.Response(200, json={"Id": 1, "SagsTitel": "Test"}),
        ]
    )

    with SbsysClient(settings) as client:
        sag = client.sager.hent(1)

    assert sag.id == 1
    assert route.call_count == 2
    assert route.calls[-1].request.headers["Authorization"] == "Bearer ny"


@respx.mock
def test_fejlende_token_giver_authfejl(settings):
    """A failing token endpoint surfaces as SbsysAuthError, not as an httpx error."""
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(400, text="invalid_grant"))

    with SbsysClient(settings) as client, pytest.raises(SbsysAuthError):
        client.sager.hent(1)
