FROM python:3.11 AS builder
WORKDIR /app
COPY . .
RUN pip install --break-system-packages poetry && poetry install
RUN ./scripts/generate_docs.sh

FROM nginxinc/nginx-unprivileged:alpine-perl
COPY --from=builder /app/site/ /usr/share/nginx/html

