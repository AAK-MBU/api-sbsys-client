# scripts/endpoints.py
"""Look up the real endpoint paths in the SBSYS specification.

    uv run python scripts/endpoints.py status          # paths matching "status"
    uv run python scripts/endpoints.py sag --method GET
    uv run python scripts/endpoints.py                 # everything
    uv run python scripts/endpoints.py --check         # audit sbsys/resources/
    uv run python scripts/endpoints.py sag --spec specs/default.json

The specification is fetched the same way the generator fetches it, or read
from a local file with ``--spec``. Use this when a call returns 404: the guess
in ``sbsys/resources/`` is wrong, and the answer is in here.

Like the generator, this script does not import the ``sbsys`` package, so it
works even when the package itself is broken.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path
from typing import Any

import httpx

from generate_models import Fetcher, _load_env, _verify

METHODS = ("get", "post", "put", "patch", "delete")

ROOT = Path(__file__).resolve().parent.parent
RESOURCES = ROOT / "src" / "sbsys" / "resources"

_KALD = re.compile(
    r"""_t\.(?:json|request|stream)\(\s*["'](?P<method>[A-Z]+)["']\s*,\s*f?["'](?P<path>/[^"']*)["']""",
)
_PLACEHOLDER = re.compile(r"\{[^}]*\}")


def _hent_dokument(args: argparse.Namespace) -> dict[str, Any]:
    """Load the specification, from a file or from SBSYS.

    Args:
        args: Parsed command line.

    Returns:
        The decoded document.

    Raises:
        SystemExit: If the file is missing, the document cannot be retrieved,
            or it is not JSON this script can read.
    """
    if args.spec:
        if not args.spec.is_file():
            raise SystemExit(f"No such file: {args.spec}")
        content = args.spec.read_bytes()
    else:
        values = _load_env()
        if not values.get("BASE_URL"):
            raise SystemExit("Set SBSYS_BASE_URL, or pass --spec with a local file.")
        with httpx.Client(timeout=120.0, verify=_verify(values), follow_redirects=True) as client:
            content, note = Fetcher(values, client).hent(args.version)
        if content is None:
            raise SystemExit(f"Could not retrieve document {args.version!r}: {note}")

    try:
        document = json.loads(content)
    except ValueError as exc:
        raise SystemExit("The document is not JSON. Save it and inspect it manually.") from exc
    if not isinstance(document, dict):
        raise SystemExit("Unexpected document shape.")
    return document


def _operationer(document: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Flatten the document into one row per operation.

    Args:
        document: The decoded specification.

    Returns:
        Triples of method, path and a short summary or operation id.
    """
    raekker: list[tuple[str, str, str]] = []
    for path, item in (document.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method in METHODS:
            operation = item.get(method)
            if not isinstance(operation, dict):
                continue
            beskrivelse = (
                operation.get("summary")
                or operation.get("operationId")
                or (operation.get("description") or "").split("\n")[0]
            )
            raekker.append((method.upper(), path, beskrivelse[:70]))
    return sorted(raekker, key=lambda r: (r[1], r[0]))


def _normaliser(path: str) -> str:
    """Reduce a path to a shape that can be compared across naming styles.

    ``/api/sag/{sags_id}/erindringer`` and ``/api/sag/{id}/erindringer`` are the
    same endpoint, so placeholder names are stripped and case is ignored.

    Args:
        path: A path from either the source or the specification.

    Returns:
        The comparable form.
    """
    return _PLACEHOLDER.sub("{}", path).rstrip("/").lower()


def _ord(path: str) -> set[str]:
    """Split a path into the words worth matching on.

    Args:
        path: A normalised path.

    Returns:
        Its segments, minus placeholders and the generic ``api`` prefix.
    """
    return {d for d in path.strip("/").split("/") if d not in ("api", "{}") and len(d) > 2}


def _forslag(sti: str, kendte: dict[str, str]) -> list[str]:
    """Rank the specification paths most likely to be what was meant.

    Word overlap beats string similarity here: ``/api/sag/{}/erindringer`` and
    ``/api/erindring/sag/{}`` are nowhere near each other as strings, but share
    two concepts. Words match on a common prefix, so ``erindring`` and
    ``erindringer`` count as the same.

    Args:
        sti: The normalised path from the source.
        kendte: Normalised specification paths mapped to their original form.

    Returns:
        Up to three candidate paths, best first.
    """
    soegt = _ord(sti)
    scoret: list[tuple[int, str]] = []
    for normaliseret in kendte:
        overlap = sum(
            1
            for a in soegt
            for b in _ord(normaliseret)
            if a.startswith(b[:5]) or b.startswith(a[:5])
        )
        if overlap:
            scoret.append((overlap, normaliseret))

    if scoret:
        scoret.sort(key=lambda s: (-s[0], len(s[1])))
        return [n for _, n in scoret[:3]]
    return difflib.get_close_matches(sti, list(kendte), n=2, cutoff=0.7)


def _kald_i_kildekoden() -> list[tuple[str, str, str]]:
    """Find every endpoint the resource layer calls.

    Returns:
        Triples of module name, HTTP method and path, in file order.
    """
    fundet: list[tuple[str, str, str]] = []
    for fil in sorted(RESOURCES.glob("*.py")):
        for match in _KALD.finditer(fil.read_text(encoding="utf-8")):
            fundet.append((fil.stem, match.group("method"), match.group("path")))
    return fundet


def _revision(document: dict[str, Any]) -> int:
    """Compare every path the resource layer uses against the specification.

    Args:
        document: The decoded specification.

    Returns:
        ``0`` if every call matched, ``1`` otherwise.
    """
    spec = _operationer(document)
    kendte = {(m, _normaliser(p)) for m, p, _ in spec}
    alle_stier = sorted({p for _, p, _ in spec})
    normaliserede = {_normaliser(p): p for p in alle_stier}

    kald = _kald_i_kildekoden()
    if not kald:
        raise SystemExit(f"Found no endpoint calls under {RESOURCES}.")

    fejl = 0
    for modul, metode, sti in kald:
        if (metode, _normaliser(sti)) in kendte:
            print(f"  ok      {modul:<16} {metode:<6} {sti}")  # noqa: T201
            continue

        fejl += 1
        print(f"  MISSING {modul:<16} {metode:<6} {sti}")  # noqa: T201

        if _normaliser(sti) in normaliserede:
            rigtig = normaliserede[_normaliser(sti)]
            metoder = sorted({m for m, p, _ in spec if _normaliser(p) == _normaliser(sti)})
            print(f"          path exists, but only as: {', '.join(metoder)} {rigtig}")  # noqa: T201
            continue

        for forslag in _forslag(_normaliser(sti), normaliserede):
            metoder = sorted({m for m, p, _ in spec if _normaliser(p) == forslag})
            print(f"          did you mean: {', '.join(metoder)} {normaliserede[forslag]}")  # noqa: T201

    print(f"\n{len(kald) - fejl}/{len(kald)} calls found in the specification")  # noqa: T201
    return 1 if fejl else 0


def main() -> None:
    """Print the endpoints matching the filter.

    Raises:
        SystemExit: If the document could not be loaded.
    """
    parser = argparse.ArgumentParser(
        description="List SBSYS endpoints from the OpenAPI specification.",
    )
    parser.add_argument("filter", nargs="?", default="", help="Substring to match in the path.")
    parser.add_argument("--method", help="Only this HTTP method, e.g. GET.")
    parser.add_argument("--version", default="default", help="Document to read. Default: default.")
    parser.add_argument("--spec", type=Path, help="Read a local file instead of fetching.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Audit every path used in sbsys/resources/ against the specification.",
    )
    args = parser.parse_args()

    document = _hent_dokument(args)

    if args.check:
        raise SystemExit(_revision(document))

    raekker = _operationer(document)
    if args.filter:
        needle = args.filter.lower()
        raekker = [r for r in raekker if needle in r[1].lower() or needle in r[2].lower()]
    if args.method:
        raekker = [r for r in raekker if r[0] == args.method.upper()]

    if not raekker:
        print(f"No endpoints matched {args.filter!r}.")  # noqa: T201
        return

    bredde = max(len(r[1]) for r in raekker)
    for method, path, beskrivelse in raekker:
        print(f"{method:<7} {path:<{bredde}}  {beskrivelse}")  # noqa: T201
    print(f"\n{len(raekker)} endpoints")  # noqa: T201


if __name__ == "__main__":
    main()
