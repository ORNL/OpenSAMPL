# Dependency security remediation for 1.2.4

Date: 2026-10-12  
Base commit: `eef295f017cb10caf0ebe7aa5af640aa65bf63e4`  
Branch: `fix/dependabot-nine-alert-remediation`

## Scope and result

This release remediates the nine Dependabot alerts that were open when work began. The five affected packages are constrained at their patched minimum in the published dependency metadata and resolve above those minimums in `uv.lock`. A final `uv audit` found no known vulnerabilities or adverse project statuses in the comprehensive 114-package resolved graph or in the separately audited runtime, backend, migrations, and development subsets.

| Alert | Severity | Package | Advisory | Before | Locked after | Patched minimum | Result |
|---|---|---|---|---:|---:|---:|---|
| #46 | Critical | anyio | GHSA-82r6-8w77-94w6 / CVE-2026-63374 | 4.13.0 | 4.14.2 | 4.14.2 | Fixed |
| #49 | High | urllib3 | GHSA-8988-9cw3-xx77 | 2.7.0 | 2.8.0 | 2.8.0 | Fixed |
| #43 | High | pymdown-extensions | GHSA-gm37-52c6-37mw / CVE-2026-67422 | 10.21.3 | 12.2 | 11.0.1 | Fixed |
| #48 | High | urllib3 | GHSA-vxq7-64xx-v4gw / CVE-2026-97689 | 2.7.0 | 2.8.0 | 2.8.0 | Fixed |
| #47 | Moderate | urllib3 | GHSA-gh4c-6fx4-qh6g / CVE-2026-97688 | 2.7.0 | 2.8.0 | 2.8.0 | Fixed |
| #45 | Moderate | anyio | GHSA-5p39-cfhj-2xmp / CVE-2026-64847 | 4.13.0 | 4.14.2 | 4.14.2 | Fixed |
| #50 | Moderate | Mako | GHSA-5639-2j2p-m4mx / CVE-2026-102991 | 1.3.12 | 1.4.3 | 1.4.2 | Fixed |
| #44 | Moderate | mkdocs-material | GHSA-xvg9-69gf-fjrf / CVE-2026-73295 | 9.6.14 | 9.7.7 | 9.7.7 | Fixed |
| #42 | Moderate | pymdown-extensions | GHSA-9xwg-3r6f-jcx2 / CVE-2026-61632 | 10.21.3 | 12.2 | 11.0.0 | Fixed |

GitHub must reprocess the merged default branch before these alerts can be reported as closed. This document does not claim pre-merge alert closure.

## Published dependency constraints

- Runtime: `urllib3>=2.8.0,<3` prevents `requests` from selecting an affected urllib3 release.
- Backend extra: `anyio>=4.14.2,<5` prevents FastAPI/Starlette from selecting an affected AnyIO release.
- Migrations extra: `mako>=1.4.2,<2` protects Alembic templating, including supported Windows installs.
- Development/documentation: `mkdocs-material>=9.7.7,<10` and `pymdown-extensions>=11.0.1,<13` protect generated search and Markdown rendering.
- Documentation compatibility: `mkdocstrings[python]>=1.0.6,<2` is required for the PyMdown 12 Highlight API.
- Supported Python compatibility: `libcst>=1.9.0,<2`; NumPy 1.26.4 is retained for Python 3.10-3.12 and NumPy 2.4+ is required for Python 3.13-3.14, where compatible wheels are published.

The backend and migrations Dockerfiles repeat the relevant security floors so building a released OpenSAMPL version cannot reintroduce the vulnerable transitives.

## Resolution changes

The requested targeted `uv lock --upgrade-package` operation was used. Follow-up targeted updates were made only where compatibility testing demonstrated a constraint or wheel incompatibility.

| Package | Before | After | Reason |
|---|---:|---:|---|
| anyio | 4.13.0 | 4.14.2 | Security |
| urllib3 | 2.7.0 | 2.8.0 | Security |
| pymdown-extensions | 10.21.3 | 12.2 | Security; current compatible release |
| Mako | 1.3.12 | 1.4.3 | Security; current compatible release |
| mkdocs-material | 9.6.14 | 9.7.7 | Security |
| mkdocstrings | 0.29.1 | 1.0.6/1.0.7 | PyMdown 12 compatibility across Python markers |
| mkdocstrings-python | 1.16.11 | 2.0.9 | mkdocstrings compatibility |
| griffe | 1.7.3 | removed | Replaced by mkdocstrings' `griffelib` dependency |
| griffelib | absent | 2.3.0/2.3.2 | mkdocstrings dependency across Python markers |
| libcst | 1.8.0 | 1.9.0 | Python 3.14 wheel and grammar support |
| numpy | 1.26.4 | 1.26.4 / 2.5.4 | Python-version-specific wheel compatibility |
| scipy | 1.15.3 | 1.15.3 / 1.18.1 | NumPy/Python marker resolution |
| pydantic | 2.11.5 | 2.14.1 | Python 3.14 wheel compatibility |
| pydantic-core | 2.33.2 | 2.50.1 | Pydantic dependency |
| typing-extensions | 4.13.2 | 4.16.0 | Pydantic dependency |
| typing-inspection | 0.4.2 | 0.4.4 | Pydantic dependency |
| pyyaml | 6.0.2 | 6.0.2 / 6.0.3 | Python-marker wheel compatibility |

