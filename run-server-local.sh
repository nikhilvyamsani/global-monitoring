#!/bin/bash

echo "🚀 Starting Monitoring Server on Mac..."

cd server-docker

# Install Python dependencies
pip3 install -r requirements.txt

# Install Prometheus if not exists
if ! command -v prometheus &> /dev/null; then
    echo "📦 Installing Prometheus..."
    brew install prometheus
fi

# Install Grafana if not exists
if ! command -v grafana-server &> /dev/null; then
    echo "📦 Installing Grafana..."
    brew install grafana
fi

# Create data directories
mkdir -p prometheus-data grafana-data

# Start Prometheus in background
echo "📊 Starting Prometheus..."
prometheus \
    --config.file=central-prometheus.yml \
    --storage.tsdb.path=./prometheus-data \
    --web.enable-lifecycle \
    --web.listen-address=0.0.0.0:9090 &

# Start Grafana in background
echo "📈 Starting Grafana..."
GF_PATHS_DATA=./grafana-data \
GF_SECURITY_ADMIN_PASSWORD=admin \
grafana-server \
    --homepath=/opt/homebrew/share/grafana \
    --config=/opt/homebrew/etc/grafana/grafana.ini &

# Wait for services
sleep 5

# Start registration server
echo "🔧 Starting Registration Server..."
echo "Access points:"
echo "  Prometheus: http://192.168.1.47:9090"
echo "  Grafana: http://192.168.1.47:3000 (admin/admin)"
echo "  Registration API: http://192.168.1.47:5001"
python3 registration-server.py