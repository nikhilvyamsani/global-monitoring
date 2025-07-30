# Stage 1: Prometheus
FROM prom/prometheus:latest as prometheus

# Stage 2: Grafana
FROM grafana/grafana:latest as grafana

# Final Stage: Python + Monitoring Setup
FROM python:3.11-slim

# Install Prometheus binary and config
COPY --from=prometheus /bin/prometheus /usr/local/bin/prometheus
COPY --from=prometheus /etc/prometheus /etc/prometheus

# Install Grafana
COPY --from=grafana /usr/share/grafana /opt/grafana

# Setup app
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --verbose

COPY server.py .
COPY central-prometheus.yml .
COPY dashboard.json .
COPY start.sh .

RUN chmod +x start.sh

# Expose ports
EXPOSE 9090 3000 5001

# Start everything
CMD ["./start.sh"]
