#!/usr/bin/env python3
from flask import Flask, request, jsonify
import yaml
import os
import subprocess
import time
from collections import defaultdict

app = Flask(__name__)
PROMETHEUS_CONFIG = '/app/central-prometheus.yml'

# In-memory storage for pushed metrics
metrics_store = defaultdict(dict)

def ensure_prometheus_config():
    """Create Prometheus config if it doesn't exist"""
    if not os.path.exists(PROMETHEUS_CONFIG):
        default_config = {
            'global': {
                'evaluation_interval': '15s',
                'scrape_interval': '15s'
            },
            'scrape_configs': [
                {
                    'job_name': 'prometheus',
                    'static_configs': [{'targets': ['localhost:9090']}]
                }
            ]
        }
        os.makedirs(os.path.dirname(PROMETHEUS_CONFIG), exist_ok=True)
        with open(PROMETHEUS_CONFIG, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)
        print(f"✅ Created default Prometheus config at {PROMETHEUS_CONFIG}")

# Ensure config exists on startup
ensure_prometheus_config()

@app.route('/register', methods=['POST'])
def register_client():
    """Register a new client for monitoring"""
    try:
        print("\n🔄 Starting client registration process...")
        
        client_data = request.json
        print(f"📥 Received client data: {client_data}")
        
        hostname = client_data['hostname']
        ip = client_data['ip']
        port = client_data.get('port', 8118)
        
        print(f"🏷️  Client details: {hostname} ({ip}:{port})")
        
        # Read current config
        print(f"📖 Reading Prometheus config from: {PROMETHEUS_CONFIG}")
        with open(PROMETHEUS_CONFIG, 'r') as f:
            config = yaml.safe_load(f)
        
        print(f"📋 Current scrape configs: {len(config['scrape_configs'])} jobs")
        for job in config['scrape_configs']:
            print(f"   - {job['job_name']}: {job['static_configs'][0]['targets']}")
        
        # Check if job already exists
        job_name = f'client-{hostname}'
        existing_job = None
        for job in config['scrape_configs']:
            if job['job_name'] == job_name:
                existing_job = job
                break
        
        if existing_job:
            # Update existing job
            old_targets = existing_job['static_configs'][0]['targets']
            existing_job['static_configs'][0]['targets'] = [f'{ip}:{port}']
            print(f"🔄 Updated job '{job_name}': {old_targets} → [{ip}:{port}]")
        else:
            # Add new job
            new_job = {
                'job_name': job_name,
                'static_configs': [{'targets': [f'{ip}:{port}']}],
                'scrape_interval': '15s'
            }
            config['scrape_configs'].append(new_job)
            print(f"➕ Added new job '{job_name}' with target: {ip}:{port}")
        
        # Write updated config
        print(f"💾 Writing updated config to: {PROMETHEUS_CONFIG}")
        with open(PROMETHEUS_CONFIG, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        print(f"📋 Final scrape configs: {len(config['scrape_configs'])} jobs")
        for job in config['scrape_configs']:
            print(f"   - {job['job_name']}: {job['static_configs'][0]['targets']}")
        
        # Check client connectivity before reload
        client_reachable = check_client_connectivity(ip, port)
        
        # Reload Prometheus
        print("🔄 Reloading Prometheus configuration...")
        reload_prometheus()
        
        # Final status
        if client_reachable:
            print(f"✅ Client {hostname} registration completed successfully\n")
            return jsonify({"status": "success", "message": f"Client {hostname} registered and reachable"})
        else:
            print(f"⚠️ Client {hostname} registered but not reachable\n")
            return jsonify({"status": "warning", "message": f"Client {hostname} registered but endpoint not reachable"})
        
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def reload_prometheus():
    """Reload Prometheus configuration"""
    try:
        print("🔄 Sending reload request to Prometheus...")
        import requests
        response = requests.post('http://localhost:9090/-/reload', timeout=10)
        print(f"📡 Prometheus reload response: {response.status_code}")
        if response.status_code == 200:
            print("✅ Prometheus configuration reloaded successfully")
            # Verify targets after reload
            verify_prometheus_targets()
        else:
            print(f"❌ Prometheus reload failed with status: {response.status_code}")
            print(f"📄 Response text: {response.text}")
    except Exception as e:
        print(f"❌ Failed to reload Prometheus: {e}")
        print("💡 Make sure Prometheus is running with --web.enable-lifecycle flag")

def verify_prometheus_targets():
    """Verify that targets are loaded in Prometheus"""
    try:
        print("🎯 Verifying Prometheus targets...")
        import requests
        import time
        
        # Wait a moment for reload to complete
        time.sleep(2)
        
        response = requests.get('http://localhost:9090/api/v1/targets', timeout=10)
        if response.status_code == 200:
            targets_data = response.json()
            active_targets = targets_data.get('data', {}).get('activeTargets', [])
            
            print(f"🎯 Found {len(active_targets)} active targets in Prometheus:")
            for target in active_targets:
                job = target.get('labels', {}).get('job', 'unknown')
                instance = target.get('labels', {}).get('instance', 'unknown')
                health = target.get('health', 'unknown')
                print(f"   - Job: {job}, Instance: {instance}, Health: {health}")
        else:
            print(f"❌ Failed to get targets from Prometheus: {response.status_code}")
    except Exception as e:
        print(f"❌ Failed to verify Prometheus targets: {e}")

def check_client_connectivity(ip, port):
    """Check if client endpoint is reachable"""
    try:
        print(f"🔍 Checking client connectivity: {ip}:{port}")
        import requests
        response = requests.get(f'http://{ip}:{port}/metrics', timeout=5)
        if response.status_code == 200:
            print(f"✅ Client {ip}:{port} is reachable and serving metrics")
            # Show first few lines of metrics
            lines = response.text.split('\n')[:5]
            print(f"📈 Sample metrics:")
            for line in lines:
                if line.strip():
                    print(f"   {line}")
            return True
        else:
            print(f"⚠️ Client {ip}:{port} responded with status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot reach client {ip}:{port}: {e}")
        return False

@app.route('/clients', methods=['GET'])
def list_clients():
    """List registered clients with status"""
    try:
        print("📋 Listing registered clients...")
        
        # Get clients from config file
        with open(PROMETHEUS_CONFIG, 'r') as f:
            config = yaml.safe_load(f)
        
        clients = []
        for job in config['scrape_configs']:
            if job['job_name'].startswith('client-'):
                for static_config in job['static_configs']:
                    for target in static_config['targets']:
                        ip, port = target.split(':')
                        reachable = check_client_connectivity(ip, int(port))
                        clients.append({
                            'job_name': job['job_name'],
                            'target': target,
                            'reachable': reachable
                        })
        
        print(f"📋 Found {len(clients)} registered clients")
        return jsonify({"clients": clients})
    except Exception as e:
        print(f"❌ Error listing clients: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/metrics', methods=['POST'])
def receive_metrics():
    """Receive pushed metrics from clients"""
    try:
        metrics_data = request.json
        client_id = metrics_data['client_id']
        
        # Store metrics with timestamp
        metrics_store[client_id] = {
            'hostname': metrics_data['hostname'],
            'timestamp': metrics_data['timestamp'],
            'metrics': metrics_data['metrics'],
            'last_seen': int(time.time())
        }
        
        print(f"✅ Received metrics from {client_id}: CPU={metrics_data['metrics']['cpu_usage']}%")
        return jsonify({"status": "success", "message": "Metrics received"})
    except Exception as e:
        print(f"❌ Error receiving metrics: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/metrics', methods=['GET'])
def export_metrics():
    """Export metrics in Prometheus format"""
    try:
        prometheus_metrics = []
        current_time = int(time.time())
        
        for client_id, data in metrics_store.items():
            # Skip stale metrics (older than 60 seconds)
            if current_time - data['last_seen'] > 60:
                continue
                
            hostname = data['hostname']
            metrics = data['metrics']
            
            # Format metrics in Prometheus format
            prometheus_metrics.extend([
                f'host_cpu_usage{{client_id="{client_id}",hostname="{hostname}"}} {metrics["cpu_usage"]}',
                f'host_memory_usage{{client_id="{client_id}",hostname="{hostname}"}} {metrics["memory_usage"]}',
                f'host_disk_usage{{client_id="{client_id}",hostname="{hostname}"}} {metrics["disk_usage"]}',
                f'mysql_active_connections{{client_id="{client_id}",hostname="{hostname}"}} {metrics["mysql_connections"]}',
                f'videos_processed_total{{client_id="{client_id}",hostname="{hostname}"}} {metrics["videos_processed"]}',
                f'videos_error_total{{client_id="{client_id}",hostname="{hostname}"}} {metrics.get("videos_error", 0)}',
                f'site_statics_total{{client_id="{client_id}",hostname="{hostname}"}} {metrics.get("site_statics", 0)}',
                f'videos_not_processed_total{{client_id="{client_id}",hostname="{hostname}"}} {metrics.get("videos_not_processed", 0)}'
            ])
        
        return '\n'.join(prometheus_metrics) + '\n', 200, {'Content-Type': 'text/plain'}
    except Exception as e:
        print(f"❌ Error exporting metrics: {e}")
        return f"# Error: {e}\n", 500, {'Content-Type': 'text/plain'}

@app.route('/status', methods=['GET'])
def system_status():
    """Get system status including active clients"""
    try:
        print("🔍 Checking system status...")
        
        current_time = int(time.time())
        active_clients = []
        
        for client_id, data in metrics_store.items():
            age = current_time - data['last_seen']
            active_clients.append({
                'client_id': client_id,
                'hostname': data['hostname'],
                'last_seen': age,
                'active': age < 60
            })
        
        status = {
            'total_clients': len(metrics_store),
            'active_clients': len([c for c in active_clients if c['active']]),
            'clients': active_clients
        }
        
        print(f"📈 System status: {len(active_clients)} clients")
        return jsonify(status)
    except Exception as e:
        print(f"❌ Error getting system status: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting registration server on port 5001")
    print(f"📁 Prometheus config file: {PROMETHEUS_CONFIG}")
    print(f"📊 Prometheus should be accessible at: http://localhost:9090")
    print(f"🔧 Registration API available at: http://0.0.0.0:5001")
    app.run(host='0.0.0.0', port=5001, debug=True)