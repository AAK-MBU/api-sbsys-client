# src/sbsys/models/dokument.py
"""Documents and their files."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from sbsys.models._base import SbsysModel


class Fil(SbsysModel):
    """A single file belonging to a document.

    Attributes:
        id: File id, which is what the download endpoint takes — not the
            document id.
        navn: File name as shown in SBSYS.
        filendelse: File extension, without a leading dot.
        stoerrelse: Size in bytes.
    """

    id: int
    navn: str | None = None
    filendelse: str | None = Field(default=None, alias="Filendelse")
    stoerrelse: int | None = Field(default=None, alias="Size")


class Dokument(SbsysModel):
    """A document on a case.

    A document is a container: the bytes live in :attr:`filer`. A document
    with several files is normal, so do not assume there is exactly one.

    Attributes:
        id: Document id.
        navn: Document title.
        sags_id: Id of the case the document belongs to.
        dokument_dato: The document's own date, which need not match when it
            was uploaded.
        filer: The files attached to this document.
    """

    id: int
    navn: str | None = None
    sags_id: int | None = Field(default=None, alias="SagID")
    dokument_dato: datetime | None = Field(default=None, alias="DokumentDato")
    filer: list[Fil] = Field(default_factory=list, alias="Filer")
