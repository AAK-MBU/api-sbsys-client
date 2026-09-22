# scripts/generate_models.py
"""Generate Pydantic models from the SBSYS OpenAPI specifications.

SBSYS exposes one document per API version rather than a single spec, so this
script discovers which ones exist and generates a subpackage for each::

    uv run python scripts/generate_models.py --list      # inventory, generates nothing
    uv run python scripts/generate_models.py             # every version found
    uv run python scripts/generate_models.py v10 v1      # only these
    uv run python scripts/generate_models.py --spec swagger.json --name v10

Output lands in ``src/sbsys/models/generated/<version>.py`` — one module per
version — and must be committed. Never edit the output by hand — change this generator, or the
curated models in ``sbsys/models/``, instead.

Settings are read from the environment or a ``.env`` file, the same variables
the client uses. If the endpoints require authentication, those credentials are
used to obtain a token.

This script deliberately does not import the ``sbsys`` package. A code
generator that only runs when the package already imports cleanly is backwards:
a packaging problem would surface here as a confusing traceback, and
regenerating models is exactly what you might be doing to fix a broken package.
The small amount of duplicated configuration handling is the price of that.
"""

from __future__ import annotations

import argparse
import json
import keyword
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "src" / "sbsys" / "models" / "generated"

VERSIONS = ("default", *(f"v{n}" for n in range(1, 32)))
"""Document names SBSYS may expose, in the order they are probed."""

PATH_TEMPLATES = ("/docs/{version}", "/swagger/docs/{version}", "/swagger/{version}/swagger.json")
"""Layouts to try. The first one that answers is used for every other version."""

OPENAPI_SCOPES = ("--openapi-scopes", "schemas", "paths", "parameters")
"""Needed for OpenAPI 3 documents that define models inline under ``paths``."""

REQUIRED = ("BASE_URL", "TOKEN_URL", "CLIENT_ID", "CLIENT_SECRET", "USERNAME", "PASSWORD")
"""Settings needed to reach an authenticated endpoint, without the prefix."""

PRESERVED_DOC = '''# src/sbsys/models/generated/__init__.py
"""Generated models from the SBSYS OpenAPI specifications. Do not hand-edit.

One module per API version, because SBSYS publishes one document per version
rather than a single specification::

    from sbsys.models.generated.v10 import SagDto

Regenerate with::

    uv run python scripts/generate_models.py

The output is committed, so builds are reproducible and the diff shows exactly
what changed when SBSYS was upgraded. The directory is excluded from ruff,
mypy and coverage.

Do not use these types in consuming projects: their names and shapes track the
specifications and will change without a major version bump. They exist so we
have something to check against when building the curated models in
:mod:`sbsys.models`.
"""
'''


def _valid_name(name: str) -> str:
    """Check that a version name can be used as a Python module name.

    Catching this here beats generating ``3d.py`` or ``class.py`` and having
    the import fail much later with no clue where the name came from.

    Args:
        name: Proposed version, and therefore module, name.

    Returns:
        The name unchanged.

    Raises:
        SystemExit: If the name is not a usable module name.
    """
    if not name.isidentifier() or keyword.iskeyword(name):
        raise SystemExit(
            f"{name!r} cannot be a module name. Use a plain identifier such as v10 or default."
        )
    return name


