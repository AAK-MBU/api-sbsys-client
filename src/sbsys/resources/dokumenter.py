# src/sbsys/resources/dokumenter.py
"""Documents: lookup, download and upload."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from sbsys.errors import error_for_status
from sbsys.models.dokument import Dokument
from sbsys.resources._base import Resource


class Dokumenter(Resource):
    """Document operations. Reached as ``client.dokumenter``.

    Note the distinction between a document and a file: a document is a
    container that may hold several files, and downloads address a file id,
    not a document id.
    """

    def hent(self, dokument_id: int) -> Dokument:
        """Fetch a document and its file metadata.

        Args:
            dokument_id: Document id.

        Returns:
            The document, including the list of files. File contents are not
            included — use :meth:`download` for those.

        Raises:
            SbsysNotFoundError: If no document has that id.
        """
        return Dokument.model_validate(self._t.json("GET", f"/api/dokument/{dokument_id}"))

    def hent_paa_sag(self, sags_id: int) -> list[Dokument]:
        """List the documents on a case.

        Args:
            sags_id: Internal case id.

        Returns:
            Every document on the case, or an empty list if it has none. This
            endpoint is not paged, so a case with very many documents returns
            them all in one response.
        """
        data = self._t.json("GET", f"/api/sag/{sags_id}/dokumenter")
        rows = data.get("Results", data) if isinstance(data, dict) else data
        return [Dokument.model_validate(r) for r in rows or []]

    def download(self, fil_id: int) -> Iterator[bytes]:
        """Stream the contents of a file.

        The file is never held in memory in full, so this is safe for large
        attachments. Consume the iterator before doing anything else — the
        connection stays open until it is exhausted.

        Args:
            fil_id: File id, taken from ``Dokument.filer``. Not a document id.

        Yields:
            Chunks of the file, in order.

        Raises:
            SbsysNotFoundError: If no file has that id.
            SbsysAPIError: On any other unsuccessful status.
        """
        with self._t.stream("GET", f"/api/fil/{fil_id}") as response:
            if not response.is_success:
                response.read()
                raise error_for_status(
                    response.status_code, "GET", f"/api/fil/{fil_id}", response.text
                )
            yield from response.iter_bytes()

    def download_til(self, fil_id: int, sti: Path | str) -> Path:
        """Download a file straight to disk.

        Args:
            fil_id: File id.
            sti: Destination path. Overwritten if it exists. The parent
                directory must already exist.

        Returns:
            The path written to.

        Raises:
            SbsysNotFoundError: If no file has that id.
            OSError: If the destination cannot be written.
        """
        sti = Path(sti)
        with sti.open("wb") as fh:
            for chunk in self.download(fil_id):
                fh.write(chunk)
        return sti

    def upload(self, sags_id: int, sti: Path | str, *, navn: str | None = None) -> Dokument:
        """Upload a file to a case, journalising it as a new document.

        Never retried: a replayed upload would leave duplicate documents on
        the case.

        Args:
            sags_id: Internal case id.
            sti: Path to the file to upload.
            navn: Document name in SBSYS. Defaults to the file name on disk.

        Returns:
            The created document.

        Raises:
            SbsysAPIError: If SBSYS rejects the upload, e.g. on a blocked file
                type or a size limit.
            OSError: If the file cannot be read.
        """
        sti = Path(sti)
        metadata = {"SagID": sags_id, "DokumentNavn": navn or sti.name}
        with sti.open("rb") as fh:
            data = self._t.json(
                "POST",
                "/api/dokument/journaliser",
                files={"file": (sti.name, fh)},
                data={"json": json.dumps(metadata)},
                retry=False,
            )
        return Dokument.model_validate(data)
