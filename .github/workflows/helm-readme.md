# CI/CD overview

Checks run on **every pull request**. Images and charts are published **only after a merge to `main`**.

| Workflow | Trigger | Publishes? |
|---|---|---|
| `lint.yml`, `tests.yml`, `dependency-security.yml` | every PR, push to `main` | no |
| `helm-checks.yml` | every PR | no |
| `publish-artifacts.yml` | push to `main` | images + Helm chart to GHCR |
| `publish.yml` (PyPI), `static.yml` (Pages) | push to `main` | yes |
| `build-images.yml` | reusable (called by the two above) | only when `push: true` |

## Images are built from a wheel
`build-images.yml` runs `uv build --wheel` once and passes the wheel to the `backend` and `migrations`
Docker builds as the named context `wheel`. Their Dockerfiles install that wheel when present and fall back
to `opensampl==$OPENSAMPL_VERSION` from PyPI for local builds, so images always contain the code being built.

## Pull requests (`helm-checks.yml`)
```
build wheel -> build 4 images (not pushed) -> load into minikube -> helm install (migrations enabled)
helm lint + template, and a check that helm/Chart.yaml `version` was bumped if helm/ changed
```
Images are tagged `pr-local` and installed with `imagePullPolicy=Never`; nothing touches GHCR.

## Push to `main` (`publish-artifacts.yml`)
```
build wheel -> build + push db/backend/grafana/migrations (latest and the pyproject version) -> package + push chart
```
