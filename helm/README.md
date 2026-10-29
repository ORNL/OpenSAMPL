# Deployment
# Update  --version <Latest github oci version>

helm install opensampl-test \
  oci://ghcr.io/ornl/charts/opensampl \
  --version 0.1.7 \
  --namespace opensampl-test \
  --create-namespace \
  --dry-run \
  --debug



charts/
└── opensampl/
    ├── Chart.yaml
    ├── values.yaml
    ├── templates/
    │   ├── _helpers.tpl
    │   ├── db-statefulset.yaml
    │   ├── db-service.yaml
    │   ├── grafana-deployment.yaml
    │   ├── grafana-service.yaml
    │   ├── backend-deployment.yaml
    │   ├── backend-service.yaml
    │   ├── migrations-job.yaml
    │   ├── pvc.yaml
    │   ├── ingress.yaml (optional)
    │   └── NOTES.txt
    └── .helmignore