### 1. **Smart Image Tagging**
Images now get tagged with:
- `pr-123` for pull requests
- `helm-deploy-abc123` for branch commits
- `latest` for main branch

### 2. **New Test Job** (`test-helm-chart`)
- **Only runs on PRs** (not regular pushes)
- Spins up local Kubernetes (minikube)
- Installs your Helm chart with PR-tagged images
- Verifies pods start successfully
- Shows detailed logs if anything fails

### 3. **Separated Helm Packaging**
- `helm-package` job only runs on **direct pushes** (not PRs)
- Lints, packages, and pushes the chart

## Workflow Flow

**On Pull Request:**
```
Build Images (with pr-123 tags) → Test in Kubernetes → ✓ Pass/Fail
```

**On Push to helm-deploy:**
```
Build Images (with latest tag) → Package & Push Helm Chart