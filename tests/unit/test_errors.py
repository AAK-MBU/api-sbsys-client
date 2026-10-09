# tests/unit/test_errors.py
"""HTTP statuses must surface as our own exceptions, never as httpx'."""

from __future__ import annotations

import httpx
import pytest
import respx

from sbsys import (
    SbsysAPIError,
    SbsysConflictError,
    SbsysNotFoundError,
    SbsysServerError,
)
from tests.conftest import BASE_URL


@pytest.mark.parametrize(
    ("status", "forventet"),
    [
        (404, SbsysNotFoundError),
        (409, SbsysConflictError),
        (400, SbsysAPIError),
        (500, SbsysServerError),
    ],
)
@respx.mock(assert_all_called=False)
def test_status_mappes_til_exception(respx_mock, client, status, forventet):
    """Each HTTP status maps to its specific exception subclass."""
    respx_mock.get(f"{BASE_URL}/api/sag/9").mock(
        return_value=httpx.Response(status, json={"Message": "fejl"})
    )
    with pytest.raises(forventet):
        client.sager.hent(9)


def test_fejlbesked_indeholder_kontekst(respx_mock, client):
    """The exception carries status, response body and a correlation id."""
    respx_mock.get(f"{BASE_URL}/api/sag/9").mock(
        return_value=httpx.Response(404, text="Sagen findes ikke")
    )
    with pytest.raises(SbsysNotFoundError) as exc:
        client.sager.hent(9)

    assert exc.value.status_code == 404
    assert "Sagen findes ikke" in str(exc.value)
    assert exc.value.request_id


def test_serverfejl_genforsoeges_paa_get(respx_mock, client):
    """A 5xx on a GET is retried, and the second attempt's result is returned."""
    route = respx_mock.get(f"{BASE_URL}/api/sag/9").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json={"Id": 9, "SagsTitel": "Ok"}),
        ]
    )
    sag = client.sager.hent(9)
    assert sag.id == 9
    assert route.call_count == 2


def test_oprettelse_genforsoeges_ikke(respx_mock, client):
    """A 5xx on case creation is not retried, so a timeout cannot duplicate a case."""
    route = respx_mock.post(f"{BASE_URL}/api/sag/template").mock(return_value=httpx.Response(503))
    with pytest.raises(SbsysServerError):
        client.sager.opret_fra_skabelon(titel="Test", skabelon_id=1, sagsbehandler_id=2, part_id=3)
    assert route.call_count == 1
