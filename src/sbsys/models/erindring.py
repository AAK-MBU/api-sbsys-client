# src/sbsys/models/erindring.py
"""Reminders."""

from __future__ import annotations

from datetime import date

from pydantic import Field

from sbsys.models._base import SbsysModel


class Erindring(SbsysModel):
    """A follow-up reminder attached to a case.

    Attributes:
        id: Reminder id. ``None`` on objects built locally before creation.
        navn: Short title, which is what the caseworker sees in their list.
        beskrivelse: Longer description.
        sags_id: Id of the case the reminder belongs to.
        frist: Due date.
    """

    id: int | None = None
    navn: str | None = None
    beskrivelse: str | None = None
    sags_id: int | None = Field(default=None, alias="SagID")
    frist: date | None = Field(default=None, alias="Deadline")
