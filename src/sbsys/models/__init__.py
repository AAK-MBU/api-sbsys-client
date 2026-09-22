# src/sbsys/models/__init__.py
"""Curated Pydantic models for the parts of SBSYS we actually use.

These are hand-written and stable: field names, types and the documented
behaviour are public API and follow semantic versioning. The much larger set
of generated models under :mod:`sbsys.models.generated` is a reference for
building these, not something to use directly.
"""

from sbsys.models._base import SbsysModel
from sbsys.models.dokument import Dokument, Fil
from sbsys.models.erindring import Erindring
from sbsys.models.journalnotat import Journalnotat
from sbsys.models.part import Part, PartType
from sbsys.models.sag import Sag, Sagsbehandler, Sagsstatus

__all__ = [
    "Dokument",
    "Erindring",
    "Fil",
    "Journalnotat",
    "Part",
    "PartType",
    "Sag",
    "Sagsbehandler",
    "Sagsstatus",
    "SbsysModel",
]
