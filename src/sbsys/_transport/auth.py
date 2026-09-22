# src/sbsys/_transport/auth.py
"""OAuth2 authentication against the SBSYS identity provider."""

from __future__ import annotations

import threading
import time
from collections.abc import Generator

import httpx

from sbsys.config import SbsysSettings
from sbsys.errors import SbsysAuthError


class SbsysAuth(httpx.Auth):
    """Obtains and refreshes access tokens using the password grant.

    Implemented as an :class:`httpx.Auth` so token handling lives in exactly
    one place and the resource layer never has to think about it. Tokens are
    cached until shortly before they expire, a lock makes sure concurrent
    requests trigger only one refresh, and a token rejected mid-flight is
    refreshed once and the request replayed.

    Token requests go through a separate :class:`httpx.Client` so they do not
    recurse back into this auth flow.
    """

    def __init__(self, settings: SbsysSettings, token_client: httpx.Client | None = None) -> None:
        """Prepare the auth flow. No network call is made until first use.

        Args:
            settings: Connection settings, including the credentials and the
                leeway applied before token expiry.
            token_client: Client used for token requests. Injected by tests;
                production code leaves it out and gets one configured from
                ``settings``.
        """
        self._settings = settings
        self._lock = threading.Lock()
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._client = token_client or httpx.Client(
            timeout=settings.timeout,
            verify=settings.verify,
        )

    def sync_auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        """Attach a bearer token, and retry once if the token is rejected.

        Called by ``httpx`` for every outgoing request.

        Args:
            request: The request about to be sent.

        Yields:
            The request with an ``Authorization`` header. If SBSYS answers
            ``401``, the token is force-refreshed and the request is yielded a
            second time.
        """
        request.headers["Authorization"] = f"Bearer {self._valid_token()}"
        response = yield request

        if response.status_code == 401:
            response.read()
            request.headers["Authorization"] = f"Bearer {self._valid_token(force=True)}"
            yield request

    def _valid_token(self, *, force: bool = False) -> str:
        """Return a usable access token, refreshing it if necessary.

        Args:
            force: Refresh even if the cached token still looks valid. Used
                after SBSYS has rejected a token we believed was good.

        Returns:
            The access token.

        Raises:
            SbsysAuthError: If a token could not be obtained.
        """
        with self._lock:
            expired = time.monotonic() >= self._expires_at - self._settings.token_leeway
            if force or self._token is None or expired:
                self._refresh()
            assert self._token is not None
            return self._token

    def _refresh(self) -> None:
        """Fetch a new access token. The caller must hold the lock.

        Raises:
            SbsysAuthError: If the token endpoint is unreachable, answers with
                a non-200 status, or returns a body without an access token.
        """
        settings = self._settings
        try:
            response = self._client.post(
                settings.token_url,
                data={
                    "grant_type": "password",
                    "client_id": settings.client_id,
                    "client_secret": settings.client_secret.get_secret_value(),
                    "username": settings.username,
                    "password": settings.password.get_secret_value(),
                },
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise SbsysAuthError(0, "POST", settings.token_url, str(exc)) from exc

        if response.status_code != 200:
            raise SbsysAuthError(response.status_code, "POST", settings.token_url, response.text)

        try:
            payload = response.json()
            token = payload["access_token"]
            expires_in = int(payload.get("expires_in", 3600))
        except (ValueError, KeyError, TypeError) as exc:
            raise SbsysAuthError(
                response.status_code,
                "POST",
                settings.token_url,
                "Unexpected response from token endpoint",
            ) from exc

        self._token = token
        self._expires_at = time.monotonic() + expires_in

    def close(self) -> None:
        """Close the client used for token requests."""
        self._client.close()
