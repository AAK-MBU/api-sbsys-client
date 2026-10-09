# src/sbsys/resources/erindringer.py
"""Reminders."""

from __future__ import annotations

from datetime import date

from sbsys.models.erindring import Erindring
from sbsys.resources._base import Resource


class Erindringer(Resource):
    """Reminder operations. Reached as ``client.erindringer``."""

    def hent_paa_sag(self, sags_id: int) -> list[Erindring]:
        """List the reminders on a case.

        Args:
            sags_id: Internal case id.

        Returns:
            Every reminder on the case, including completed ones, or an empty
            list if it has none.
        """
        data = self._t.json("GET", f"/api/erindring/sag/{sags_id}")
        rows = data.get("Results", data) if isinstance(data, dict) else data
        return [Erindring.model_validate(r) for r in rows or []]

    def opret(
        self,
        sags_id: int,
        *,
        navn: str,
        beskrivelse: str = "",
        frist: date | None = None,
        ansvarlig_id: int | None = None,
        erindringstype_id: int | None = None,
    ) -> Erindring:
        """Create a reminder on a case.

        Optional arguments are omitted from the payload when left out, so
        SBSYS applies its own defaults — typically the case's caseworker as
        the responsible user. Never retried, to avoid duplicates.

        Args:
            sags_id: Internal case id.
            navn: Short title, which is what the caseworker sees in their list.
            beskrivelse: Longer description.
            frist: Due date. Omitted from the payload when ``None``.
            ansvarlig_id: SBSYS user id of the responsible caseworker.
            erindringstype_id: Reminder type id. Types are per-installation
                configuration, so look the id up rather than hard-coding it.

        Returns:
            The created reminder.

        Raises:
            SbsysAPIError: If SBSYS rejects the reminder, e.g. on an unknown
                type or user id.
        """
        body: dict[str, object] = {
            "SagId": sags_id,
            "Navn": navn,
            "Beskrivelse": beskrivelse,
            "HarDeadline": frist is not None,
        }
        if frist is not None:
            body["Deadline"] = frist.isoformat()
        if ansvarlig_id is not None:
            body["Ansvarlig"] = {"Id": ansvarlig_id}
        if erindringstype_id is not None:
            body["ErindringType"] = {"Id": erindringstype_id}
        return Erindring.model_validate(
            self._t.json("POST", "/api/erindring", json=body, retry=False)
        )
