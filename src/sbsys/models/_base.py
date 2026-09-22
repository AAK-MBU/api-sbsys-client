# src/sbsys/models/_base.py
"""Shared base class for every model parsed from SBSYS."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_pascal


class SbsysModel(BaseModel):
    """Base class for everything we parse out of SBSYS.

    Three configuration choices carry most of the weight:

    ``alias_generator=to_pascal``
        Matches SBSYS' PascalCase JSON without an explicit ``Field(alias=...)``
        on every attribute. Irregular names such as ``CPRnummer`` and
        ``SagsTitel`` are overridden where they occur.

    ``extra="allow"``
        A new field in an SBSYS release does not break parsing. Unmodelled
        values are kept and reachable through :meth:`raw`.

    ``frozen=True``
        Responses are immutable, so nothing can accidentally mutate an object
        handed to it. Build request payloads as plain dicts instead.
    """

    model_config = ConfigDict(
        alias_generator=to_pascal,
        populate_by_name=True,
        extra="allow",
        frozen=True,
    )

    def raw(self) -> dict[str, Any]:
        """Return the response as SBSYS sent it.

        Returns:
            A dict keyed by SBSYS' own field names, including any fields this
            package does not model. Useful when an endpoint returns something
            not yet covered, and when reporting an unexpected payload.
        """
        return self.model_dump(by_alias=True)
