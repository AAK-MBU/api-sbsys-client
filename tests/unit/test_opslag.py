# tests/unit/test_opslag.py
"""The lookup resource: paths and response shapes."""

from __future__ import annotations

import httpx

from tests.conftest import BASE_URL


def test_sagsskabeloner_bruger_verificeret_sti(respx_mock, client):
    """Templates are listed from /api/sagsskabelon, as the instance documents it."""
    respx_mock.get(f"{BASE_URL}/api/sagsskabelon").mock(
        return_value=httpx.Response(200, json=[{"Id": 332, "Navn": "Underretning"}])
    )

    assert client.opslag.sagsskabeloner() == [{"Id": 332, "Navn": "Underretning"}]


def test_sagsskabelon_bruger_verificeret_sti(respx_mock, client):
    """One template is fetched from /api/sagsskabelon/{id}."""
    respx_mock.get(f"{BASE_URL}/api/sagsskabelon/332").mock(
        return_value=httpx.Response(200, json={"Id": 332, "Navn": "Underretning"})
    )

    assert client.opslag.sagsskabelon(332) == {"Id": 332, "Navn": "Underretning"}
