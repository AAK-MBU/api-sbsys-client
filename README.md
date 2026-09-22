# api-sbsys-client

Delt Python-klient til **SBSYS** ESDH REST API. Én fælles indgang til søgning,
sager, parter, dokumenter, journalnotater og erindringer, så de enkelte
projekter ikke hver især skal håndtere OAuth2-tokens, PascalCase-JSON og
SBSYS' særheder.

```python
from sbsys import SbsysClient

with SbsysClient.from_env() as sbsys:
    borger = sbsys.parter.hent_person("010101-1234")

    sag = sbsys.sager.opret_fra_skabelon(
        titel="Underretning",
        skabelon_id=332,
        sagsbehandler_id=sbsys.opslag.bruger_id_for_initialer("roboa"),
        part_id=borger.id,
    )

    sbsys.journalnotater.opret(sag.id, "Modtaget", "<p>Underretning modtaget.</p>")

    for sag in sbsys.sager.soeg_paa_cpr("010101-1234", max_antal=10):
        print(sag.nummer, sag.visningstitel)
```

---

## Status

Klienten er under opbygning, og **endpoint-stierne er endnu ikke verificeret**
mod et rigtigt miljø. De er udledt af mønstre og skal rettes ét område ad
gangen. Revider dem mod jeres egen specifikation, før I bygger noget ovenpå:

```bash
uv run python scripts/endpoints.py --check
```

| Område | Status |
| --- | --- |
| Konfiguration, token, TLS, genforsøg, fejlmapning | virker |
| `sager.hent`, `sager.soeg` | verificeret mod testmiljø |
| Øvrige ressourcer | stier ikke verificeret |
| Modeller | dækker de felter vi kender; `raw()` viser resten |

