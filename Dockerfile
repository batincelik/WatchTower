FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY watchtower ./watchtower
RUN pip install --no-cache-dir .
COPY alembic.ini ./
COPY migrations ./migrations
CMD ["uvicorn", "watchtower.api:app", "--host", "0.0.0.0", "--port", "8000"]

