# src/sbsys/__init__.py
"""Delt Python-klient til SBSYS ESDH REST API."""

from sbsys.client import SbsysClient
from sbsys.config import SbsysSettings
from sbsys.errors import (
    SbsysAPIError,
    SbsysAuthError,
    SbsysConflictError,
    SbsysError,
    SbsysNotFoundError,
    SbsysRateLimitError,
    SbsysServerError,
    SbsysValidationError,
)
from sbsys.models import (
    Dokument,
    Erindring,
    Fil,
    Journalnotat,
    Part,
    PartType,
    Sag,
    Sagsbehandler,
    Sagsstatus,
    dokument,
)

__version__ = "0.1.0"

__all__ = [
    "dokument",
    "Erindring",
    "Fil",
    "Journalnotat",
    "Part",
    "PartType",
    "Sag",
    "Sagsbehandler",
    "Sagsstatus",
    "SbsysAPIError",
    "SbsysAuthError",
    "SbsysClient",
    "SbsysConflictError",
    "SbsysError",
    "SbsysNotFoundError",
    "SbsysRateLimitError",
    "SbsysServerError",
    "SbsysSettings",
    "SbsysValidationError",
    "__version__",
]
