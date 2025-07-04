FROM python:3.11-slim

WORKDIR /app

# Install build dependencies for ARM architectures
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY auto-discovery-client.py .
COPY .env .

EXPOSE 8118

CMD ["python3", "auto-discovery-client.py"]