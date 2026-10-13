FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RETAILPULSE_HOME=/app

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[dashboard,dev]"

COPY sql ./sql
COPY tests ./tests
COPY dashboard ./dashboard
COPY .streamlit ./.streamlit

RUN mkdir -p data/raw data/processed dashboard/exports

CMD ["retailpulse", "run"]
