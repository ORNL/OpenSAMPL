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