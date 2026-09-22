# src/sbsys/_transport/http.py
"""HTTP layer: retrying, error translation and redacted logging.

Knows nothing about cases, documents or any other SBSYS concept.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from sbsys._transport.auth import SbsysAuth
from sbsys._transport.redact import redact
from sbsys.config import SbsysSettings
from sbsys.errors import SbsysRateLimitError, SbsysServerError, error_for_status

logger = logging.getLogger("sbsys")

_IDEMPOTENT = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})


class Transport:
    """Thin wrapper around :class:`httpx.Client`.

    Owns authentication, timeouts, retrying, translation of HTTP failures into
    :mod:`sbsys.errors`, and redacted logging. The resource layer only ever
    calls :meth:`request`, :meth:`json` and :meth:`stream`.

    Safe to share between threads: ``httpx.Client`` is thread-safe and token
    refresh is guarded by a lock.
    """

    def __init__(self, settings: SbsysSettings, client: httpx.Client | None = None) -> None:
        """Build the transport and its connection pool.

        Args:
            settings: Connection settings.
            client: Pre-configured HTTP client. Injected by tests; production
                code leaves it out and gets one wired up from ``settings``.
        """
        self._settings = settings
        self._auth = SbsysAuth(settings)
        self._client = client or httpx.Client(
            base_url=settings.base_url,
            timeout=settings.timeout,
            verify=settings.verify,
            auth=self._auth,
            headers={"Accept": "application/json"},
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        retry: bool | None = None,
    ) -> httpx.Response:
        """Send a request and return the response, or raise.

        Retrying defaults to on for idempotent methods and off for everything
        else, because replaying a ``POST`` that creates a case produces
        duplicates. Callers that know better can override it either way: pass
        ``retry=True`` for a search endpoint that happens to use ``POST``, or
        ``retry=False`` for a non-idempotent ``PUT``.

        Args:
            method: HTTP method. Case-insensitive.
            path: Path relative to the configured base URL, or an absolute URL.
            json: Body to serialise as JSON.
            params: Query string parameters.
            files: Multipart file payload, for document upload.
            data: Form-encoded body.
            headers: Extra request headers.
            retry: Override the default retry decision for this request.

        Returns:
            The successful response.

        Raises:
            SbsysAPIError: If SBSYS returns an unsuccessful status, after any
                retries have been exhausted. The concrete subclass depends on
                the status code.
            httpx.TransportError: If the request never completed and retries
                did not help.
        """
        method = method.upper()
        should_retry = method in _IDEMPOTENT if retry is None else retry
        attempts = self._settings.max_retries if should_retry else 1
        request_id = uuid.uuid4().hex[:12]

        retrying = Retrying(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential_jitter(initial=0.5, max=8.0),
            retry=retry_if_exception_type(
                (SbsysServerError, SbsysRateLimitError, httpx.TransportError)
            ),
            reraise=True,
        )

        for attempt in retrying:
            with attempt:
                return self._send(
                    method,
                    path,
                    json=json,
                    params=params,
                    files=files,
                    data=data,
                    headers=headers,
                    request_id=request_id,
                )
        raise AssertionError("unreachable")  # pragma: no cover

    def json(self, method: str, path: str, **kwargs: Any) -> Any:
        """Send a request and return the parsed response body.

        Args:
            method: HTTP method.
            path: Path relative to the base URL, or an absolute URL.
            **kwargs: Passed through to :meth:`request`.

        Returns:
            The decoded JSON body, ``None`` for an empty response, or the raw
            text when SBSYS answers with a non-JSON content type — which it
            does for some write endpoints.

        Raises:
            SbsysAPIError: If SBSYS returns an unsuccessful status.
        """
        response = self.request(method, path, **kwargs)
        if not response.content:
            return None
        if "json" not in response.headers.get("content-type", ""):
            return response.text
        return response.json()

    def stream(self, method: str, path: str, **kwargs: Any) -> Any:
        """Open a streaming response, for document download.

        The response is not read into memory, so arbitrarily large files can
        be written straight to disk. Unlike :meth:`request`, the status is not
        checked here — the caller decides when to read the body.

        Args:
            method: HTTP method.
            path: Path relative to the base URL, or an absolute URL.
            **kwargs: Passed through to ``httpx.Client.stream``.

        Returns:
            A context manager yielding the streaming response.
        """
        return self._client.stream(method, self._url(path), **kwargs)

    def close(self) -> None:
        """Close the connection pool and the token client."""
        self._client.close()
        self._auth.close()

    @staticmethod
    def _url(path: str) -> str:
        """Normalise a path so it joins cleanly onto the base URL.

        Args:
            path: A relative path, with or without a leading slash, or an
                absolute URL.

        Returns:
            The absolute URL unchanged, or the path with exactly one leading
            slash.
        """
        return path if path.startswith("http") else "/" + path.lstrip("/")

    def _send(
        self,
        method: str,
        path: str,
        *,
        json: Any,
        params: dict[str, Any] | None,
        files: dict[str, Any] | None,
        data: dict[str, Any] | None,
        headers: dict[str, str] | None,
        request_id: str,
    ) -> httpx.Response:
        """Perform a single attempt, without retrying.

        Args:
            method: HTTP method, already upper-cased.
            path: Request path or absolute URL.
            json: Body to serialise as JSON.
            params: Query string parameters.
            files: Multipart file payload.
            data: Form-encoded body.
            headers: Extra request headers.
            request_id: Correlation id shared by every attempt of one logical
                request, so retries can be tied together in the log.

        Returns:
            The response, if it was successful.

        Raises:
            SbsysAPIError: If the status was unsuccessful. The body is
                redacted and truncated before being attached.
        """
        url = self._url(path)
        logger.debug("sbsys %s %s [%s]", method, url, request_id)

        response = self._client.request(
            method,
            url,
            json=json,
            params=params,
            files=files,
            data=data,
            headers=headers,
        )

        if response.is_success:
            return response

        body = redact(response.text)[:2000] if response.text else None
        logger.warning("sbsys %s %s [%s] -> %s", method, url, request_id, response.status_code)
        raise error_for_status(response.status_code, method, url, body, request_id)
