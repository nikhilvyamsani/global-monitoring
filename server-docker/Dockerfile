FROM prom/prometheus:latest as prometheus
FROM grafana/grafana:latest as grafana
FROM python:3.11-slim

# Install Prometheus
COPY --from=prometheus /bin/prometheus /usr/local/bin/
COPY --from=prometheus /usr/share/prometheus /usr/share/prometheus
COPY --from=prometheus /etc/prometheus /etc/prometheus

# Install Grafana
COPY --from=grafana /usr/share/grafana /opt/grafana

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY registration-server.py .
COPY central-prometheus.yml .
COPY dashboard.json .
COPY start.sh .

RUN chmod +x start.sh

EXPOSE 9090 3000 5001

CMD ["./start.sh"]