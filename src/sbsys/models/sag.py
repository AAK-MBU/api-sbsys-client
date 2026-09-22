# src/sbsys/models/sag.py
"""Cases, and the lookup types that hang off them."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from sbsys.models._base import SbsysModel
from sbsys.models.part import Part


class Sagsstatus(SbsysModel):
    """A case status, as configured in the SBSYS installation.

    Statuses are per-installation configuration rather than a fixed list, so
    look up the id you need instead of hard-coding one.

    Attributes:
        id: Status id, used when updating a case.
        navn: Display name.
    """

    id: int
    navn: str | None = None


class Sagsbehandler(SbsysModel):
    """A caseworker.

    Attributes:
        id: SBSYS user id, required when creating or reassigning a case.
        navn: Full name.
        initialer: Short login initials, which is usually what a human knows.
    """

    id: int
    navn: str | None = None
    initialer: str | None = None


class Sag(SbsysModel):
    """A case.

    Attributes:
        id: Internal case id, used by every other endpoint.
        nummer: Human-readable case number, e.g. ``27.00.00-G01-1-24``.
        titel: Case title as returned by the read endpoints.
        sags_titel: Case title as returned by search and creation endpoints.
            Prefer :attr:`visningstitel` over either of these.
        sagsstatus: Current status, when the endpoint includes it.
        sagsbehandler: Assigned caseworker, when the endpoint includes it.
        primaer_part: The citizen or company the case is about.
        oprettet_dato: Case date, i.e. when the case was created.
        sidst_aendret: Timestamp of the most recent change.
    """

    id: int
    nummer: str | None = None
    titel: str | None = Field(default=None, alias="Titel")
    sags_titel: str | None = Field(default=None, alias="SagsTitel")
    sagsstatus: Sagsstatus | None = None
    sagsbehandler: Sagsbehandler | None = None
    primaer_part: Part | None = Field(default=None, alias="PrimaryPart")
    oprettet_dato: datetime | None = Field(default=None, alias="SagsDato")
    sidst_aendret: datetime | None = Field(default=None, alias="SidstAendret")

    @property
    def visningstitel(self) -> str:
        """The case title, whichever field SBSYS put it in.

        SBSYS returns the title as ``Titel`` from some endpoints and
        ``SagsTitel`` from others. Use this instead of picking one.

        Returns:
            The title, or an empty string if neither field was populated.
        """
        return self.titel or self.sags_titel or ""