def _find_env_file() -> Path | None:
    """Locate the ``.env`` file, mirroring what :mod:`sbsys.config` does.

    ``SBSYS_ENV_FILE`` wins if set. Otherwise the working directory and each of
    its parents are searched, then the project root as a fallback for the case
    where the script is invoked from somewhere else entirely.

    Returns:
        Path to the file, or ``None`` if there is none.
    """
    override = os.environ.get("SBSYS_ENV_FILE")
    if override:
        return Path(override)

    current = Path.cwd().resolve()
    for directory in (current, *current.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate

    fallback = ROOT / ".env"
    return fallback if fallback.is_file() else None


def _load_env() -> dict[str, str]:
    """Read SBSYS settings from the environment, topped up from ``.env``.

    Real environment variables win over the file, matching the client. The
    parser handles ``KEY=value``, comments, blank lines, ``export`` prefixes
    and surrounding quotes — enough for a credentials file, and not a
    general-purpose dotenv implementation.

    Returns:
        Settings keyed without the ``SBSYS_`` prefix, e.g. ``{"BASE_URL": ...}``.
    """
    values = {k[6:]: v for k, v in os.environ.items() if k.startswith("SBSYS_")}

    env_file = _find_env_file()
    if env_file and env_file.is_file():
        for raw in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip().removeprefix("export ").strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key.startswith("SBSYS_"):
                values.setdefault(key[6:], value.strip().strip("\"'"))

    return values


def _verify(values: dict[str, str]) -> bool | str:
    """Interpret the ``SBSYS_VERIFY`` setting for httpx.

    Args:
        values: Settings as returned by :func:`_load_env`.

    Returns:
        ``True``, ``False``, or a path to a CA bundle.
    """
    raw = values.get("VERIFY", "true").strip()
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    return raw


def _token(values: dict[str, str], client: httpx.Client) -> str:
    """Obtain an access token using the password grant.

    Args:
        values: Settings as returned by :func:`_load_env`.
        client: HTTP client to use.

    Returns:
        The access token.

    Raises:
        SystemExit: If the token endpoint rejects the request or answers with
            something that is not a token.
    """
    response = client.post(
        values["TOKEN_URL"].rstrip("/"),
        data={
            "grant_type": "password",
            "client_id": values["CLIENT_ID"],
            "client_secret": values["CLIENT_SECRET"],
            "username": values["USERNAME"],
            "password": values["PASSWORD"],
        },
        headers={"Accept": "application/json"},
    )
    if response.status_code != 200:
        raise SystemExit(
            f"The endpoint requires a token, and the token endpoint returned "
            f"{response.status_code}: {response.text[:300]}"
        )
    try:
        return str(response.json()["access_token"])
    except (ValueError, KeyError, TypeError) as exc:
        raise SystemExit("Token endpoint returned no access_token.") from exc


class Fetcher:
    """Retrieves specification documents, obtaining a token only if asked for one."""

    def __init__(self, values: dict[str, str], client: httpx.Client) -> None:
        """Bind to settings and a client.

        Args:
            values: Settings as returned by :func:`_load_env`.
            client: HTTP client to use for every request.
        """
        self._values = values
        self._client = client
        self._base = values["BASE_URL"].rstrip("/")
        self._bearer: str | None = None
        self._template: str | None = None

    def urls(self, version: str) -> list[str]:
        """Candidate URLs for one document.

        Once a layout has worked, only that one is tried for the remaining
        versions, so discovery does not make three requests per version.

        Args:
            version: Document name, e.g. ``"v10"``.

        Returns:
            URLs to try, in order.
        """
        templates = [self._template] if self._template else list(PATH_TEMPLATES)
        return [self._base + t.format(version=version) for t in templates if t]

    def hent(self, version: str) -> tuple[bytes | None, str]:
        """Retrieve one document.

        Args:
            version: Document name, e.g. ``"v10"``.

        Returns:
            A pair of the document bytes and a short status note. The bytes are
            ``None`` when the document does not exist or could not be read.
        """
        note = "not found"
        for url in self.urls(version):
            try:
                response = self._client.get(url)
                if response.status_code in (401, 403):
                    self._bearer = self._bearer or _token(self._values, self._client)
                    response = self._client.get(
                        url, headers={"Authorization": f"Bearer {self._bearer}"}
                    )
            except httpx.HTTPError as exc:
                note = f"{type(exc).__name__}: {exc}"
                continue

            if response.is_success and response.content:
                for template in PATH_TEMPLATES:
                    if url.endswith(template.format(version=version)):
                        self._template = template
                        break
                return response.content, "ok"
            note = str(response.status_code)
        return None, note


def _titel(content: bytes) -> str:
    """Read the title and version out of a specification, for the listing.

    Args:
        content: The raw document.

    Returns:
        A short description, or the document size when it is not JSON we can
        read — a YAML document is still perfectly usable for generation.
    """
    try:
        info = json.loads(content).get("info", {})
    except (ValueError, AttributeError):
        return f"{len(content) // 1024} kB"
    return f"{info.get('title', '?')} {info.get('version', '')}".strip()


def opdag(fetcher: Fetcher, versioner: list[str]) -> dict[str, bytes]:
    """Probe each requested document and keep the ones that exist.

    Args:
        fetcher: Retriever bound to the configured environment.
        versioner: Document names to probe.

    Returns:
        The documents that were retrieved, keyed by version name.
    """
    fundet: dict[str, bytes] = {}
    for version in versioner:
        content, note = fetcher.hent(version)
        if content is None:
            print(f"  {version:<10} —  {note}")  # noqa: T201
            continue
        fundet[version] = content
        print(f"  {version:<10} ok  {_titel(content)}")  # noqa: T201
    return fundet


def _forbered(content: bytes, tmpdir: Path) -> tuple[Path, list[str]] | None:
    """Write the document to disk in the form the generator can read.

    SBSYS publishes Swagger 2.0 for at least some versions, which the
    generator's OpenAPI parser rejects — 2.0 puts models under ``definitions``
    rather than ``components/schemas`` and allows ``"in": "body"`` parameters
    that the OpenAPI 3 parser refuses. For those documents only the
    ``definitions`` section is extracted and fed in as plain JSON Schema, which
    also yields better model names than parsing inline path schemas would.

    Args:
        content: The raw document.
        tmpdir: Directory to write the prepared file into.

    Returns:
        A pair of the prepared file and the extra generator arguments it needs,
        or ``None`` if the document holds no models at all.
    """
    if content.lstrip()[:1] not in (b"{", b"["):
        spec = tmpdir / "swagger.yaml"
        spec.write_bytes(content)
        return spec, ["--input-file-type", "openapi", *OPENAPI_SCOPES]

    try:
        document = json.loads(content)
    except ValueError:
        spec = tmpdir / "swagger.json"
        spec.write_bytes(content)
        return spec, ["--input-file-type", "openapi", *OPENAPI_SCOPES]

    if str(document.get("swagger", "")).startswith("2"):
        definitions = document.get("definitions") or {}
        if not definitions:
            return None
        spec = tmpdir / "definitions.json"
        spec.write_text(json.dumps({"definitions": definitions}), encoding="utf-8")
        return spec, ["--input-file-type", "jsonschema"]

    spec = tmpdir / "swagger.json"
    spec.write_bytes(content)
    return spec, ["--input-file-type", "openapi", *OPENAPI_SCOPES]


def generer(content: bytes, version: str) -> Path | None:
    """Generate one module from one specification document.

    The generator requires a file path rather than a directory when the input
    is a single file, so each version becomes ``generated/<version>.py`` rather
    than a subpackage.

    Args:
        content: The raw document.
        version: Document name, which becomes the module name.

    Returns:
        Path to the generated module or package, or ``None`` if the document
        contained no models at all. Some SBSYS documents are routing stubs with
        no schemas and nothing to generate, which is not an error.

        Definition names containing dots, which SBSYS uses heavily
        (``Dto.Sag.SagDto``), become a module hierarchy. The generator then
        demands a directory, so those versions land as a package
        ``generated/<version>/`` instead of a single module.

    Raises:
        SystemExit: If ``datamodel-code-generator`` is not installed.
        subprocess.CalledProcessError: If generation fails for any other reason.
    """
    forberedt = _forbered(content, Path(tempfile.mkdtemp()))
    if forberedt is None:
        return None
    spec, ekstra = forberedt

    OUTPUT.mkdir(parents=True, exist_ok=True)
    som_fil = OUTPUT / f"{version}.py"
    som_pakke = OUTPUT / version

    resultat = _koer(spec, ekstra, som_fil)
    if resultat.returncode != 0 and "output directory" in resultat.stderr + resultat.stdout:
        # Definitionsnavne med punktummer bliver til et modulhierarki, og
        # generatoren kraever da en mappe. Vi ved det foerst naar den siger det.
        som_fil.unlink(missing_ok=True)
        shutil.rmtree(som_pakke, ignore_errors=True)
        som_pakke.mkdir(parents=True, exist_ok=True)
        resultat = _koer(spec, ekstra, som_pakke)
        maal = som_pakke
    else:
        maal = som_fil

    if resultat.returncode != 0:
        if "Models not found" in resultat.stderr + resultat.stdout:
            som_fil.unlink(missing_ok=True)
            shutil.rmtree(som_pakke, ignore_errors=True)
            return None
        sys.stderr.write(resultat.stderr)
        raise subprocess.CalledProcessError(resultat.returncode, resultat.args)

    return maal


def _koer(spec: Path, ekstra: list[str], output: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the generator once, without raising on failure.

    Args:
        spec: Prepared specification file.
        ekstra: Input-type specific arguments from :func:`_forbered`.
        output: Target file or directory.

    Returns:
        The completed process, so the caller can inspect why it failed.

    Raises:
        SystemExit: If ``datamodel-code-generator`` is not installed.
    """
    try:
        return subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "datamodel_code_generator",
                "--input",
                str(spec),
                *ekstra,
                "--output",
                str(output),
                "--output-model-type",
                "pydantic_v2.BaseModel",
                "--target-python-version",
                "3.11",
                "--snake-case-field",
                "--use-annotated",
                "--use-standard-collections",
                "--use-union-operator",
                "--field-constraints",
                "--allow-population-by-field-name",
                "--disable-timestamp",
                "--formatters",
                "builtin",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:  # pragma: no cover
        raise SystemExit(
            "datamodel-code-generator is not installed. Run `uv sync --dev` first."
        ) from exc


def _parse_args() -> argparse.Namespace:
    """Define and parse the command line.

    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Generate Pydantic models from the SBSYS OpenAPI specifications.",
    )
    parser.add_argument(
        "versioner",
        nargs="*",
        metavar="VERSION",
        help="Documents to generate, e.g. v10 v1. Defaults to every one found.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="kun_liste",
        help="Report which documents exist and generate nothing.",
    )
    parser.add_argument(
        "--spec",
        type=Path,
        help="Generate from a local file instead of fetching. Requires --name.",
    )
    parser.add_argument(
        "--dump",
        type=Path,
        metavar="DIR",
        help="Also write each fetched document to this directory, for inspection.",
    )
    parser.add_argument(
        "--name",
        help="Module name to generate a local --spec into, e.g. v10.",
    )
    return parser.parse_args()


def main() -> None:
    """Discover, generate, and restore the package docstring.

    ``datamodel-code-generator`` writes its own ``__init__.py``, so the
    hand-written top-level docstring recording the do-not-edit policy is
    written back afterwards.

    Raises:
        SystemExit: On a bad command line, missing settings, or if no document
            could be retrieved.
    """
    args = _parse_args()
    versioner = [_valid_name(v) for v in args.versioner] or list(VERSIONS)

    if args.spec:
        if not args.name:
            raise SystemExit("--spec requires --name, e.g. --spec swagger.json --name v10")
        if not args.spec.is_file():
            raise SystemExit(f"No such file: {args.spec}")
        maal = generer(args.spec.read_bytes(), _valid_name(args.name))
        (OUTPUT / "__init__.py").write_text(PRESERVED_DOC, encoding="utf-8")
        if maal is None:
            raise SystemExit(f"{args.spec} contains no models.")
        print(f"Generated {maal}")  # noqa: T201
        return

    values = _load_env()
    mangler = [f"SBSYS_{k}" for k in REQUIRED if not values.get(k)]
    if mangler:
        hvor = _find_env_file() or "no .env file found"
        raise SystemExit(
            f"Missing settings: {', '.join(mangler)}\n"
            f"Looked in the environment and: {hvor}\n"
            "Alternatively, generate from a local file with --spec and --name."
        )

    print(f"Probing {len(versioner)} documents under {values['BASE_URL'].rstrip('/')}")  # noqa: T201

    with httpx.Client(timeout=120.0, verify=_verify(values), follow_redirects=True) as client:
        fundet = opdag(Fetcher(values, client), versioner)

    if args.dump:
        args.dump.mkdir(parents=True, exist_ok=True)
        for version, content in fundet.items():
            (args.dump / f"{version}.json").write_bytes(content)
        print(f"\nWrote {len(fundet)} documents to {args.dump}")  # noqa: T201

    if not fundet:
        raise SystemExit("\nNo specification documents could be retrieved.")

    if args.kun_liste:
        print(f"\n{len(fundet)} documents available. Run without --list to generate.")  # noqa: T201
        return

    skrevet: list[str] = []
    tomme: list[str] = []
    for version, content in fundet.items():
        print(f"\nGenerating {version} …")  # noqa: T201
        if generer(content, version) is None:
            print(f"  {version}: no models in the document, skipped")  # noqa: T201
            tomme.append(version)
        else:
            skrevet.append(version)

    (OUTPUT / "__init__.py").write_text(PRESERVED_DOC, encoding="utf-8")
    print(f"\nGenerated {len(skrevet)} modules in {OUTPUT}")  # noqa: T201
    if tomme:
        print(f"Skipped, no models: {', '.join(tomme)}")  # noqa: T201
    if not skrevet:
        raise SystemExit("Nothing was generated. Inspect a document with --dump.")


if __name__ == "__main__":
    main()
