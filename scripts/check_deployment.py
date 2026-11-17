"""Verify a Helm test deployment from inside its backend container."""

import sys
import time

import requests


def main():
    """Check database readiness and execute the provisioned datasource health query."""
    grafana_url = sys.argv[1]
    for attempt in range(12):
        try:
            for endpoint in ("healthcheck_database", "healthcheck_metadata"):
                response = requests.get(f"http://127.0.0.1:8000/{endpoint}", timeout=10)
                response.raise_for_status()
                assert response.json()["status"] == "OK"
            response = requests.get(f"{grafana_url}/api/datasources", auth=("admin", "admin"), timeout=10)
            response.raise_for_status()
            sources = response.json()
            assert sources, "No provisioned datasource"
            for source in sources:
                response = requests.get(
                    f"{grafana_url}/api/datasources/uid/{source['uid']}/health",
                    auth=("admin", "admin"),
                    timeout=10,
                )
                response.raise_for_status()
                assert response.json()["status"] == "OK", response.text
            print("Backend database and Grafana datasource checks passed")
            return
        except (requests.RequestException, AssertionError):
            if attempt == 11:
                raise
            time.sleep(5)


if __name__ == "__main__":
    main()
