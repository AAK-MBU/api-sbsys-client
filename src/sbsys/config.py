# src/sbsys/config.py
"""Connection settings for the SBSYS client."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE_VAR = "SBSYS_ENV_FILE"
"""Environment variable holding an explicit path to the ``.env`` file."""


def find_env_file() -> Path | str:
    """Locate the ``.env`` file to read settings from.

    ``SBSYS_ENV_FILE`` wins if it is set, which is how a service or scheduled
    job points at a file outside its working directory. Otherwise the current
    directory and each of its parents are searched, so running a script from a
    subdirectory of the project still finds the project's ``.env``.

    Resolved at instantiation rather than at import, so a process that changes
    directory after importing still gets the right answer.

    Returns:
        Path to the file that was found, the configured override whether or
        not it exists, or the literal ``".env"`` when nothing was found — which
        leaves pydantic-settings to report the missing fields.
    """
    override = os.environ.get(ENV_FILE_VAR)
    if override:
        return override

    current = Path.cwd().resolve()
    for directory in (current, *current.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return ".env"


class SbsysSettings(BaseSettings):
    """Everything needed to connect to one SBSYS environment.

    Values are read from ``SBSYS_``-prefixed environment variables or a
    ``.env`` file, and any of them can be overridden in code. Real environment
    variables win over the file.

    The ``.env`` file is located by :func:`find_env_file`: set
    ``SBSYS_ENV_FILE`` to an absolute path, or let it be found by searching
    upwards from the working directory. Pass ``_env_file`` to override for one
    instance.

    Construct settings explicitly when a single process has to talk to more
    than one environment::

        test = SbsysSettings(base_url="https://sbsys.test.dk", ...)
        prod = SbsysSettings(base_url="https://sbsys.prod.dk", ...)

    Secrets are held as :class:`~pydantic.SecretStr`, so an accidental
    ``print`` or traceback shows ``**********`` instead of the credential.

    Attributes:
        base_url: Root URL of the SBSYS web API. A trailing slash is stripped.
        token_url: OAuth2 token endpoint. A trailing slash is stripped.
        client_id: OAuth2 client id.
        client_secret: OAuth2 client secret.
        username: Service account user name.
        password: Service account password.
        timeout: Per-request timeout in seconds.
        max_retries: Total attempts for retryable requests. ``1`` disables
            retrying. Only ever applied to idempotent requests.
        verify: TLS verification: ``True``, ``False``, or a path to a CA
            bundle. Never use ``False`` in production — every request carries
            personal data. Point it at the municipality's own CA bundle when
            the environment uses an internal certificate.
        token_leeway: Seconds before expiry at which the access token is
            refreshed proactively, so a token cannot expire mid-flight.
    """

    model_config = SettingsConfigDict(
        env_prefix="SBSYS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def __init__(self, **values: Any) -> None:
        """Build the settings, discovering the ``.env`` file if none was given.

        Args:
            **values: Field values, plus any of pydantic-settings' own
                underscore-prefixed arguments such as ``_env_file``.
        """
        values.setdefault("_env_file", find_env_file())
        super().__init__(**values)

    base_url: str
    token_url: str
    client_id: str
    client_secret: SecretStr
    username: str
    password: SecretStr

    timeout: float = 30.0
    max_retries: int = 3
    verify: bool | str = True
    token_leeway: int = 60

    @field_validator("base_url", "token_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        """Normalise URLs so paths can be joined without doubling slashes.

        Args:
            value: The configured URL.

        Returns:
            The URL without a trailing slash.
        """
        return value.rstrip("/")
