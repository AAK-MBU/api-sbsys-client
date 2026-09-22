# src/sbsys/resources/opslag.py
"""Lookup data: case templates, users and status lists.

These are per-installation configuration rather than a fixed vocabulary, so
ids differ between municipalities and between test and production. Look them
up instead of hard-coding them.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from sbsys.errors import SbsysNotFoundError
from sbsys.models.sag import Sagsbehandler, Sagsstatus
from sbsys.resources._base import Resource


class Opslag(Resource):
    """Lookup operations. Reached as ``client.opslag``.

    Lookup data changes rarely, so some results are cached for the lifetime of
    the client. A long-running process will not see a configuration change
    until it is restarted.
    """

    def sagsskabeloner(self) -> list[dict[str, Any]]:
        """List every case template in the installation.

        Returned as raw dicts rather than models, because template shape
        varies a great deal between installations and there is no useful
        common subset to pin down.

        Returns:
            The templates, as SBSYS returns them.
        """
        data = self._t.json("GET", "/api/sag/sagsskabelon")
        return list(data or [])

    def sagsskabelon(self, skabelon_id: int) -> dict[str, Any]:
        """Fetch one case template.

        Args:
            skabelon_id: Template id.

        Returns:
            The template, as SBSYS returns it.

        Raises:
            SbsysNotFoundError: If no template has that id.
        """
        return dict(self._t.json("GET", f"/api/sag/sagsskabelon/{skabelon_id}"))

    def statusser(self) -> list[Sagsstatus]:
        """List the case statuses configured in the installation.

        Returns:
            Every status, in the order SBSYS returned them.
        """
        data = self._t.json("GET", "/api/sag/sagsstatus")
        return [Sagsstatus.model_validate(r) for r in data or []]

    def find_brugere(self, soegetekst: str) -> list[Sagsbehandler]:
        """Search for users by name or initials.

        Args:
            soegetekst: Free-text search. SBSYS matches substrings, so short
                input can return many users.

        Returns:
            Matching users, or an empty list.
        """
        data = self._t.json("GET", "/api/bruger/search", params={"q": soegetekst})
        rows = data.get("Results", data) if isinstance(data, dict) else data
        return [Sagsbehandler.model_validate(r) for r in rows or []]

    @lru_cache(maxsize=256)  # noqa: B019
    def bruger_id_for_initialer(self, initialer: str) -> int:
        """Resolve a caseworker's initials to their SBSYS user id.

        Case creation wants a user id, but what a human knows is the initials.
        Results are cached for the lifetime of the client, since the mapping
        is stable.

        Args:
            initialer: Login initials. Matched case-insensitively, and only on
                an exact match — a substring hit from the underlying search is
                not accepted.

        Returns:
            The user id.

        Raises:
            SbsysNotFoundError: If no user has exactly those initials.
        """
        brugere = self.find_brugere(initialer)
        traef = [b for b in brugere if (b.initialer or "").lower() == initialer.lower()]
        if not traef:
            raise SbsysNotFoundError(404, "GET", "/api/bruger/search", f"No user: {initialer}")
        return traef[0].id
