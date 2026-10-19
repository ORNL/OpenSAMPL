FROM ghcr.io/astral-sh/uv:0.13.1 AS uv

FROM python:3.14 AS builder
WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY . .
RUN uv sync --locked --all-extras --all-groups
RUN uv run python scripts/gen_api_docs.py && uv run mkdocs build --clean

FROM nginxinc/nginx-unprivileged:alpine-perl
COPY --from=builder /app/site/ /usr/share/nginx/html
