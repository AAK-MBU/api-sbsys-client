# src/sbsys/resources/journalnotater.py
"""Journal notes."""

from __future__ import annotations

from datetime import datetime

from sbsys.models.journalnotat import Journalnotat
from sbsys.resources._base import Resource


class Journalnotater(Resource):
    """Journal note operations. Reached as ``client.journalnotater``."""

    def hent_paa_sag(self, sags_id: int) -> list[Journalnotat]:
        """List the journal notes on a case.

        Args:
            sags_id: Internal case id.

        Returns:
            Every note on the case, or an empty list if it has none.
        """
        data = self._t.json("GET", f"/api/sag/{sags_id}/journalarknotes")
        rows = data.get("Results", data) if isinstance(data, dict) else data
        return [Journalnotat.model_validate(r) for r in rows or []]

    def opret(self, sags_id: int, titel: str, notat: str) -> Journalnotat:
        """Add a journal note to a case.

        SBSYS renders HTML in the note body, which is how tables and
        formatting get in. Escape any value interpolated into that HTML — note
        bodies routinely contain names and addresses straight from a citizen.

        The contact time SBSYS requires is set to now.

        Never retried, since a replay would leave duplicate notes on the case.

        Args:
            sags_id: Internal case id.
            titel: Note heading.
            notat: Note body. May contain HTML.

        Returns:
            The created note.

        Raises:
            SbsysConflictError: If the case does not accept new notes, e.g.
                because it is closed.
        """
        body = {
            "SagID": sags_id,
            "Overskrift": titel,
            "Note": notat,
            "KontaktTidspunkt": datetime.now().astimezone().isoformat(),
        }
        return Journalnotat.model_validate(
            self._t.json("POST", "/api/journalarknote/create", json=body, retry=False)
        )
