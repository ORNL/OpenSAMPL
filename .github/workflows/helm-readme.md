# Helm chart workflow (`helm-chart.yml`)

Artifacts are published **only after a merge to `main`**. Pull requests validate but never push.

## On pull requests to `main`
```
Build images (not pushed) -> load into minikube -> helm install test
Helm lint + template, and a check that helm/Chart.yaml version was bumped if helm/ changed
```
- Images are built with the `pr-local` tag, shared as short-lived workflow artifacts, and loaded into minikube with `imagePullPolicy=Never`, so nothing is pulled from or pushed to GHCR.
- If anything under `helm/` changes, bump `version` in `helm/Chart.yaml` (otherwise `helm push` would collide with an existing version).

## On push to `main`
```
Build + push images (latest and the pyproject version) -> package + push chart to oci://ghcr.io/ornl/charts
```
