# src/sbsys/testing/fake.py
"""An in-memory fake, so consuming projects can be tested without SBSYS."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sbsys.errors import SbsysNotFoundError
from sbsys.models.journalnotat import Journalnotat
from sbsys.models.part import PartType
from sbsys.models.sag import Sag


class _FakeSager:
    """Stand-in for :class:`~sbsys.resources.sager.Sager`, backed by a dict."""

    def __init__(self, sager: dict[int, dict[str, Any]]) -> None:
        """Seed the fake with cases.

        Args:
            sager: Cases keyed by id, each value shaped like an SBSYS
                response, e.g. ``{"Id": 1, "SagsTitel": "Test"}``.
        """
        self._sager = sager
        self._naeste_id = max(sager, default=0) + 1
        self.oprettede: list[dict[str, Any]] = []
        """Cases created through this fake, in order. Assert against it."""

    def hent(self, sags_id: int) -> Sag:
        """Fetch a seeded case.

        Args:
            sags_id: Case id.

        Returns:
            The case.

        Raises:
            SbsysNotFoundError: If no case was seeded with that id — the same
                error the real client raises.
        """
        if sags_id not in self._sager:
            raise SbsysNotFoundError(404, "GET", f"/api/sag/{sags_id}", "Case not found")
        return Sag.model_validate(self._sager[sags_id])

    def soeg(self, kriterier: dict[str, Any] | None = None, **_: Any) -> Iterator[Sag]:
        """Yield every seeded case.

        Criteria are ignored: filtering would mean reimplementing SBSYS' search
        semantics, and a test that depends on those is testing the wrong thing.
        Seed only the cases the test needs.

        Args:
            kriterier: Ignored, accepted for signature compatibility.
            **_: Ignored.

        Yields:
            Every seeded case.
        """
        for row in self._sager.values():
            yield Sag.model_validate(row)

    def opret_fra_skabelon(
        self,
        *,
        titel: str,
        skabelon_id: int,
        sagsbehandler_id: int,
        part_id: int,
        part_type: PartType = PartType.PERSON,
    ) -> Sag:
        """Create a case in memory and record it on :attr:`oprettede`.

        Template, caseworker and party ids are not validated.

        Args:
            titel: Case title.
            skabelon_id: Template id. Recorded but not checked.
            sagsbehandler_id: Caseworker id. Recorded but not checked.
            part_id: Party id. Recorded but not checked.
            part_type: Whether the party is a person or a company.

        Returns:
            The created case, with a generated id.
        """
        row = {"Id": self._naeste_id, "SagsTitel": titel, "Nummer": f"FAKE-{self._naeste_id}"}
        self._sager[self._naeste_id] = row
        self.oprettede.append(row)
        self._naeste_id += 1
        return Sag.model_validate(row)


class _FakeJournalnotater:
    """Stand-in for the journal note resource, recording what it is given."""

    def __init__(self) -> None:
        """Start with no recorded notes."""
        self.oprettede: list[tuple[int, str, str]] = []
        """Notes created, as ``(sags_id, titel, notat)``. Assert against it."""

    def opret(self, sags_id: int, titel: str, notat: str) -> Journalnotat:
        """Record a journal note.

        The case id is not checked against the seeded cases.

        Args:
            sags_id: Case id.
            titel: Note heading.
            notat: Note body.

        Returns:
            The recorded note, with a generated id.
        """
        self.oprettede.append((sags_id, titel, notat))
        return Journalnotat(Id=len(self.oprettede), SagID=sags_id, Titel=titel, Notat=notat)


class FakeSbsysClient:
    """Drop-in replacement for :class:`~sbsys.SbsysClient` in tests.

    Use it instead of mocking this package, so every project tests against one
    shared understanding of how the client behaves::

        sbsys = FakeSbsysClient(sager={1: {"Id": 1, "SagsTitel": "Test"}})
        min_proces(sbsys)
        assert sbsys.journalnotater.oprettede

    Only cases and journal notes are covered. Anything else raises
    :class:`NotImplementedError` rather than silently returning something
    wrong — extend the fake when you need more, or use ``respx`` for that
    particular test.
    """

    def __init__(self, sager: dict[int, dict[str, Any]] | None = None) -> None:
        """Seed the fake.

        Args:
            sager: Cases keyed by id, each shaped like an SBSYS response.
        """
        self.sager = _FakeSager(dict(sager or {}))
        self.journalnotater = _FakeJournalnotater()

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Reject raw endpoint calls.

        Args:
            method: HTTP method.
            path: Endpoint path.
            **kwargs: Ignored.

        Raises:
            NotImplementedError: Always. A fake cannot guess what an arbitrary
                endpoint returns, and guessing would make the test pass for
                the wrong reason.
        """
        raise NotImplementedError(
            f"FakeSbsysClient does not support raw calls ({method} {path}). "
            "Extend the fake, or use respx for this test."
        )

    def close(self) -> None:
        """Do nothing. Present so the fake matches the real client."""
        return None

    def __enter__(self) -> FakeSbsysClient:
        """Enter the context manager.

        Returns:
            This fake.
        """
        return self

    def __exit__(self, *exc: object) -> None:
        """Do nothing on leaving the context manager.

        Args:
            *exc: Exception type, value and traceback. Ignored.
        """
        return None
