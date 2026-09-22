# src/sbsys/models/journalnotat.py
"""Journal notes."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from sbsys.models._base import SbsysModel


class Journalnotat(SbsysModel):
    """A note on a case journal.

    Attributes:
        id: Note id. ``None`` on objects built locally before creation.
        titel: Note heading.
        notat: Note body. SBSYS accepts and renders HTML here, which is how
            tables and formatting get in.
        sags_id: Id of the case the note belongs to.
        oprettet: When the note was created.
    """

    id: int | None = None
    titel: str | None = None
    notat: str | None = None
    sags_id: int | None = Field(default=None, alias="SagID")
    oprettet: datetime | None = Field(default=None, alias="Oprettet")
