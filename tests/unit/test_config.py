# tests/unit/test_config.py
"""Discovery of the .env file, which decides whether a job can start at all."""

from __future__ import annotations

import pytest

from sbsys import SbsysSettings
from sbsys.config import ENV_FILE_VAR, find_env_file

ENV_CONTENT = """\
SBSYS_BASE_URL=https://sbsys.fundet.dk
SBSYS_TOKEN_URL=https://auth.fundet.dk/token
SBSYS_CLIENT_ID=id
SBSYS_CLIENT_SECRET=secret
SBSYS_USERNAME=user
SBSYS_PASSWORD=pass
"""


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch):
    """Strip any SBSYS_ variable inherited from the developer's own shell."""
    monkeypatch.delenv(ENV_FILE_VAR, raising=False)
    for name in (
        "SBSYS_BASE_URL",
        "SBSYS_TOKEN_URL",
        "SBSYS_CLIENT_ID",
        "SBSYS_CLIENT_SECRET",
        "SBSYS_USERNAME",
        "SBSYS_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)


def test_findes_i_arbejdskataloget(tmp_path, monkeypatch):
    """A .env in the working directory is used."""
    (tmp_path / ".env").write_text(ENV_CONTENT)
    monkeypatch.chdir(tmp_path)

    assert SbsysSettings().base_url == "https://sbsys.fundet.dk"


def test_findes_i_et_overliggende_katalog(tmp_path, monkeypatch):
    """Running from a subdirectory still finds the project's .env."""
    (tmp_path / ".env").write_text(ENV_CONTENT)
    dybt = tmp_path / "src" / "pakke"
    dybt.mkdir(parents=True)
    monkeypatch.chdir(dybt)

    assert SbsysSettings().base_url == "https://sbsys.fundet.dk"


def test_eksplicit_sti_vinder(tmp_path, monkeypatch):
    """SBSYS_ENV_FILE beats whatever is in the working directory."""
    (tmp_path / ".env").write_text(ENV_CONTENT.replace("fundet", "forkert"))
    andet = tmp_path / "andet"
    andet.mkdir()
    (andet / "produktion.env").write_text(ENV_CONTENT)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(ENV_FILE_VAR, str(andet / "produktion.env"))

    assert SbsysSettings().base_url == "https://sbsys.fundet.dk"


def test_miljoevariabel_vinder_over_filen(tmp_path, monkeypatch):
    """A real environment variable overrides the same key in the file."""
    (tmp_path / ".env").write_text(ENV_CONTENT)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SBSYS_BASE_URL", "https://sbsys.override.dk")

    assert SbsysSettings().base_url == "https://sbsys.override.dk"


def test_arbejdskatalog_laeses_ved_kald_ikke_ved_import(tmp_path, monkeypatch):
    """Changing directory after import still resolves correctly."""
    (tmp_path / ".env").write_text(ENV_CONTENT)
    tom = tmp_path / "tom"
    tom.mkdir()

    monkeypatch.chdir(tom)
    assert find_env_file() == tmp_path / ".env"


def test_ingen_fil_giver_valideringsfejl(tmp_path, monkeypatch):
    """With no .env and no variables, the missing fields are reported."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(Exception, match="base_url"):
        SbsysSettings()


def test_trailing_slash_fjernes(tmp_path, monkeypatch):
    """Base and token URLs are normalised so paths join cleanly."""
    (tmp_path / ".env").write_text(ENV_CONTENT.replace("fundet.dk", "fundet.dk/"))
    monkeypatch.chdir(tmp_path)

    assert not SbsysSettings().base_url.endswith("/")


def test_hemmeligheder_laekker_ikke_i_repr(tmp_path, monkeypatch):
    """Passwords and secrets are masked in repr, so a traceback is safe.

    Distinctive values are used, because the field names themselves contain
    the words "password" and "secret".
    """
    indhold = ENV_CONTENT.replace("secret", "hemmelig-vaerdi-1").replace(
        "SBSYS_PASSWORD=pass", "SBSYS_PASSWORD=hemmelig-vaerdi-2"
    )
    (tmp_path / ".env").write_text(indhold)
    monkeypatch.chdir(tmp_path)

    tekst = repr(SbsysSettings())

    assert "hemmelig-vaerdi-1" not in tekst
    assert "hemmelig-vaerdi-2" not in tekst
    assert "**********" in tekst
