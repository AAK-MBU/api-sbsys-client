# src/sbsys/resources/parter.py
"""Parties: looking up citizens and companies."""

from __future__ import annotations

from sbsys.errors import SbsysNotFoundError
from sbsys.models.part import Part
from sbsys.resources._base import Resource, normaliser_cpr


class Parter(Resource):
    """Party lookups. Reached as ``client.parter``.

    Case creation and party endpoints want SBSYS' internal party id, so a
    lookup here is usually the first call in any workflow that starts from a
    CPR or CVR number.
    """

    def hent_person(self, cpr: str) -> Part:
        """Look up a citizen by CPR number.

        Args:
            cpr: CPR number, with or without a hyphen.

        Returns:
            The first matching party.

        Raises:
            SbsysValidationError: If the CPR number is malformed.
            SbsysNotFoundError: If SBSYS knows no such citizen. The search
                endpoint answers ``200`` with an empty result, which is
                translated here so callers get one consistent failure mode.
        """
        body = {"CprNummer": normaliser_cpr(cpr)}
        rows = self._t.json("POST", "/api/person/search", json=body, retry=True)
        if not rows:
            raise SbsysNotFoundError(404, "POST", "/api/person/search", "Citizen not found")
        return Part.model_validate(rows[0] if isinstance(rows, list) else rows)

    def hent_firma(self, cvr: str) -> Part:
        """Look up a company by CVR number.

        Args:
            cvr: CVR number.

        Returns:
            The first matching party.

        Raises:
            SbsysNotFoundError: If SBSYS knows no such company.
        """
        rows = self._t.json("POST", "/api/firma/search", json={"CvrNummer": cvr}, retry=True)
        if not rows:
            raise SbsysNotFoundError(404, "POST", "/api/firma/search", "Company not found")
        return Part.model_validate(rows[0] if isinstance(rows, list) else rows)
