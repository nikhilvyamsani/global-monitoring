#!/usr/bin/env python3
from flask import Flask, request, jsonify
import yaml
import os
import subprocess
import time
from collections import defaultdict
from datetime import datetime, date
from logging import basicConfig, getLogger, INFO

basicConfig(level=INFO)
logger = getLogger(__name__)

app = Flask(__name__)
PROMETHEUS_CONFIG = '/app/central-prometheus.yml'

# In-memory storage for pushed metrics
metrics_store = defaultdict(dict)
DB_CONFIG = {
    'host': '192.168.2.34',
    'user': 'root',
    'password': 'Seekright@123',
    'database': 'metrics',
    'port': 3306
}

def get_db_connection():
    """Establish a connection to the database"""
    import mysql.connector
    return mysql.connector.connect(**DB_CONFIG)

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

def store_combined_metrics_to_db(cursor, client_id, metrics_data):
    """Store combined metrics (both created_on and video_date) to database tables"""
    try:
        # Extract dates from payload
        current_date_str = metrics_data['current_date']  # For created_on tables
        video_date_str = metrics_data['video_date']      # For video_date tables
        
        print(f"📝 Storing COMBINED metrics to database")
        print(f"   📅 Current date (created_on tables): {current_date_str}")
        print(f"   📅 Video date (video_date tables): {video_date_str}")
        
        metrics = metrics_data['metrics']
        
        # ========== OVERALL CREATED_ON METRICS ==========
        print(f"📝 Storing created_on_metrics with date: {current_date_str}")
        cursor.execute("""
            INSERT INTO created_on_metrics (
                client_id, date, videos_processed, videos_error, site_statics, 
                videos_not_processed, ASP, ASN
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                videos_processed = VALUES(videos_processed),
                videos_error = VALUES(videos_error),
                site_statics = VALUES(site_statics),
                videos_not_processed = VALUES(videos_not_processed),
                ASP = VALUES(ASP),
                ASN = VALUES(ASN)
        """, (
            client_id,
            current_date_str,
            metrics.get('videos_processed_created_on', 0),
            metrics.get('videos_error_created_on', 0),
            metrics.get('site_statics_created_on', 0),
            metrics.get('videos_not_processed_created_on', 0),
            metrics.get('positives_created_on', 0),
            metrics.get('negatives_created_on', 0)
        ))
        
        created_on_overall = {
            'processed': metrics.get('videos_processed_created_on', 0),
            'error': metrics.get('videos_error_created_on', 0),
            'site_statics': metrics.get('site_statics_created_on', 0),
            'not_processed': metrics.get('videos_not_processed_created_on', 0),
            'positives': metrics.get('positives_created_on', 0),
            'negatives': metrics.get('negatives_created_on', 0)
        }
        print(f"✅ created_on_metrics stored: {created_on_overall}")
        
        # ========== OVERALL VIDEO_DATE METRICS ==========
        print(f"📝 Storing video_date_metrics with date: {video_date_str}")
        cursor.execute("""
            INSERT INTO video_date_metrics (
                client_id, date, videos_processed, videos_error, site_statics, 
                videos_not_processed, ASP, ASN
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                videos_processed = VALUES(videos_processed),
                videos_error = VALUES(videos_error),
                site_statics = VALUES(site_statics),
                videos_not_processed = VALUES(videos_not_processed),
                ASP = VALUES(ASP),
                ASN = VALUES(ASN)
        """, (
            client_id,
            video_date_str,
            metrics.get('videos_processed_video_date', 0),
            metrics.get('videos_error_video_date', 0),
            metrics.get('site_statics_video_date', 0),
            metrics.get('videos_not_processed_video_date', 0),
            metrics.get('positives_video_date', 0),
            metrics.get('negatives_video_date', 0)
        ))
        
        video_date_overall = {
            'processed': metrics.get('videos_processed_video_date', 0),
            'error': metrics.get('videos_error_video_date', 0),
            'site_statics': metrics.get('site_statics_video_date', 0),
            'not_processed': metrics.get('videos_not_processed_video_date', 0),
            'positives': metrics.get('positives_video_date', 0),
            'negatives': metrics.get('negatives_video_date', 0)
        }
        print(f"✅ video_date_metrics stored: {video_date_overall}")
        
        # ========== ASSET-SPECIFIC METRICS ==========
        asset_types = ['linear', 'fixed', 'electrical']
        
        for asset_type in asset_types:
            print(f"📝 Processing {asset_type} asset metrics...")
            
            # Store asset_type_created_on_metrics
            print(f"📝 Storing {asset_type}_created_on_metrics with date: {current_date_str}")
            cursor.execute(f"""
                INSERT INTO {asset_type}_created_on_metrics (
                    client_id, date, videos_processed, videos_error, site_statics, 
                    videos_not_processed, ASP, ASN
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    videos_processed = VALUES(videos_processed),
                    videos_error = VALUES(videos_error),
                    site_statics = VALUES(site_statics),
                    videos_not_processed = VALUES(videos_not_processed),
                    ASP = VALUES(ASP),
                    ASN = VALUES(ASN)
            """, (
                client_id,
                current_date_str,
                metrics.get(f'{asset_type}_videos_processed_created_on', 0),
                metrics.get(f'{asset_type}_videos_error_created_on', 0),
                metrics.get(f'{asset_type}_site_statics_created_on', 0),
                metrics.get(f'{asset_type}_videos_not_processed_created_on', 0),
                metrics.get(f'{asset_type}_positives_created_on', 0),
                metrics.get(f'{asset_type}_negatives_created_on', 0)
            ))
            
            asset_created_on = {
                'processed': metrics.get(f'{asset_type}_videos_processed_created_on', 0),
                'error': metrics.get(f'{asset_type}_videos_error_created_on', 0),
                'site_statics': metrics.get(f'{asset_type}_site_statics_created_on', 0),
                'not_processed': metrics.get(f'{asset_type}_videos_not_processed_created_on', 0),
                'positives': metrics.get(f'{asset_type}_positives_created_on', 0),
                'negatives': metrics.get(f'{asset_type}_negatives_created_on', 0)
            }
            print(f"✅ {asset_type}_created_on_metrics stored: {asset_created_on}")
            
            # Store asset_type_video_date_metrics
            print(f"📝 Storing {asset_type}_video_date_metrics with date: {video_date_str}")
            cursor.execute(f"""
                INSERT INTO {asset_type}_video_date_metrics (
                    client_id, date, videos_processed, videos_error, site_statics, 
                    videos_not_processed, ASP, ASN
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    videos_processed = VALUES(videos_processed),
                    videos_error = VALUES(videos_error),
                    site_statics = VALUES(site_statics),
                    videos_not_processed = VALUES(videos_not_processed),
                    ASP = VALUES(ASP),
                    ASN = VALUES(ASN)
            """, (
                client_id,
                video_date_str,
                metrics.get(f'{asset_type}_videos_processed_video_date', 0),
                metrics.get(f'{asset_type}_videos_error_video_date', 0),
                metrics.get(f'{asset_type}_site_statics_video_date', 0),
                metrics.get(f'{asset_type}_videos_not_processed_video_date', 0),
                metrics.get(f'{asset_type}_positives_video_date', 0),
                metrics.get(f'{asset_type}_negatives_video_date', 0)
            ))
            
            asset_video_date = {
                'processed': metrics.get(f'{asset_type}_videos_processed_video_date', 0),
                'error': metrics.get(f'{asset_type}_videos_error_video_date', 0),
                'site_statics': metrics.get(f'{asset_type}_site_statics_video_date', 0),
                'not_processed': metrics.get(f'{asset_type}_videos_not_processed_video_date', 0),
                'positives': metrics.get(f'{asset_type}_positives_video_date', 0),
                'negatives': metrics.get(f'{asset_type}_negatives_video_date', 0)
            }
            print(f"✅ {asset_type}_video_date_metrics stored: {asset_video_date}")
        
        print(f"✅ All COMBINED metrics stored successfully to 8 database tables")
        return True
        
    except Exception as e:
        print(f"❌ Error storing combined metrics: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        raise e

@app.route('/metrics', methods=['POST'])
def receive_metrics():
    """Receive combined pushed metrics from clients (both created_on and video_date in one request)"""
    try:
        print(f"\n📥 Received COMBINED metrics request at {datetime.now()}")
        
        # Validate request data
        if not request.json:
            print("❌ No JSON data in request")
            return jsonify({"error": "No JSON data provided"}), 400
            
        metrics_data = request.json
        print(f"📊 Raw metrics data keys: {list(metrics_data.keys())}")
        
        # Validate required fields for combined metrics
        required_fields = ['client_id', 'hostname', 'timestamp', 'video_date', 'current_date', 'metric_type', 'metrics']
        for field in required_fields:
            if field not in metrics_data:
                print(f"❌ Missing required field: {field}")
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        client_id = metrics_data['client_id']
        hostname = metrics_data['hostname']
        timestamp = metrics_data['timestamp']
        video_date_str = metrics_data['video_date']
        current_date_str = metrics_data['current_date']
        metric_type = metrics_data['metric_type']  # Should be 'combined'
        
        print(f"🏷️ Client: {client_id} ({hostname})")
        print(f"📅 Timestamp: {timestamp}")
        print(f"📊 Metric Type: {metric_type}")
        print(f"📅 Current Date (created_on): {current_date_str}")
        print(f"📅 Video Date (video_date): {video_date_str}")
        
        if metric_type != 'combined':
            print(f"⚠️ Expected metric_type 'combined', got '{metric_type}'")
        
        # Handle timestamp conversion
        if isinstance(timestamp, str):
            try:
                timestamp_dt = datetime.strptime(timestamp, '%Y-%m-%d')
            except ValueError:
                print(f"❌ Invalid timestamp format: {timestamp}")
                return jsonify({"error": "Invalid timestamp format. Expected 'YYYY-MM-DD'."}), 400
        else:
            timestamp_dt = datetime.now()
        
        # Create storage key for combined metrics
        storage_key = f"{client_id}_{video_date_str}_combined"
        
        # Store metrics with timestamp
        metrics_store[storage_key] = {
            'client_id': client_id,
            'hostname': hostname,
            'timestamp': timestamp_dt,
            'metric_type': metric_type,
            'video_date': video_date_str,
            'current_date': current_date_str,
            'metrics': metrics_data['metrics'],
            'last_seen': int(time.time())
        }
        
        print(f"💾 Stored combined metrics in memory for {storage_key}")
        
        # Verify expected combined metrics are present
        expected_system_metrics = ['cpu_usage', 'memory_usage', 'disk_usage', 'mysql_connections']
        expected_created_on_metrics = [
            'videos_processed_created_on', 'videos_error_created_on', 'site_statics_created_on',
            'videos_not_processed_created_on', 'positives_created_on', 'negatives_created_on'
        ]
        expected_video_date_metrics = [
            'videos_processed_video_date', 'videos_error_video_date', 'site_statics_video_date',
            'videos_not_processed_video_date', 'positives_video_date', 'negatives_video_date'
        ]
        expected_asset_metrics = []
        for asset in ['linear', 'fixed', 'electrical']:
            for metric in ['videos_processed', 'videos_error', 'site_statics', 'videos_not_processed', 'positives', 'negatives']:
                expected_asset_metrics.append(f'{asset}_{metric}_created_on')
                expected_asset_metrics.append(f'{asset}_{metric}_video_date')
        
        all_expected = expected_system_metrics + expected_created_on_metrics + expected_video_date_metrics + expected_asset_metrics
        missing_metrics = [m for m in all_expected if m not in metrics_data['metrics']]
        
        if missing_metrics:
            print(f"⚠️ Missing some expected metrics: {missing_metrics[:5]}... (showing first 5)")
        else:
            print("✅ All expected combined metrics present")
        
        # Get database connection and store metrics
        try:
            db_conn = get_db_connection()
            if not db_conn:
                print("❌ Failed to connect to database")
                return jsonify({"error": "Database connection failed"}), 500
                
            cursor = db_conn.cursor()
            
            # Store combined metrics to database (updates 8 tables)
            store_combined_metrics_to_db(cursor, client_id, metrics_data)
            
            # Commit all changes
            db_conn.commit()
            print("💾 All combined metrics committed to database")
            
        except Exception as e:
            print(f"❌ Database operation failed: {e}")
            if 'db_conn' in locals():
                db_conn.rollback()
            return jsonify({"error": f"Database operation failed: {str(e)}"}), 500
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'db_conn' in locals():
                db_conn.close()
        
        # Log success with key metrics
        cpu_usage = metrics_data['metrics'].get('cpu_usage', 'N/A')
        overall_created_on = metrics_data['metrics'].get('videos_processed_created_on', 'N/A')
        overall_video_date = metrics_data['metrics'].get('videos_processed_video_date', 'N/A')
        linear_created_on = metrics_data['metrics'].get('linear_videos_processed_created_on', 'N/A')
        linear_video_date = metrics_data['metrics'].get('linear_videos_processed_video_date', 'N/A')
        
        logger.info(f"✅ Received combined metrics from {client_id} for video_date {video_date_str}: CPU={cpu_usage}%, Overall_CO={overall_created_on}, Overall_VD={overall_video_date}, Linear_CO={linear_created_on}, Linear_VD={linear_video_date}")
        
        print(f"✅ Successfully processed COMBINED metrics from {client_id}")
        print(f"📊 Database Storage Summary:")
        print(f"   📅 Video Date: {video_date_str}")
        print(f"   📅 Current Date: {current_date_str}")
        print(f"   🗄️  Tables Updated (8 total):")
        print(f"      📅 created_on_metrics → {current_date_str}")
        print(f"      📅 video_date_metrics → {video_date_str}")
        print(f"      📅 linear_created_on_metrics → {current_date_str}")
        print(f"      📅 linear_video_date_metrics → {video_date_str}")
        print(f"      📅 fixed_created_on_metrics → {current_date_str}")
        print(f"      📅 fixed_video_date_metrics → {video_date_str}")
        print(f"      📅 electrical_created_on_metrics → {current_date_str}")
        print(f"      📅 electrical_video_date_metrics → {video_date_str}")
        print(f"   📊 Key Metrics Summary:")
        print(f"      🔢 Overall created_on processed: {overall_created_on}")
        print(f"      🔢 Overall video_date processed: {overall_video_date}")
        print(f"      🎯 Linear created_on processed: {linear_created_on}")
        print(f"      🎯 Linear video_date processed: {linear_video_date}")
        print(f"      🎯 Fixed created_on processed: {metrics_data['metrics'].get('fixed_videos_processed_created_on', 'N/A')}")
        print(f"      🎯 Fixed video_date processed: {metrics_data['metrics'].get('fixed_videos_processed_video_date', 'N/A')}")
        print(f"      🎯 Electrical created_on processed: {metrics_data['metrics'].get('electrical_videos_processed_created_on', 'N/A')}")
        print(f"      🎯 Electrical video_date processed: {metrics_data['metrics'].get('electrical_videos_processed_video_date', 'N/A')}")
        
        return jsonify({
            "status": "success", 
            "message": "Combined metrics received and stored successfully",
            "client_id": client_id,
            "timestamp": timestamp_dt.isoformat(),
            "metric_type": metric_type,
            "current_date": current_date_str,
            "video_date": video_date_str,
            "storage_key": storage_key,
            "tables_updated": 8,
            "metrics_included": {
                "system_metrics": True,
                "created_on_metrics": True,
                "video_date_metrics": True,
                "asset_specific_metrics": True
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Error receiving combined metrics: {e}")
        print(f"❌ Error in receive_metrics: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/metrics', methods=['GET'])
def export_metrics():
    """Export metrics in Prometheus format"""
    try:
        prometheus_metrics = []
        current_time = int(time.time())
        
        for storage_key, data in metrics_store.items():
            # Skip stale metrics (older than  4hrs)
            if current_time - data['last_seen'] > 14400: 
                continue
                
            client_id = data['client_id']
            hostname = data['hostname']
            metric_type = data['metric_type']
            video_date = data.get('video_date', 'N/A')
            current_date = data.get('current_date', 'N/A')
            metrics = data['metrics']
            
            # Base labels for combined metrics
            base_labels = f'client_id="{client_id}",hostname="{hostname}",metric_type="{metric_type}",video_date="{video_date}",current_date="{current_date}"'
            
            # Format metrics in Prometheus format
            prometheus_metrics.extend([
                # System metrics
                f'host_cpu_usage{{{base_labels}}} {metrics.get("cpu_usage", 0)}',
                f'host_memory_usage{{{base_labels}}} {metrics.get("memory_usage", 0)}',
                f'host_disk_usage{{{base_labels}}} {metrics.get("disk_usage", 0)}',
                f'mysql_active_connections{{{base_labels}}} {metrics.get("mysql_connections", 0)}',

                f'videos_processed{{{base_labels}}} {metrics.get("videos_processed", 0)}',
                f'videos_error{{{base_labels}}} {metrics.get("videos_error", 0)}',
                f'site_statics{{{base_labels}}} {metrics.get("site_statics", 0)}',
                f'videos_not_processed{{{base_labels}}} {metrics.get("videos_not_processed", 0)}',
                f'positives{{{base_labels}}} {metrics.get("positives", 0)}',
                f'negatives{{{base_labels}}} {metrics.get("negatives", 0)}',
                
                # Overall created_on metrics
                f'videos_processed_created_on{{{base_labels}}} {metrics.get("videos_processed_created_on", 0)}',
                f'videos_error_created_on{{{base_labels}}} {metrics.get("videos_error_created_on", 0)}',
                f'site_statics_created_on{{{base_labels}}} {metrics.get("site_statics_created_on", 0)}',
                f'videos_not_processed_created_on{{{base_labels}}} {metrics.get("videos_not_processed_created_on", 0)}',
                f'positives_created_on{{{base_labels}}} {metrics.get("positives_created_on", 0)}',
                f'negatives_created_on{{{base_labels}}} {metrics.get("negatives_created_on", 0)}',
                
                # Overall video_date metrics
                f'videos_processed_video_date{{{base_labels}}} {metrics.get("videos_processed_video_date", 0)}',
                f'videos_error_video_date{{{base_labels}}} {metrics.get("videos_error_video_date", 0)}',
                f'site_statics_video_date{{{base_labels}}} {metrics.get("site_statics_video_date", 0)}',
                f'videos_not_processed_video_date{{{base_labels}}} {metrics.get("videos_not_processed_video_date", 0)}',
                f'positives_video_date{{{base_labels}}} {metrics.get("positives_video_date", 0)}',
                f'negatives_video_date{{{base_labels}}} {metrics.get("negatives_video_date", 0)}'
            ])
            
            # Asset type specific metrics (both created_on and video_date)
            asset_types = ['linear', 'fixed', 'electrical']
            for asset in asset_types:
                asset_labels = f'{base_labels},asset_type="{asset}"'
                prometheus_metrics.extend([
                    # Asset created_on metrics
                    f'{asset}_videos_processed_created_on{{{asset_labels}}} {metrics.get(f"{asset}_videos_processed_created_on", 0)}',
                    f'{asset}_videos_error_created_on{{{asset_labels}}} {metrics.get(f"{asset}_videos_error_created_on", 0)}',
                    f'{asset}_site_statics_created_on{{{asset_labels}}} {metrics.get(f"{asset}_site_statics_created_on", 0)}',
                    f'{asset}_videos_not_processed_created_on{{{asset_labels}}} {metrics.get(f"{asset}_videos_not_processed_created_on", 0)}',
                    f'{asset}_positives_created_on{{{asset_labels}}} {metrics.get(f"{asset}_positives_created_on", 0)}',
                    f'{asset}_negatives_created_on{{{asset_labels}}} {metrics.get(f"{asset}_negatives_created_on", 0)}',
                    
                    # Asset video_date metrics
                    f'{asset}_videos_processed_video_date{{{asset_labels}}} {metrics.get(f"{asset}_videos_processed_video_date", 0)}',
                    f'{asset}_videos_error_video_date{{{asset_labels}}} {metrics.get(f"{asset}_videos_error_video_date", 0)}',
                    f'{asset}_site_statics_video_date{{{asset_labels}}} {metrics.get(f"{asset}_site_statics_video_date", 0)}',
                    f'{asset}_videos_not_processed_video_date{{{asset_labels}}} {metrics.get(f"{asset}_videos_not_processed_video_date", 0)}',
                    f'{asset}_positives_video_date{{{asset_labels}}} {metrics.get(f"{asset}_positives_video_date", 0)}',
                    f'{asset}_negatives_video_date{{{asset_labels}}} {metrics.get(f"{asset}_negatives_video_date", 0)}'
                ])
        
        return '\n'.join(prometheus_metrics) + '\n', 200, {'Content-Type': 'text/plain'}
    except Exception as e:
        print(f"❌ Error exporting metrics: {e}")
        return f"# Error: {e}\n", 500, {'Content-Type': 'text/plain'}

@app.route('/status', methods=['GET'])
def system_status():
    """Get system status including active clients and their combined metrics"""
    try:
        print("🔍 Checking combined system status...")
        
        current_time = int(time.time())
        active_metrics = []
        
        for storage_key, data in metrics_store.items():
            age = current_time - data['last_seen']
            active_metrics.append({
                'storage_key': storage_key,
                'client_id': data['client_id'],
                'hostname': data['hostname'],
                'metric_type': data['metric_type'],
                'video_date': data.get('video_date', 'N/A'),
                'current_date': data.get('current_date', 'N/A'),
                'timestamp': data['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'last_seen': age,
                'active': age < 60,
                'tables_covered': 8 if data['metric_type'] == 'combined' else 1
            })
        
        # Group by client_id to show summary
        clients_summary = {}
        for metric in active_metrics:
            client_id = metric['client_id']
            if client_id not in clients_summary:
                clients_summary[client_id] = {
                    'hostname': metric['hostname'],
                    'combined_metrics': [],
                    'active_combined_metrics': 0,
                    'total_tables_covered': 0
                }
            clients_summary[client_id]['combined_metrics'].append({
                'video_date': metric['video_date'],
                'current_date': metric['current_date'],
                'timestamp': metric['timestamp'],
                'active': metric['active'],
                'tables_covered': metric['tables_covered']
            })
            if metric['active']:
                clients_summary[client_id]['active_combined_metrics'] += 1
                clients_summary[client_id]['total_tables_covered'] += metric['tables_covered']
        
        status = {
            'total_combined_metrics': len(metrics_store),
            'active_combined_metrics': len([m for m in active_metrics if m['active']]),
            'unique_clients': len(clients_summary),
            'total_active_tables_covered': sum(c['total_tables_covered'] for c in clients_summary.values()),
            'clients_summary': clients_summary,
            'all_combined_metrics': active_metrics
        }
        
        print(f"📈 Combined system status:")
        print(f"   🔢 Total combined metrics: {len(active_metrics)}")
        print(f"   ✅ Active combined metrics: {len([m for m in active_metrics if m['active']])}")
        print(f"   👥 Unique clients: {len(clients_summary)}")
        print(f"   🗄️  Total active database tables covered: {status['total_active_tables_covered']}")
        
        return jsonify(status)
    except Exception as e:
        print(f"❌ Error getting system status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/combined_metrics', methods=['GET'])
def list_combined_metrics():
    """List all combined metrics being monitored"""
    try:
        print("📋 Listing all combined metrics...")
        
        current_time = int(time.time())
        combined_metrics_list = []
        
        for storage_key, data in metrics_store.items():
            age = current_time - data['last_seen']
            
            # Get key metrics for this combined entry
            metrics = data['metrics']
            combined_info = {
                'storage_key': storage_key,
                'client_id': data['client_id'],
                'hostname': data['hostname'],
                'metric_type': data['metric_type'],
                'timestamp': data['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'video_date': data.get('video_date', 'N/A'),
                'current_date': data.get('current_date', 'N/A'),
                'last_seen_seconds': age,
                'active': age < 60,
                'tables_updated': 8,
                'key_metrics': {
                    'cpu_usage': metrics.get('cpu_usage', 0),
                    'mysql_connections': metrics.get('mysql_connections', 0),
                    'overall_created_on_processed': metrics.get('videos_processed_created_on', 0),
                    'overall_video_date_processed': metrics.get('videos_processed_video_date', 0),
                    'linear_created_on_processed': metrics.get('linear_videos_processed_created_on', 0),
                    'linear_video_date_processed': metrics.get('linear_videos_processed_video_date', 0),
                    'fixed_created_on_processed': metrics.get('fixed_videos_processed_created_on', 0),
                    'fixed_video_date_processed': metrics.get('fixed_videos_processed_video_date', 0),
                    'electrical_created_on_processed': metrics.get('electrical_videos_processed_created_on', 0),
                    'electrical_video_date_processed': metrics.get('electrical_videos_processed_video_date', 0)
                }
            }
            combined_metrics_list.append(combined_info)
        
        # Sort by timestamp for better readability
        combined_metrics_list.sort(key=lambda x: x['timestamp'], reverse=True)
        
        response = {
            'total_combined_metrics': len(combined_metrics_list),
            'active_combined_metrics': len([m for m in combined_metrics_list if m['active']]),
            'total_database_tables_covered': len(combined_metrics_list) * 8,
            'combined_metrics': combined_metrics_list
        }
        
        print(f"📋 Found {len(combined_metrics_list)} combined metrics")
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ Error listing combined metrics: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/client/<client_id>/combined_metrics', methods=['GET'])
def get_client_combined_metrics(client_id):
    """Get all combined metrics for a specific client"""
    try:
        print(f"🔍 Getting combined metrics for client: {client_id}")
        
        current_time = int(time.time())
        client_combined_metrics = []
        
        for storage_key, data in metrics_store.items():
            if data['client_id'] == client_id:
                age = current_time - data['last_seen']
                client_combined_metrics.append({
                    'storage_key': storage_key,
                    'metric_type': data['metric_type'],
                    'timestamp': data['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                    'video_date': data.get('video_date', 'N/A'),
                    'current_date': data.get('current_date', 'N/A'),
                    'last_seen_seconds': age,
                    'active': age < 60,
                    'tables_updated': 8,
                    'metrics': data['metrics']
                })
        
        if not client_combined_metrics:
            print(f"⚠️ No combined metrics found for client: {client_id}")
            return jsonify({"error": f"Client {client_id} not found"}), 404
        
        # Sort by timestamp
        client_combined_metrics.sort(key=lambda x: x['timestamp'], reverse=True)
        
        response = {
            'client_id': client_id,
            'total_combined_metrics': len(client_combined_metrics),
            'active_combined_metrics': len([m for m in client_combined_metrics if m['active']]),
            'total_database_tables_covered': len(client_combined_metrics) * 8,
            'combined_metrics': client_combined_metrics
        }
        
        print(f"📊 Found {len(client_combined_metrics)} combined metrics for client {client_id}")
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ Error getting client combined metrics: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db_conn = get_db_connection()
        if db_conn:
            cursor = db_conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            db_conn.close()
            db_status = "healthy"
        else:
            db_status = "unhealthy"
        
        # Check metrics store
        current_time = int(time.time())
        active_count = len([
            data for data in metrics_store.values()
            if current_time - data['last_seen'] < 60
        ])
        
        health_status = {
            'status': 'healthy' if db_status == 'healthy' else 'degraded',
            'timestamp': datetime.now().isoformat(),
            'database': db_status,
            'metrics_store': {
                'total_combined_entries': len(metrics_store),
                'active_combined_entries': active_count,
                'total_database_tables_covered': active_count * 8
            },
            'prometheus_config_exists': os.path.exists(PROMETHEUS_CONFIG),
            'mode': 'combined_metrics'
        }
        
        status_code = 200 if health_status['status'] == 'healthy' else 503
        return jsonify(health_status), status_code
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 503

if __name__ == '__main__':
    print("🚀 Starting COMBINED monitoring server on port 5001")
    print(f"📁 Prometheus config file: {PROMETHEUS_CONFIG}")
    print(f"📊 Prometheus should be accessible at: http://localhost:9090")
    print(f"🔧 Registration API available at: http://0.0.0.0:5001")
    print("🗄️  Database tables mapping:")
    print("   📅 created_on_metrics (current_date)")
    print("   📅 video_date_metrics (video_date)")
    print("   📅 linear_created_on_metrics (current_date)")
    print("   📅 linear_video_date_metrics (video_date)")
    print("   📅 fixed_created_on_metrics (current_date)")
    print("   📅 fixed_video_date_metrics (video_date)")
    print("   📅 electrical_created_on_metrics (current_date)")
    print("   📅 electrical_video_date_metrics (video_date)")
    print("🔄 COMBINED monitoring mode:")
    print("   📊 Each request contains BOTH created_on AND video_date metrics")
    print("   🎯 Single loop: one request per video_date")
    print("   📈 Each request updates ALL 8 database tables")
    print("   🔍 Available endpoints:")
    print("      📊 GET /status - System status with combined metrics")
    print("      📋 GET /combined_metrics - List all combined metrics")
    print("      👤 GET /client/<id>/combined_metrics - Client-specific combined metrics")
    print("      💚 GET /health - Health check")
    app.run(host='0.0.0.0', port=5001, debug=True)