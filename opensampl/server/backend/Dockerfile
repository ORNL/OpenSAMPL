# Optional build context holding a locally built opensampl wheel.
# CI overrides this stage with `--build-context wheel=<dir containing the .whl>`;
# without it the stage is empty and the released version is installed from PyPI.
FROM scratch AS wheel

FROM python:3.14 AS base
ARG OPENSAMPL_VERSION=1.2.7

WORKDIR /tmp
ENV ROUTE_TO_BACKEND=false

FROM base AS prod

RUN --mount=type=bind,from=wheel,target=/wheels \
    if ls /wheels/opensampl-*.whl >/dev/null 2>&1; then \
        spec="$(ls /wheels/opensampl-*.whl)[backend]"; \
    else \
        spec="opensampl[backend]==${OPENSAMPL_VERSION}"; \
    fi && \
    pip install --no-cache-dir \
    "${spec}" \
    "anyio>=4.14.2,<5" \
    "urllib3>=2.8.0,<3"

CMD ["uvicorn", "opensampl.server.backend.main:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS dev

CMD ["sh", "-c", "pip install -e \"./opensampl[backend]\" && uvicorn opensampl.server.backend.main:app --proxy-headers --host 0.0.0.0 --port 8000 --log-level debug --reload"]
