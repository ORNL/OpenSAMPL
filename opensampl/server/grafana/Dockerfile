FROM grafana/grafana

COPY ./grafana-provisioning/dashboards /etc/grafana/provisioning/dashboards
COPY ./grafana-provisioning/datasources /etc/grafana/provisioning/datasources

COPY ./grafana-dashboards /var/lib/grafana/dashboards

COPY ./grafana.env .
RUN source ./grafana.env