FROM python:3.14

ARG OPENSAMPL_VERSION=1.1.5

WORKDIR /
RUN pip install --no-cache-dir \
    "opensampl[migrations]==${OPENSAMPL_VERSION}" \
    "mako>=1.4.2,<2" \
    "urllib3>=2.8.0,<3"

RUN useradd -m alembic
USER alembic
WORKDIR /app
COPY _migrations/ /app/_migrations/
COPY alembic.ini .

# needs 15 seconds for the db to finish initializing when run locally
CMD ["sh", "-c", "sleep 15 && alembic upgrade head"]
# uncomment below to reset datbase before any migration
#CMD ["alembic", "downgrade", "base"]
# or uncomment below to allow container to just stay awake
#CMD ["tail", "-f", "/dev/null"]
