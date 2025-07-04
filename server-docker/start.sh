#!/bin/bash

echo "🚀 Starting Centralized Monitoring Server..."

# Create necessary directories
mkdir -p /app/prometheus-data /app/grafana-data

# Start Prometheus in background
echo "📊 Starting Prometheus..."
prometheus \
    --config.file=/app/central-prometheus.yml \
    --storage.tsdb.path=/app/prometheus-data \
    --web.console.libraries=/usr/share/prometheus/console_libraries \
    --web.console.templates=/usr/share/prometheus/consoles \
    --web.enable-lifecycle \
    --web.listen-address=0.0.0.0:9090 &

# Wait for Prometheus to start
sleep 5

# Configure Grafana
echo "📈 Configuring Grafana..."
export GF_PATHS_DATA=/app/grafana-data
export GF_PATHS_LOGS=/app/grafana-data/logs
export GF_PATHS_PLUGINS=/app/grafana-data/plugins
export GF_PATHS_PROVISIONING=/app/grafana-provisioning
export GF_SECURITY_ADMIN_PASSWORD=admin

# Create Grafana provisioning directories
mkdir -p /app/grafana-provisioning/datasources
mkdir -p /app/grafana-provisioning/dashboards
mkdir -p /app/dashboards

# Create Prometheus datasource configuration
cat > /app/grafana-provisioning/datasources/prometheus.yml << EOF
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://localhost:9090
    isDefault: true
    editable: true
EOF

# Create dashboard provisioning configuration
cat > /app/grafana-provisioning/dashboards/dashboard.yml << EOF
apiVersion: 1
providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /app/dashboards
EOF

# Copy dashboard to provisioning directory
cp /app/dashboard.json /app/dashboards/

# Start Grafana in background
echo "📈 Starting Grafana..."
cd /opt/grafana
./bin/grafana-server \
    --homepath=/opt/grafana \
    --config=/opt/grafana/conf/defaults.ini &

# Wait for Grafana to start
sleep 10

# Start Flask registration server
echo "🔧 Starting Registration Server..."
cd /app
python3 registration-server.py