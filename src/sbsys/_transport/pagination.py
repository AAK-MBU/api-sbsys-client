# src/sbsys/_transport/pagination.py
"""Pagination of the SBSYS search endpoints.

The ``/search`` endpoints take page number and page size in the request body
and answer with ``{"Results": [...], "TotalNumberOfResults": n}``. The exact
field names vary between API versions, so they can be overridden.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")

DEFAULT_PAGE_SIZE = 100
"""Rows fetched per request when the caller does not say otherwise."""


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    """One page of a search result.

    Attributes:
        items: The rows on this page.
        page_number: One-based index of this page.
        page_size: Rows requested per page.
        total: Total matches across all pages, or ``None`` when SBSYS did not
            report a total.
    """

    items: list[T]
    page_number: int
    page_size: int
    total: int | None

    @property
    def has_more(self) -> bool:
        """Whether another page is likely to exist.

        Returns:
            ``True`` if more rows are expected. When SBSYS reports a total,
            the answer is exact. Without one, a full page is taken to mean
            there may be more, which costs one extra empty request when the
            result happens to be an exact multiple of the page size.
        """
        if self.total is None:
            return len(self.items) == self.page_size
        return self.page_number * self.page_size < self.total


def paginate(
    fetch: Callable[[int, int], dict[str, Any]],
    parse: Callable[[dict[str, Any]], T],
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_items: int | None = None,
    results_key: str = "Results",
    total_key: str = "TotalNumberOfResults",
) -> Iterator[T]:
    """Walk a paged search endpoint, yielding one parsed item at a time.

    Pages are fetched lazily: stop consuming after three items and only the
    first page is ever requested. That matters for case searches, which can
    match tens of thousands of rows.

    Args:
        fetch: Called with ``(page_number, page_size)`` and returns the decoded
            response body for that page.
        parse: Converts a single row into the model type to yield.
        page_size: Rows per request.
        max_items: Stop after this many items. ``None`` means no limit.
        results_key: Body key holding the rows.
        total_key: Body key holding the total match count.

    Yields:
        Parsed items, in the order SBSYS returned them.
    """
    page_number = 1
    yielded = 0

    while True:
        payload = fetch(page_number, page_size)
        rows = payload.get(results_key) or []
        total = payload.get(total_key)

        for row in rows:
            yield parse(row)
            yielded += 1
            if max_items is not None and yielded >= max_items:
                return

        page = Page(items=rows, page_number=page_number, page_size=page_size, total=total)
        if not rows or not page.has_more:
            return
        page_number += 1