The package version was advanced from 1.2.3 to 1.2.4 in `pyproject.toml`, `uv.lock`, the Docker bake configuration, and `CHANGELOG.md`.

## Validation evidence

### Security-specific behavior

- AnyIO: verified IDNA 2008 resolution of `faß.de` and completion of a process-pool worker writing beyond a pipe buffer to stderr.
- urllib3: verified local HTTP, gzip, chunked deflate streaming with trailing data, retry behavior, read timeouts, and separate certificate-verifying proxy and destination TLS contexts. Certificate verification remains enabled.
- PyMdown Extensions: verified code fences, admonitions, deletion, superscript, and automatic links; generated the complete API navigation and built the site.
- Mako/Alembic: verified template rendering, rejection of a Windows drive-letter traversal path, and discovery of the packaged Alembic revision chain.
- Material for MkDocs: built the site with search enabled and verified a non-empty search index and JavaScript search assets.

### Commands and results

| Check | Result |
|---|---|
| `uv lock --check` | Pass; 115 packages resolved |
| Python 3.10 non-integration tests | 108 passed, 1 deprecation warning |
| Python 3.12 non-integration tests | 108 passed, 1 deprecation warning |
| Python 3.13 non-integration tests | 108 passed, 1 deprecation warning |
| Python 3.14 non-integration tests | 108 passed, 1 deprecation warning |
| Python 3.13 PostgreSQL 15 + PostGIS integration tests | 10 passed |
| Final wheel install/import smoke, Python 3.10/3.12/3.13/3.14 | Pass on all four versions |
| CLI help: `opensampl`, `opensampl-collect`, `opensampl-server`, `opensampl-server2` | Pass on Python 3.10/3.12/3.14 |
| `ruff check .` | Pass |
| `ruff format --check .` | Pass; 48 files formatted |
| `uv build` | Pass; 1.2.4 sdist and wheel produced |
| API documentation generation | Pass |
| `mkdocs build --clean` | Pass; search index and JavaScript assets present |
| Backend Docker image build/smoke | Pass; AnyIO 4.15.1 and urllib3 2.8.0 |
| Migrations Docker image build/smoke | Pass; Mako 1.4.3 and urllib3 2.8.0 |
| Documentation Docker image build/smoke | Pass; search index and JavaScript assets present |
| Grafana Docker image build/provisioning inspection | Pass; data source and five dashboard files present |
| `ty check` | Executed; original commit had 42 diagnostics and this branch has 41, so this is not yet a passing repository gate |
| GitHub-hosted PR checks | Pass on PR #33: dependency audit, Ruff/docs, Python 3.10, Python 3.12, and Python 3.14 |

The PostgreSQL/PostGIS integration suite covers schema creation, PostGIS availability, seeded metrics and reference types, default UUID behavior, and transaction rollback. The full production Alembic upgrade chain additionally requires TimescaleDB and `pg_cron`; only revision discovery and Mako rendering were exercised in this environment.

## Audit results

`uv audit --locked --preview-features audit-command` queried OSV without ignore rules:

| Graph | Packages audited | Findings |
|---|---:|---:|
| Comprehensive lockfile | 114 | 0 |
| Runtime install | 103 | 0 |
| Backend install | 110 | 0 |
| Migrations install | 105 | 0 |
| Development/documentation install | 56 | 0 |

No residual actionable dependency vulnerability was found, and none of the five vulnerable versions remains in the applicable resolved environments.

## Prevention and exception process

`.github/dependabot.yml` schedules weekly uv, GitHub Actions, and Docker updates. Compatible minor and patch version updates are grouped; Dependabot security updates remain independently actionable. `.github/workflows/dependency-security.yml` verifies lock consistency, audits the comprehensive graph and installable subsets, asserts all five patched minimums, and uploads a CycloneDX SBOM. No advisory is suppressed.

If a future finding cannot immediately be remediated, an exception requires human review and a tracking issue that records the advisory ID, affected installation scope, exploitability analysis, compensating controls, accountable owner, review date, and expiry date. Any audit ignore must name one advisory precisely, be linked to that approved issue, and be removed no later than the expiry date. Broad package, severity, or tool suppressions are not acceptable.

## Outstanding risks and unverified items

- GitHub-hosted CI passed on PR #33. Dependabot alert closure can only be confirmed after merge and default-branch reprocessing.
- Hardware-in-the-loop collection against physical ADVA and Microchip equipment was unavailable. Existing parser/collector unit coverage and CLI imports passed; live equipment behavior was not claimed.
- NTP behavior was covered by the existing unit suite, but no external NTP appliance was used.
- The complete Alembic upgrade chain was not executed against the private production TimescaleDB/`pg_cron` image. Migration imports, revision discovery, Mako rendering, PostgreSQL/PostGIS ORM integration, and the migrations container were validated.
- The Docker application images install the latest published OpenSAMPL release. Before 1.2.4 is published, image smoke testing necessarily used OpenSAMPL 1.2.3 plus the new enforced security floors; the branch's 1.2.4 wheel was separately installed and imported on all four tested Python versions.
- `ty check` reports 41 diagnostics outside the dependency-remediation scope (down from 42 at the original commit); Ruff, tests, builds, and security checks pass.
