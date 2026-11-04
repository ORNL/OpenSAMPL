# Optional build context holding a locally built opensampl wheel.
# CI overrides this stage with `--build-context wheel=<dir containing the .whl>`;
# without it the stage is empty and the released version is installed from PyPI.
FROM scratch AS wheel

FROM python:3.14

ARG OPENSAMPL_VERSION=1.2.6

WORKDIR /
RUN --mount=type=bind,from=wheel,target=/wheels \
    if ls /wheels/opensampl-*.whl >/dev/null 2>&1; then \
        spec="$(ls /wheels/opensampl-*.whl)[migrations]"; \
    else \
        spec="opensampl[migrations]==${OPENSAMPL_VERSION}"; \
    fi && \
    pip install --no-cache-dir \
    "${spec}" \
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
