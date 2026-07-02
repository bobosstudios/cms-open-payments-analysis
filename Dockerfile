# Lightweight image to run the pipeline anywhere Docker is available.
# docker build -t cms-open-payments .
# docker run --rm cms-open-payments --states TX --max-records 2000
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so this layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Args after the image name are passed straight to main.py (e.g. --states TX).
ENTRYPOINT ["python", "main.py"]
