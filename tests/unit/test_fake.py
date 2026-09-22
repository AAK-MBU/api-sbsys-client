# tests/unit/test_fake.py
"""The fake must behave like the real client for what it covers."""

from __future__ import annotations

import pytest

from sbsys import SbsysNotFoundError
from sbsys.testing import FakeSbsysClient


def test_hent_kendt_sag():
    """A seeded case can be fetched from the fake."""
    sbsys = FakeSbsysClient(sager={1: {"Id": 1, "SagsTitel": "Test"}})
    assert sbsys.sager.hent(1).visningstitel == "Test"


def test_ukendt_sag_giver_samme_fejl_som_rigtig_klient():
    """An unseeded case raises the same error the real client would."""
    sbsys = FakeSbsysClient()
    with pytest.raises(SbsysNotFoundError):
        sbsys.sager.hent(99)


def test_oprettelse_registreres():
    """A case created through the fake is recorded for assertion."""
    sbsys = FakeSbsysClient()
    sag = sbsys.sager.opret_fra_skabelon(
        titel="Ny sag", skabelon_id=1, sagsbehandler_id=2, part_id=3
    )
    assert sag.visningstitel == "Ny sag"
    assert len(sbsys.sager.oprettede) == 1
