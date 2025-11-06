FROM python:3.12 AS base
ARG OPENSAMPL_VERSION=1.1.5

WORKDIR /tmp
ENV ROUTE_TO_BACKEND=false

FROM base AS prod

RUN pip install --no-cache-dir "opensampl[backend]==${OPENSAMPL_VERSION}"

COPY main.py .

CMD ["uvicorn", "main:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS dev

CMD ["sh", "-c", "pip install -e \"/app/opensampl[backend]\" && uvicorn main:app --proxy-headers --host 0.0.0.0 --port 8000 --log-level debug --reload"]

# CMD ["tail", "-f", "/dev/null"]