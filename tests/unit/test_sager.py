# tests/unit/test_sager.py
"""The case resource: parsing, pagination and local validation."""

from __future__ import annotations

import httpx
import pytest

from sbsys import SbsysValidationError
from tests.conftest import BASE_URL


def test_hent_sag_parses(respx_mock, client):
    """A case response parses, including the nested primary party."""
    respx_mock.get(f"{BASE_URL}/api/sag/42").mock(
        return_value=httpx.Response(
            200,
            json={
                "Id": 42,
                "Nummer": "27.00.00-G01-1-24",
                "SagsTitel": "Underretning",
                "PrimaryPart": {"Id": 7, "Navn": "Test Testesen", "CPRnummer": "010101-1234"},
            },
        )
    )
    sag = client.sager.hent(42)

    assert sag.id == 42
    assert sag.visningstitel == "Underretning"
    assert sag.primaer_part is not None
    assert sag.primaer_part.cpr_nummer == "010101-1234"


def test_ukendte_felter_bevares(respx_mock, client):
    """A field we do not model survives parsing and is reachable through raw()."""
    respx_mock.get(f"{BASE_URL}/api/sag/42").mock(
        return_value=httpx.Response(200, json={"Id": 42, "HeltNytFelt": "værdi"})
    )
    sag = client.sager.hent(42)

    assert sag.id == 42
    assert sag.raw()["HeltNytFelt"] == "værdi"


def test_soegning_henter_flere_sider(respx_mock, client):
    """Pagination walks every page until the reported total is reached."""
    side1 = {"Results": [{"Id": i} for i in range(1, 101)], "TotalNumberOfResults": 150}
    side2 = {"Results": [{"Id": i} for i in range(101, 151)], "TotalNumberOfResults": 150}
    route = respx_mock.post(f"{BASE_URL}/api/sag/search").mock(
        side_effect=[httpx.Response(200, json=side1), httpx.Response(200, json=side2)]
    )

    sager = list(client.sager.soeg({"SagsTitel": "x"}))

    assert len(sager) == 150
    assert route.call_count == 2


def test_soegning_er_doven(respx_mock, client):
    """Stopper man efter tre elementer, hentes kun første side."""
    side1 = {"Results": [{"Id": i} for i in range(1, 101)], "TotalNumberOfResults": 500}
    route = respx_mock.post(f"{BASE_URL}/api/sag/search").mock(
        return_value=httpx.Response(200, json=side1)
    )

    iterator = client.sager.soeg({})
    fundne = [next(iterator) for _ in range(3)]

    assert len(fundne) == 3
    assert route.call_count == 1


def test_cpr_normaliseres(respx_mock, client):
    """A CPR number without a hyphen is normalised before being sent."""
    route = respx_mock.post(f"{BASE_URL}/api/sag/search").mock(
        return_value=httpx.Response(200, json={"Results": [], "TotalNumberOfResults": 0})
    )
    list(client.sager.soeg_paa_cpr("0101011234"))

    body = route.calls.last.request.content.decode()
    assert '"CprNummer": "010101-1234"' in body.replace('"CprNummer":"', '"CprNummer": "')


def test_ugyldigt_cpr_afvises_lokalt(respx_mock, client):
    """A malformed CPR number fails locally, without a request being sent."""
    with pytest.raises(SbsysValidationError):
        list(client.sager.soeg_paa_cpr("ikke-et-cpr"))


def test_tom_titel_afvises(client):
    """A blank case title is rejected before SBSYS is contacted."""
    with pytest.raises(SbsysValidationError):
        client.sager.opret_fra_skabelon(titel="   ", skabelon_id=1, sagsbehandler_id=2, part_id=3)
