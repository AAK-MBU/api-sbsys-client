# tests/integration/test_contract.py
"""Contract tests: catch a change in SBSYS before production does.

Run with::

    uv run pytest -m integration

These are deliberately read-only. Write tests belong in an environment with
teardown — do not add them here without that in place.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


def test_statusliste_parser(live_client):
    """The configured status list still parses into our model."""
    statusser = live_client.opslag.statusser()
    assert statusser
    assert all(s.id for s in statusser)


def test_sagsskabeloner_parser(live_client):
    """The template list is non-empty and decodes as JSON."""
    skabeloner = live_client.opslag.sagsskabeloner()
    assert skabeloner


@pytest.mark.contract
def test_kendt_sag_parser(live_client):
    """A known case still parses, including its title field."""
    sags_id = os.environ.get("SBSYS_TEST_SAGS_ID")
    if not sags_id:
        pytest.skip("Set SBSYS_TEST_SAGS_ID to run this test")
    sag = live_client.sager.hent(int(sags_id))
    assert sag.id == int(sags_id)
    assert sag.visningstitel