Mangler et endpoint, eller er stien forkert, så brug
[escape hatchen](#endpoints-vi-ikke-har-wrappet-endnu) frem for at vente.

---

## Installation

```bash
uv add "sbsys-client @ git+https://github.com/AAK-MBU/api-sbsys-client.git@v0.1.0"
```

Pin altid et tag. Installation fra `main` betyder, at et andet teams commit kan
brække jeres produktion.

## Konfiguration

Kopiér `.env.example` til `.env`, eller sæt miljøvariablerne direkte.

| Variabel | Påkrævet | Beskrivelse |
| --- | --- | --- |
| `SBSYS_BASE_URL` | ja | Fx `https://webapi.sbsys-test.<kommune>.dk` |
| `SBSYS_TOKEN_URL` | ja | OAuth2 token-endpoint |
| `SBSYS_CLIENT_ID` | ja | |
| `SBSYS_CLIENT_SECRET` | ja | |
| `SBSYS_USERNAME` | ja | Servicekonto |
| `SBSYS_PASSWORD` | ja | |
| `SBSYS_TIMEOUT` | nej | Sekunder, standard `30` |
| `SBSYS_MAX_RETRIES` | nej | Standard `3` |
| `SBSYS_VERIFY` | nej | `true`, `false` eller sti til CA-bundle |
| `SBSYS_ENV_FILE` | nej | Absolut sti til `.env` |


### Certifikater

Bruger jeres SBSYS et internt certifikat, fejler kald med
`CERTIFICATE_VERIFY_FAILED`. Eksportér CA-kæden og peg på den:

```
SBSYS_VERIFY=C:\sbsys\kommune-ca.pem
```

På Windows ligger CA'en ofte allerede i certifikatlageret. Pakken `truststore`
får Python til at bruge det:

```python
import truststore

truststore.inject_into_ssl()  # før klienten oprettes
```

`SBSYS_VERIFY=false` slår valideringen fra for al trafik med personoplysninger
i. Brug det højst til en enkelt lokal kørsel, aldrig i `.env` og aldrig i drift.

### Flere miljøer i samme proces

```python
from sbsys import SbsysClient, SbsysSettings

test = SbsysClient(SbsysSettings(base_url=..., token_url=..., ...))
```

---

## Brug

Operationerne er grupperet i ressourcer på klienten.

| Ressource | Metoder |
| --- | --- |
| `sbsys.sager` | `hent`, `soeg`, `soeg_paa_cpr`, `opret_fra_skabelon`, `opdater`, `tilfoej_part` |
| `sbsys.parter` | `hent_person`, `hent_firma` |
| `sbsys.dokumenter` | `hent`, `hent_paa_sag`, `download`, `download_til`, `upload` |
| `sbsys.journalnotater` | `hent_paa_sag`, `opret` |
| `sbsys.erindringer` | `hent_paa_sag`, `opret` |
| `sbsys.opslag` | `sagsskabeloner`, `sagsskabelon`, `statusser`, `find_brugere`, `bruger_id_for_initialer` |

Søgninger returnerer en iterator, der henter sider løbende. Stopper du efter tre
resultater, hentes kun første side:

```python
for sag in sbsys.sager.soeg({"SagsTitel": "Underretning"}, max_antal=50):
    ...
```

Alle fejl nedarver fra `SbsysError`, så `httpx` aldrig slipper ud:

```python
from sbsys import SbsysNotFoundError

try:
    sag = sbsys.sager.hent(149)
except SbsysNotFoundError:
    ...
```

Genforsøg sker automatisk ved 429 og 5xx, men kun på idempotente kald.
Oprettelser gentages aldrig — en gentagelse ville give dubletsager.

### Endpoints vi ikke har wrappet endnu

```python
adviseringer = sbsys.request("GET", f"/api/sag/{sags_id}/adviseringer")
```

Understøttet og forventet brug. Sig til bagefter, så promoverer vi endpointet
til en rigtig metode med modeller og tests.

---

## Test i jeres eget projekt

Brug den medfølgende fake i stedet for at mocke pakken:

```python
from sbsys.testing import FakeSbsysClient


def test_min_proces():
    sbsys = FakeSbsysClient(sager={1: {"Id": 1, "SagsTitel": "Test"}})
    min_proces(sbsys)
    assert sbsys.journalnotater.oprettede
```

Fake'en dækker sager og journalnotater. Alt andet rejser `NotImplementedError`
frem for at returnere noget forkert — udvid den, eller brug `respx` i den test.

---

## Arkitektur

```
sbsys/
├── client.py       # SbsysClient — det eneste offentlige indgangspunkt
├── config.py       # SbsysSettings
├── errors.py       # exception-hierarki
├── _transport/     # httpx, OAuth2, retry, fejlmapning, maskering  (internt)
├── models/         # Pydantic-modeller, PascalCase-aliaser
│   └── generated/  # autogenereret fra OpenAPI — rør ikke
├── resources/      # ét modul pr. domæneområde
└── testing/        # FakeSbsysClient til forbrugernes tests
```

Afhængigheder peger kun nedad: ressourcer kender modeller og transport,
transport kender intet til domænet.

**Klienten indeholder ikke forretningslogik.** "Opret sag, tilføj part,
journalisér kvittering, sæt erindring" er et arbejdsgangsflow og hører til i
det projekt, der ejer processen — ellers kan pakken ikke genbruges på tværs.

Metodenavnene er danske, fordi `sag`, `journalnotat` og `erindring` ikke har
gode engelske ækvivalenter og er de ord, SBSYS og sagsbehandlerne bruger.
Dokumentationen i koden er engelsk.

---

## Udvikling

```bash
uv sync --dev
uv run pytest                    # unit-tests, ingen credentials nødvendige
uv run pytest -m integration     # mod testmiljø, kræver .env
uv run ruff check . && uv run ruff format .
uv run mypy
```

Integrationstests er slået fra som standard. Kontrakttestene fanger, at SBSYS
har ændret svarformat, før produktionen gør det — kør dem gerne natligt.

### Værktøjer

| Kommando | Formål |
| --- | --- |
| `python scripts/endpoints.py --check` | Revider alle stier i `resources/` mod specifikationen |
| `python scripts/endpoints.py sag` | Slå rigtige stier op, filtreret |
| `python scripts/smoketest.py [sags_id]` | Trinvis verifikation mod et rigtigt miljø |
| `python scripts/generate_models.py --list` | Hvilke API-versioner udstiller instansen |
| `python scripts/generate_models.py default` | Generér modeller for én version |

Alle tre scripts læser `.env` som klienten. `endpoints.py` og
`generate_models.py` importerer bevidst ikke `sbsys`, så de virker, også når
pakken er i stykker.

### Modelgenerering

SBSYS udstiller ét dokument pr. API-version under `{base_url}/docs/{version}` —
`default` og `v1` til `v31`. Scriptet opdager, hvilke der findes:

```bash
uv run python scripts/generate_models.py --list      # inventar
uv run python scripts/generate_models.py             # alle fundne
uv run python scripts/generate_models.py default     # kun denne
uv run python scripts/generate_models.py default --dump specs\   # gem dokumentet
```

Tre dokumentformer håndteres automatisk:

| Form | Hvad der sker |
| --- | --- |
| Swagger 2.0 (`definitions`) | Kun `definitions` læses som JSON Schema. Giver de pæneste navne: `SagDto`. |
| OpenAPI 3 (`components/schemas`) | Læses direkte. |
| OpenAPI 3 med inline modeller | Læses med `--openapi-scopes`. Navngivning bliver maskinel. |

Output lander i `src/sbsys/models/generated/` som enten `<version>.py` eller
`<version>/`, hvis definitionsnavnene indeholder punktummer — SBSYS bruger
navne som `Dto.Sag.SagDto`, der bliver til et modulhierarki:

```python
from sbsys.models.generated.default.Dto.Sag import SagDto
```

Mappen er ekskluderet fra ruff, mypy og coverage, og genereret kode formateres
med generatorens indbyggede formatter, så projektets egne lint-regler ikke
håndhæves på maskingenereret kode.

**Brug ikke de genererede typer direkte i jeres projekter.** De skifter navn og
form med specifikationen, og navngivningen er maskinel — `CPRnummer` bliver til
`cp_rnummer`. De er opslagsværk, når vi bygger de kuraterede modeller i
`sbsys/models/`.

---

## Sikkerhed og persondata

- CPR-numre, tokens og kodeord maskeres før logning (`_transport/redact.py`).
  Al logning i pakken går gennem den funktion — brug den også hos jer.
- `SbsysAPIError.body` kan indeholde personoplysninger fra det afviste request.
  Log den kun til fejlsøgning, ikke til et delt logindeks.
- Hemmeligheder i `SbsysSettings` er `SecretStr` og maskeres i tracebacks.
- Journalnotater renderes som HTML. Escape alt, I interpolerer ind i dem.

## Versionering

SemVer. `SbsysClient`, ressourcemetoder og modeller er offentligt API. Alt
under `_transport/` er internt og kan ændre sig i en patch-udgivelse.