# src/sbsys/client.py
"""The public entry point to SBSYS."""

from __future__ import annotations

from functools import cached_property
from types import TracebackType
from typing import Any

import httpx

from sbsys._transport.http import Transport
from sbsys.config import SbsysSettings
from sbsys.resources.dokumenter import Dokumenter
from sbsys.resources.erindringer import Erindringer
from sbsys.resources.journalnotater import Journalnotater
from sbsys.resources.opslag import Opslag
from sbsys.resources.parter import Parter
from sbsys.resources.sager import Sager


class SbsysClient:
    """Client for the SBSYS case management REST API.

    Operations are grouped into resources reached as attributes::

        with SbsysClient.from_env() as sbsys:
            sag = sbsys.sager.hent(12345)
            sbsys.journalnotater.opret(sag.id, "Received", "<p>Noted.</p>")

    Create one client per process and reuse it: each instance holds its own
    connection pool and token cache, so building a client per call means a
    fresh TLS handshake and a fresh token every time. Sharing an instance
    between threads is safe.

    Business logic does not belong here. A workflow such as "create the case,
    attach the party, journal the receipt, set a reminder" belongs in the
    project that owns that process — keeping it out is what makes this package
    reusable across repositories.

    Use it as a context manager, or call :meth:`close` when done.
    """

    def __init__(
        self,
        settings: SbsysSettings,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        """Build a client. No connection is opened until the first request.

        Args:
            settings: Connection settings. Use :meth:`from_env` to build these
                from the environment.
            http_client: Pre-configured HTTP client. Injected by tests;
                production code leaves it out.
        """
        self._settings = settings
        self._transport = Transport(settings, client=http_client)

    @classmethod
    def from_env(cls, **overrides: Any) -> SbsysClient:
        """Build a client from ``SBSYS_``-prefixed environment variables.

        Values are also read from a ``.env`` file when one is present.

        Args:
            **overrides: Settings to override, using the field names of
                :class:`~sbsys.config.SbsysSettings`.

        Returns:
            A ready client.

        Raises:
            pydantic.ValidationError: If a required setting is missing or has
                the wrong type.
        """
        return cls(SbsysSettings(**overrides))

    @cached_property
    def sager(self) -> Sager:
        """Cases: lookup, search, creation and updates."""
        return Sager(self._transport)

    @cached_property
    def parter(self) -> Parter:
        """Parties: looking up citizens and companies."""
        return Parter(self._transport)

    @cached_property
    def dokumenter(self) -> Dokumenter:
        """Documents: lookup, download and upload."""
        return Dokumenter(self._transport)

    @cached_property
    def journalnotater(self) -> Journalnotater:
        """Journal notes."""
        return Journalnotater(self._transport)

    @cached_property
    def erindringer(self) -> Erindringer:
        """Reminders."""
        return Erindringer(self._transport)

    @cached_property
    def opslag(self) -> Opslag:
        """Lookup data: case templates, users and status lists."""
        return Opslag(self._transport)

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Call any SBSYS endpoint and get the raw JSON back.

        This is supported, documented usage, not a workaround. When you need
        an endpoint this package does not wrap yet, use it rather than waiting
        for a release — then tell us, so we can promote the endpoint to a
        proper method with models and tests.

        You give up what the resource layer provides: no parsed models, no
        validation, and payload shapes that change with SBSYS rather than with
        this package's version number.

        Args:
            method: HTTP method.
            path: Path relative to the base URL, e.g.
                ``"/api/sag/123/adviseringer"``.
            **kwargs: ``json``, ``params``, ``files``, ``data``, ``headers``
                and ``retry``, as taken by the transport. Retrying defaults to
                on for idempotent methods only.

        Returns:
            The decoded JSON body, ``None`` for an empty response, or raw text
            for a non-JSON content type.

        Raises:
            SbsysAPIError: If SBSYS returns an unsuccessful status.
        """
        return self._transport.json(method, path, **kwargs)

    def close(self) -> None:
        """Close the connection pool. The client cannot be used afterwards."""
        self._transport.close()

    def __enter__(self) -> SbsysClient:
        """Enter the context manager.

        Returns:
            This client.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the client on leaving the context manager.

        Args:
            exc_type: Type of any exception raised in the block.
            exc: The exception raised, if any.
            tb: Traceback of the exception, if any.
        """
        self.close()
