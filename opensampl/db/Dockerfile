FROM timescale/timescaledb-ha:pg16.2-ts2.14.2-all

ENV DEBIAN_FRONTEND=noninteractive

COPY create-grafana.sh /docker-entrypoint-initdb.d/020_create_grafana_user.sh

CMD ["postgres"]