FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

COPY ./src/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim-bookworm

WORKDIR /app

RUN addgroup --system app && adduser --system --group app

COPY --chown=app:app --from=builder /app/venv /app/venv
COPY --chown=app:app . .

ENV PATH="/app/venv/bin:$PATH"

USER app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]