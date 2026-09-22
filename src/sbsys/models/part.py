# src/sbsys/models/part.py
"""Parties: the people and companies attached to a case."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from sbsys.models._base import SbsysModel


class PartType(StrEnum):
    """The kind of party, as SBSYS names it in request payloads."""

    PERSON = "Person"
    """A citizen, identified by CPR number."""

    FIRMA = "Firma"
    """A company, identified by CVR number."""


class Part(SbsysModel):
    """A person or company known to SBSYS.

    The same model covers both kinds, because SBSYS returns them from
    different endpoints with largely the same shape. Which identifier is
    populated tells the two apart.

    Attributes:
        id: SBSYS' internal party id. This, not the CPR or CVR number, is what
            case creation and party endpoints expect.
        navn: Display name.
        cpr_nummer: CPR number in ``DDMMYY-NNNN`` format, for persons.
        cvr_nummer: CVR number, for companies.
        adresse: Address as a single formatted string.
        part_type: Whether SBSYS considers this a person or a company.
    """

    id: int
    navn: str | None = None
    cpr_nummer: str | None = Field(default=None, alias="CPRnummer")
    cvr_nummer: str | None = Field(default=None, alias="CVRnummer")
    adresse: str | None = None
    part_type: PartType | None = None
