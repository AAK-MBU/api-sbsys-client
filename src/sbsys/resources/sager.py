# src/sbsys/resources/sager.py
"""Cases: lookup, search, creation and updates."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sbsys._transport.pagination import DEFAULT_PAGE_SIZE, paginate
from sbsys.errors import SbsysValidationError
from sbsys.models.part import PartType
from sbsys.models.sag import Sag
from sbsys.resources._base import Resource, normaliser_cpr


class Sager(Resource):
    """Operations on cases. Reached as ``client.sager``."""

    def hent(self, sags_id: int) -> Sag:
        """Fetch a single case.

        Args:
            sags_id: Internal case id.

        Returns:
            The case.

        Raises:
            SbsysNotFoundError: If no case has that id.
        """
        return Sag.model_validate(self._t.json("GET", f"/api/sag/{sags_id}"))

    def soeg(
        self,
        kriterier: dict[str, Any] | None = None,
        *,
        max_antal: int | None = None,
        side_stoerrelse: int = DEFAULT_PAGE_SIZE,
    ) -> Iterator[Sag]:
        """Search for cases.

        Criteria are passed to ``/api/sag/search`` unchanged, so every SBSYS
        search field is available without this package having to wrap them one
        by one. Results are fetched lazily, one page at a time — a search
        matching thousands of cases costs one request until you consume past
        the first page.

        Args:
            kriterier: Search body as SBSYS expects it, e.g.
                ``{"SagsTitel": "Underretning"}``. Paging fields are added
                automatically and must not be included.
            max_antal: Stop after this many cases. ``None`` means no limit.
            side_stoerrelse: Cases fetched per request.

        Yields:
            Matching cases, in the order SBSYS returned them.
        """
        body = dict(kriterier or {})

        def fetch(side: int, stoerrelse: int) -> dict[str, Any]:
            """Fetch one page of search results.

            Args:
                side: One-based page number.
                stoerrelse: Rows to request.

            Returns:
                The decoded response body, or an empty result set if SBSYS
                answered with something other than a JSON object.
            """
            payload = {**body, "PageNumber": side, "PageSize": stoerrelse}
            result = self._t.json("POST", "/api/sag/search", json=payload, retry=True)
            return result if isinstance(result, dict) else {"Results": []}

        return paginate(fetch, Sag.model_validate, page_size=side_stoerrelse, max_items=max_antal)

    def soeg_paa_cpr(self, cpr: str, **kwargs: Any) -> Iterator[Sag]:
        """Search for cases where a citizen is the primary party.

        Cases where the citizen is only a secondary party are not returned.
        Use :meth:`soeg` with your own criteria for that.

        Args:
            cpr: CPR number, with or without a hyphen.
            **kwargs: Passed through to :meth:`soeg`.

        Yields:
            Matching cases.

        Raises:
            SbsysValidationError: If the CPR number is malformed. Raised on
                first iteration, not at call time, because this is a generator.
        """
        return self.soeg({"PrimaerPerson": {"CprNummer": normaliser_cpr(cpr)}}, **kwargs)

    def opret_fra_skabelon(
        self,
        *,
        titel: str,
        skabelon_id: int,
        sagsbehandler_id: int,
        part_id: int,
        part_type: PartType = PartType.PERSON,
    ) -> Sag:
        """Create a case from a case template.

        The party is set as both the primary party and the only initial party.
        Add further parties afterwards with :meth:`tilfoej_part`.

        This request is never retried. A replayed creation produces duplicate
        cases, and a timeout does not tell you whether the case was created —
        search before creating again.

        Args:
            titel: Case title. Must not be blank.
            skabelon_id: Template id, from ``client.opslag.sagsskabeloner()``.
            sagsbehandler_id: Caseworker id, from
                ``client.opslag.bruger_id_for_initialer()``.
            part_id: SBSYS party id — not a CPR or CVR number. Look it up with
                ``client.parter.hent_person()``.
            part_type: Whether the party is a person or a company.

        Returns:
            The created case.

        Raises:
            SbsysValidationError: If the title is blank.
            SbsysAPIError: If SBSYS rejects the creation.
        """
        if not titel.strip():
            raise SbsysValidationError("Case title must not be blank")

        part = {"PartId": part_id, "PartType": str(part_type)}
        body = {
            "SagsTitel": titel,
            "SkabelonId": skabelon_id,
            "SagsBehandlerID": sagsbehandler_id,
            "PrimaryPart": part,
            "Parts": [part],
        }
        return Sag.model_validate(self._t.json("POST", "/api/sag/template", json=body, retry=False))

    def opdater(self, sags_id: int, aendringer: dict[str, Any]) -> Sag:
        """Update fields on a case.

        SBSYS only offers a full ``PUT`` of the case, so the case is fetched,
        the changes are laid over it (top-level keys only), and the whole
        object is sent back. Nested values such as ``Sagsstatus`` replace the
        existing object entirely, so pass them whole.

        Not retried. Another change made between the fetch and the ``PUT`` is
        overwritten.

        Args:
            sags_id: Internal case id.
            aendringer: Fields to change, keyed by SBSYS' own field names.

        Returns:
            The updated case as SBSYS returns it.

        Raises:
            SbsysValidationError: If no changes were given.
            SbsysConflictError: If the case cannot be changed, e.g. because it
                is closed.
        """
        if not aendringer:
            raise SbsysValidationError("No changes given")
        sag = dict(self._t.json("GET", f"/api/sag/{sags_id}"))
        sag.update(aendringer)
        return Sag.model_validate(self._t.json("PUT", f"/api/sag/{sags_id}", json=sag, retry=False))

    def tilfoej_part(self, sags_id: int, part_id: int, part_type: PartType) -> None:
        """Attach another party to a case.

        Args:
            sags_id: Internal case id.
            part_id: SBSYS party id.
            part_type: Whether the party is a person or a company.

        Raises:
            SbsysAPIError: If SBSYS rejects the request, including when the
                party is already attached.
        """
        self._t.request(
            "POST",
            f"/api/sag/{sags_id}/part",
            json={"PartId": part_id, "PartType": str(part_type)},
            retry=False,
        )
