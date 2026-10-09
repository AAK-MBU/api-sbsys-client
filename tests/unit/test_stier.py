"""Paths and payloads that must match the SBSYS specification."""

from __future__ import annotations

import json

import httpx
import pytest

from sbsys import SbsysNotFoundError
from sbsys.models.part import PartType
from tests.conftest import BASE_URL


def test_statusser_bruger_sagstatuslist(respx_mock, client):
    """Statuses are listed from /api/sag/sagStatusList."""
    respx_mock.get(f"{BASE_URL}/api/sag/sagStatusList").mock(
        return_value=httpx.Response(200, json=[{"Id": 1, "Navn": "Aktiv"}])
    )

    assert [s.navn for s in client.opslag.statusser()] == ["Aktiv"]


def test_bruger_id_for_initialer_soeger_paa_logonid(respx_mock, client):
    """Users are searched with POST and matched exactly on LogonId."""
    route = respx_mock.post(f"{BASE_URL}/api/bruger/search").mock(
        return_value=httpx.Response(
            200, json=[{"Id": 7, "LogonId": "ABCD1"}, {"Id": 8, "LogonId": "abc"}]
        )
    )

    assert client.opslag.bruger_id_for_initialer("ABC") == 8
    assert json.loads(route.calls.last.request.content) == {"LogonId": "ABC"}


def test_find_brugere_fletter_navn_og_login(respx_mock, client):
    """Name and login are searched separately and merged without duplicates."""
    route = respx_mock.post(f"{BASE_URL}/api/bruger/search").mock(
        side_effect=[
            httpx.Response(200, json=[{"Id": 1, "LogonId": "an"}]),
            httpx.Response(200, json=[{"Id": 1, "Navn": "Anna"}, {"Id": 2, "Navn": "Ann"}]),
        ]
    )

    assert [b.id for b in client.opslag.find_brugere("an")] == [1, 2]
    assert [json.loads(c.request.content) for c in route.calls] == [
        {"LogonId": "an"},
        {"Navn": "an"},
    ]


def test_hent_person_poster_cpr(respx_mock, client):
    """Persons are searched with POST and a CprNummer body."""
    route = respx_mock.post(f"{BASE_URL}/api/person/search").mock(
        return_value=httpx.Response(200, json=[{"Id": 5, "CprNummer": "010101-1234"}])
    )

    person = client.parter.hent_person("0101011234")

    assert person.cpr_nummer == "010101-1234"
    assert json.loads(route.calls.last.request.content) == {"CprNummer": "010101-1234"}


def test_hent_firma_ukendt(respx_mock, client):
    """An empty company search becomes SbsysNotFoundError."""
    respx_mock.post(f"{BASE_URL}/api/firma/search").mock(return_value=httpx.Response(200, json=[]))

    with pytest.raises(SbsysNotFoundError):
        client.parter.hent_firma("12345678")


def test_opdater_henter_og_putter_hele_sagen(respx_mock, client):
    """An update is a PUT of the fetched case with the changes laid over it."""
    respx_mock.get(f"{BASE_URL}/api/sag/42").mock(
        return_value=httpx.Response(200, json={"Id": 42, "SagsTitel": "Gammel", "Nummer": "X"})
    )
    route = respx_mock.put(f"{BASE_URL}/api/sag/42").mock(
        return_value=httpx.Response(200, json={"Id": 42, "SagsTitel": "Ny", "Nummer": "X"})
    )

    client.sager.opdater(42, {"SagsTitel": "Ny"})

    assert json.loads(route.calls.last.request.content) == {
        "Id": 42,
        "SagsTitel": "Ny",
        "Nummer": "X",
    }


def test_tilfoej_part_bruger_part(respx_mock, client):
    """Parties are attached through /api/sag/{id}/part."""
    route = respx_mock.post(f"{BASE_URL}/api/sag/42/part").mock(
        return_value=httpx.Response(200, json=True)
    )

    client.sager.tilfoej_part(42, 5, PartType.PERSON)

    assert json.loads(route.calls.last.request.content) == {"PartId": 5, "PartType": "Person"}


def test_upload_journaliserer(respx_mock, client, tmp_path):
    """Uploads go to /api/dokument/journaliser with a file and a json part."""
    fil = tmp_path / "brev.pdf"
    fil.write_bytes(b"%PDF")
    route = respx_mock.post(f"{BASE_URL}/api/dokument/journaliser").mock(
        return_value=httpx.Response(200, json={"Id": 9, "Navn": "Brev", "SagID": 42})
    )

    dokument = client.dokumenter.upload(42, fil, navn="Brev")

    assert dokument.id == 9
    body = route.calls.last.request.content
    assert b'name="file"; filename="brev.pdf"' in body
    assert b'{"SagID": 42, "DokumentNavn": "Brev"}' in body


def test_erindringer_paa_sag(respx_mock, client):
    """Reminders are listed from /api/erindring/sag/{id}."""
    respx_mock.get(f"{BASE_URL}/api/erindring/sag/42").mock(
        return_value=httpx.Response(200, json=[{"Id": 1, "Navn": "Ring", "SagId": 42}])
    )

    [erindring] = client.erindringer.hent_paa_sag(42)

    assert erindring.sags_id == 42


def test_opret_erindring_payload(respx_mock, client):
    """Responsible user and type are sent as objects, as the DTO defines them."""
    route = respx_mock.post(f"{BASE_URL}/api/erindring").mock(
        return_value=httpx.Response(200, json={"Id": 1, "SagId": 42})
    )

    client.erindringer.opret(42, navn="Ring", ansvarlig_id=7, erindringstype_id=3)

    assert json.loads(route.calls.last.request.content) == {
        "SagId": 42,
        "Navn": "Ring",
        "Beskrivelse": "",
        "HarDeadline": False,
        "Ansvarlig": {"Id": 7},
        "ErindringType": {"Id": 3},
    }


def test_journalnotater_paa_sag(respx_mock, client):
    """Journal notes are listed from /api/sag/{id}/journalarknotes."""
    respx_mock.get(f"{BASE_URL}/api/sag/42/journalarknotes").mock(
        return_value=httpx.Response(
            200, json=[{"Id": 1, "SagID": 42, "Overskrift": "Samtale", "Note": "<p>x</p>"}]
        )
    )

    [notat] = client.journalnotater.hent_paa_sag(42)

    assert (notat.titel, notat.notat) == ("Samtale", "<p>x</p>")


def test_opret_journalnotat(respx_mock, client):
    """Notes are created through /api/journalarknote/create with a contact time."""
    route = respx_mock.post(f"{BASE_URL}/api/journalarknote/create").mock(
        return_value=httpx.Response(200, json={"Id": 1, "SagID": 42, "Overskrift": "Samtale"})
    )

    client.journalnotater.opret(42, "Samtale", "<p>x</p>")

    body = json.loads(route.calls.last.request.content)
    assert body["SagID"] == 42
    assert (body["Overskrift"], body["Note"]) == ("Samtale", "<p>x</p>")
    assert body["KontaktTidspunkt"]
