FROM python:3.11.14-slim-bookworm@sha256:65a93d69fa75478d554f4ad27c85c1e69fa184956261b4301ebaf6dbb0a3543d
WORKDIR /app
COPY models/pyproject.toml /app/models/pyproject.toml
COPY models/src /app/models/src
COPY infrastructure/services/piper/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt ./models
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2
CMD ["python", "-m", "iot_models.piper_service"]
