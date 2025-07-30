#!/usr/bin/env python3
import requests
import socket
import json
import time
import os
import psutil
import mysql.connector
from datetime import datetime, time as dt_time
import schedule

def get_public_ip():
    """Get the public IP address"""
    try:
        services = [
            "https://ifconfig.me/ip",
            "https://api.ipify.org",
            "https://icanhazip.com"
        ]
        
        for service in services:
            try:
                response = requests.get(service, timeout=10)
                if response.status_code == 200:
                    public_ip = response.text.strip()
                    print(f"✅ Detected public IP: {public_ip}")
                    return public_ip
            except Exception as e:
                print(f"⚠️ Failed to get IP from {service}: {e}")
                continue
        
        print("⚠️ All IP services failed, using local IP")
        return get_local_ip()
    except Exception as e:
        print(f"❌ Error in get_public_ip: {e}")
        return get_local_ip()

def get_local_ip():
    """Get the local IP address (fallback)"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        print(f"✅ Local IP detected: {ip}")
        return ip
    except Exception as e:
        print(f"⚠️ Local IP detection failed: {e}")
        fallback_ip = socket.gethostbyname(socket.gethostname())
        print(f"✅ Fallback IP: {fallback_ip}")
        return fallback_ip

def get_db_connection():
    """Establish a connection to the database with proper error handling"""
    try:
        db_host = os.getenv('DB_HOST', '192.168.2.34')
        db_user = os.getenv('DB_USER', 'root')
        db_password = os.getenv('DB_PASSWORD', 'password')
        db_name = os.getenv('DB_NAME', 'take_leap')
        db_port = int(os.getenv('DB_PORT', '3306'))
        
        print(f"🔌 Connecting to database: {db_host}:{db_port}/{db_name} as {db_user}")
        
        conn = mysql.connector.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            port=db_port,
            connect_timeout=10,
            autocommit=True,
            charset='utf8mb4',
            use_unicode=True
        )
        
        # Test connection
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        
        print(f"✅ Database connection successful: {db_host}:{db_port}/{db_name}")
        return conn
        
    except mysql.connector.Error as err:
        print(f"❌ Database connection error: {err}")
        return None
    except Exception as e:
        print(f"❌ Unexpected database error: {e}")
        return None

def test_table_access(cursor):
    """Test if we can access the video_uploads table"""
    try:
        cursor.execute("SELECT COUNT(*) FROM video_uploads LIMIT 1")
        count = cursor.fetchone()[0]
        print(f"✅ video_uploads table accessible, total records: {count}")
        return True
    except Exception as e:
        print(f"❌ Cannot access video_uploads table: {e}")
        return False

def get_combined_metrics(cursor, video_date):
    """Get both created_on and video_date metrics for a specific video_date in one comprehensive call"""
    try:
        video_date_str = video_date.strftime('%Y-%m-%d')
        current_date_str = datetime.now().strftime('%Y-%m-%d')
        
        print(f"📊 Collecting COMBINED metrics:")
        print(f"   📅 Video date: {video_date_str}")
        print(f"   📅 Current date: {current_date_str}")
        
        # Get active connections
        try:
            cursor.execute("SHOW STATUS LIKE 'Threads_connected'")
            result = cursor.fetchone()
            connections = int(result[1]) if result else 0
        except Exception as e:
            print(f"⚠️ Could not get connection count: {e}")
            connections = 0
        
        metrics = {
            'db_connections': connections,
            'video_date': video_date_str,
            'current_date': current_date_str,
            'metric_type': 'combined'  # New type indicating both metrics included
        }
        
        # ========== GENERIC METRICS (NO FILTERS) ==========
        print("📊 Collecting generic metrics (no filters)...")
        
        try:
            # Generic processed videos (no date filter)
            cursor.execute("SELECT COUNT(*) FROM video_uploads WHERE is_processed = 1 AND progress_value = 100")
            metrics['videos_processed'] = cursor.fetchone()[0]
            
            # Generic not processed videos (no date filter)
            cursor.execute("SELECT COUNT(*) FROM video_uploads WHERE is_processed = 0 OR progress_value < 100")
            metrics['videos_not_processed'] = cursor.fetchone()[0]
            
            # Generic error videos (no date filter)
            cursor.execute("SELECT COUNT(*) FROM video_uploads WHERE error_message IS NOT NULL")
            metrics['videos_error'] = cursor.fetchone()[0]
            
            # Generic site statics uploaded (no date filter)
            cursor.execute("SELECT COUNT(*) FROM video_uploads WHERE site_statics_uploaded = 1")
            metrics['site_statics'] = cursor.fetchone()[0]
            
            # Generic positives (no date filter)
            cursor.execute("SELECT COUNT(*) FROM video_uploads WHERE anomaly_uploaded = 1 AND site_statics_uploaded = 1")
            metrics['positives'] = cursor.fetchone()[0]
            
            # Generic negatives (no date filter)
            cursor.execute("SELECT COUNT(*) FROM video_uploads WHERE anomaly_uploaded < 1 OR site_statics_uploaded != 1")
            metrics['negatives'] = cursor.fetchone()[0]
            
            # Total videos count (no date filter)
            cursor.execute("SELECT COUNT(*) FROM video_uploads")
            metrics['total_videos'] = cursor.fetchone()[0]
            
            print(f"✅ Generic metrics: total={metrics['total_videos']}, processed={metrics['videos_processed']}, errors={metrics['videos_error']}")
        except Exception as e:
            print(f"❌ Error collecting generic metrics: {e}")
            metrics.update({
                'videos_processed': 0, 'videos_not_processed': 0, 'videos_error': 0,
                'site_statics': 0, 'positives': 0, 'negatives': 0, 'total_videos': 0
            })
        
        # ========== OVERALL METRICS (all asset types combined) ==========
        print("📊 Collecting overall metrics...")
        
        # Overall created_on metrics (CURDATE())
        try:
            cursor.execute("SELECT COUNT(*) FROM video_uploads WHERE (is_processed = 1 AND progress_value = 100) AND DATE(created_on) = CURDATE()")
            metrics['videos_processed_created_on'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM video_uploads WHERE error_message IS NOT NULL AND DATE(created_on) = CURDATE()")
            metrics['videos_error_created_on'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM video_uploads WHERE site_statics_uploaded = 1 AND DATE(created_on) = CURDATE()")
            metrics['site_statics_created_on'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM video_uploads WHERE (is_processed = 0 OR progress_value < 100) AND DATE(created_on) = CURDATE()")
            metrics['videos_not_processed_created_on'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM video_uploads WHERE (anomaly_uploaded = 1 AND site_statics_uploaded = 1) AND DATE(created_on) = CURDATE()")
            metrics['positives_created_on'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM video_uploads WHERE (anomaly_uploaded < 1 OR site_statics_uploaded != 1) AND DATE(created_on) = CURDATE()")
            metrics['negatives_created_on'] = cursor.fetchone()[0]
            
            print(f"✅ Overall created_on metrics: processed={metrics['videos_processed_created_on']}, errors={metrics['videos_error_created_on']}")
        except Exception as e:
            print(f"❌ Error collecting overall created_on metrics: {e}")
            metrics.update({
                'videos_processed_created_on': 0, 'videos_error_created_on': 0, 'site_statics_created_on': 0,
                'videos_not_processed_created_on': 0, 'positives_created_on': 0, 'negatives_created_on': 0
            })
        
        # Overall video_date metrics (for this specific video_date)
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM video_uploads
                WHERE (is_processed = 1 AND progress_value = 100)
                AND DATE(STR_TO_DATE(LEFT(file_name, 8), '%Y%m%d')) = %s
            """, (video_date,))
            metrics['videos_processed_video_date'] = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM video_uploads
                WHERE error_message IS NOT NULL
                AND DATE(STR_TO_DATE(LEFT(file_name, 8), '%Y%m%d')) = %s
            """, (video_date,))
            metrics['videos_error_video_date'] = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM video_uploads
                WHERE site_statics_uploaded = 1
                AND DATE(STR_TO_DATE(LEFT(file_name, 8), '%Y%m%d')) = %s
            """, (video_date,))
            metrics['site_statics_video_date'] = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM video_uploads
                WHERE (is_processed = 0 OR progress_value < 100)
                AND DATE(STR_TO_DATE(LEFT(file_name, 8), '%Y%m%d')) = %s
            """, (video_date,))
            metrics['videos_not_processed_video_date'] = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM video_uploads
                WHERE anomaly_uploaded = 1 AND site_statics_uploaded = 1
                AND DATE(STR_TO_DATE(LEFT(file_name, 8), '%Y%m%d')) = %s
            """, (video_date,))
            metrics['positives_video_date'] = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM video_uploads
                WHERE (anomaly_uploaded < 1 OR site_statics_uploaded != 1)
                AND DATE(STR_TO_DATE(LEFT(file_name, 8), '%Y%m%d')) = %s
            """, (video_date,))
            metrics['negatives_video_date'] = cursor.fetchone()[0]
            
            print(f"✅ Overall video_date metrics for {video_date_str}: processed={metrics['videos_processed_video_date']}, errors={metrics['videos_error_video_date']}")
        except Exception as e:
            print(f"❌ Error collecting overall video_date metrics: {e}")
            metrics.update({
                'videos_processed_video_date': 0, 'videos_error_video_date': 0, 'site_statics_video_date': 0,
                'videos_not_processed_video_date': 0, 'positives_video_date': 0, 'negatives_video_date': 0
            })
        
        # ========== ASSET-SPECIFIC METRICS ==========
        asset_types = {
            'linear': 'linear:other-linears',
            'fixed': 'fixed',
            'electrical': 'electrical-reflective'
        }
        
        for asset_key, asset_value in asset_types.items():
            print(f"📊 Collecting {asset_key} asset metrics...")
            
            # Asset-specific created_on metrics
            try:
                cursor.execute(f"""
                    SELECT COUNT(*) FROM video_uploads 
                    WHERE (is_processed = 1 AND progress_value = 100) 
                    AND DATE(created_on) = CURDATE() 
                    AND asset_type = %s
                """, (asset_value,))
                metrics[f'{asset_key}_videos_processed_created_on'] = cursor.fetchone()[0]
                
                cursor.execute(f"""
                    SELECT COUNT(*) FROM video_uploads 
                    WHERE error_message IS NOT NULL 
                    AND DATE(created_on) = CURDATE() 
                    AND asset_type = %s
                """, (asset_value,))
                metrics[f'{asset_key}_videos_error_created_on'] = cursor.fetchone()[0]
                
                cursor.execute(f"""
                    SELECT COUNT(*) FROM video_uploads 
                    WHERE site_statics_uploaded = 1 
                    AND DATE(created_on) = CURDATE() 
                    AND asset_type = %s
                """, (asset_value,))
                metrics[f'{asset_key}_site_statics_created_on'] = cursor.fetchone()[0]
                
                cursor.execute(f"""
                    SELECT COUNT(*) FROM video_uploads 
                    WHERE (is_processed = 0 OR progress_value < 100) 
                    AND DATE(created_on) = CURDATE() 
                    AND asset_type = %s
                """, (asset_value,))
                metrics[f'{asset_key}_videos_not_processed_created_on'] = cursor.fetchone()[0]
                
                cursor.execute(f"""
                    SELECT COUNT(*) FROM video_uploads 
                    WHERE (anomaly_uploaded = 1 AND site_statics_uploaded = 1) 
                    AND DATE(created_on) = CURDATE() 
                    AND asset_type = %s
                """, (asset_value,))
                metrics[f'{asset_key}_positives_created_on'] = cursor.fetchone()[0]
                
                cursor.execute(f"""
                    SELECT COUNT(*) FROM video_uploads 
                    WHERE (anomaly_uploaded < 1 OR site_statics_uploaded != 1) 
                    AND DATE(created_on) = CURDATE() 
                    AND asset_type = %s
                """, (asset_value,))
                metrics[f'{asset_key}_negatives_created_on'] = cursor.fetchone()[0]
                
                print(f"✅ {asset_key} created_on: processed={metrics[f'{asset_key}_videos_processed_created_on']}, errors={metrics[f'{asset_key}_videos_error_created_on']}")
                
            except Exception as e:
                print(f"❌ Error collecting {asset_key} created_on metrics: {e}")
                # Set defaults
                for metric_type in ['videos_processed', 'videos_error', 'site_statics', 'videos_not_processed', 'positives', 'negatives']:
                    metrics[f'{asset_key}_{metric_type}_created_on'] = 0
            
            # Asset-specific video_date metrics
            try:
                cursor.execute(f"""
                    SELECT COUNT(*) FROM video_uploads 
                    WHERE (is_processed = 1 AND progress_value = 100) 
                    AND DATE(STR_TO_DATE(LEFT(file_name, 8), '%Y%m%d')) = %s 
                    AND asset_type = %s
                """, (video_date, asset_value))
                metrics[f'{asset_key}_videos_processed_video_date'] = cursor.fetchone()[0]
                
                cursor.execute(f"""
                    SELECT COUNT(*) FROM video_uploads 
                    WHERE error_message IS NOT NULL 
                    AND DATE(STR_TO_DATE(LEFT(file_name, 8), '%Y%m%d')) = %s 
                    AND asset_type = %s
                """, (video_date, asset_value))
                metrics[f'{asset_key}_videos_error_video_date'] = cursor.fetchone()[0]
                
                cursor.execute(f"""
                    SELECT COUNT(*) FROM video_uploads 
                    WHERE site_statics_uploaded = 1 
                    AND DATE(STR_TO_DATE(LEFT(file_name, 8), '%Y%m%d')) = %s 
                    AND asset_type = %s
                """, (video_date, asset_value))
                metrics[f'{asset_key}_site_statics_video_date'] = cursor.fetchone()[0]
                
                cursor.execute(f"""
                    SELECT COUNT(*) FROM video_uploads 
                    WHERE (is_processed = 0 OR progress_value < 100) 
                    AND DATE(STR_TO_DATE(LEFT(file_name, 8), '%Y%m%d')) = %s 
                    AND asset_type = %s
                """, (video_date, asset_value))
                metrics[f'{asset_key}_videos_not_processed_video_date'] = cursor.fetchone()[0]
                
                cursor.execute(f"""
                    SELECT COUNT(*) FROM video_uploads 
                    WHERE (anomaly_uploaded = 1 AND site_statics_uploaded = 1) 
                    AND DATE(STR_TO_DATE(LEFT(file_name, 8), '%Y%m%d')) = %s 
                    AND asset_type = %s
                """, (video_date, asset_value))
                metrics[f'{asset_key}_positives_video_date'] = cursor.fetchone()[0]
                
                cursor.execute(f"""
                    SELECT COUNT(*) FROM video_uploads 
                    WHERE (anomaly_uploaded < 1 OR site_statics_uploaded != 1) 
                    AND DATE(STR_TO_DATE(LEFT(file_name, 8), '%Y%m%d')) = %s 
                    AND asset_type = %s
                """, (video_date, asset_value))
                metrics[f'{asset_key}_negatives_video_date'] = cursor.fetchone()[0]
                
                print(f"✅ {asset_key} video_date: processed={metrics[f'{asset_key}_videos_processed_video_date']}, errors={metrics[f'{asset_key}_videos_error_video_date']}")
                
            except Exception as e:
                print(f"❌ Error collecting {asset_key} video_date metrics: {e}")
                # Set defaults
                for metric_type in ['videos_processed', 'videos_error', 'site_statics', 'videos_not_processed', 'positives', 'negatives']:
                    metrics[f'{asset_key}_{metric_type}_video_date'] = 0
        
        print(f"✅ All COMBINED metrics collected successfully for video_date: {video_date_str}")
        return metrics
                
    except Exception as e:
        print(f"❌ Database error collecting combined metrics for {video_date}: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return None

def send_combined_metrics_to_server(central_host, client_id, hostname, metrics_data, cpu_percent, memory_percent, disk_percent):
    """Send combined metrics to server"""
    
    # Prepare complete combined metrics payload
    metrics_payload = {
        "client_id": client_id,
        "hostname": hostname,
        "timestamp": metrics_data['current_date'],
        "video_date": metrics_data['video_date'],
        "current_date": metrics_data['current_date'],
        "metric_type": "combined",  # Indicates both created_on and video_date metrics included
        "metrics": {
            # System metrics
            "cpu_usage": cpu_percent,
            "memory_usage": memory_percent,
            "disk_usage": disk_percent,
            "mysql_connections": metrics_data['db_connections'],

            # Generic metrics (no date filters)
            "videos_processed": metrics_data['videos_processed'],
            "videos_not_processed": metrics_data['videos_not_processed'],
            "videos_error": metrics_data['videos_error'],
            "site_statics": metrics_data['site_statics'],
            "positives": metrics_data['positives'],
            "negatives": metrics_data['negatives'],
            "total_videos": metrics_data['total_videos'],
            
            # Overall created_on metrics
            "videos_processed_created_on": metrics_data['videos_processed_created_on'],
            "videos_error_created_on": metrics_data['videos_error_created_on'],
            "site_statics_created_on": metrics_data['site_statics_created_on'],
            "videos_not_processed_created_on": metrics_data['videos_not_processed_created_on'],
            "positives_created_on": metrics_data['positives_created_on'],
            "negatives_created_on": metrics_data['negatives_created_on'],
            
            # Overall video_date metrics
            "videos_processed_video_date": metrics_data['videos_processed_video_date'],
            "videos_error_video_date": metrics_data['videos_error_video_date'],
            "site_statics_video_date": metrics_data['site_statics_video_date'],
            "videos_not_processed_video_date": metrics_data['videos_not_processed_video_date'],
            "positives_video_date": metrics_data['positives_video_date'],
            "negatives_video_date": metrics_data['negatives_video_date'],
            
            # Asset-specific created_on metrics
            "linear_videos_processed_created_on": metrics_data['linear_videos_processed_created_on'],
            "linear_videos_error_created_on": metrics_data['linear_videos_error_created_on'],
            "linear_site_statics_created_on": metrics_data['linear_site_statics_created_on'],
            "linear_videos_not_processed_created_on": metrics_data['linear_videos_not_processed_created_on'],
            "linear_positives_created_on": metrics_data['linear_positives_created_on'],
            "linear_negatives_created_on": metrics_data['linear_negatives_created_on'],
            
            "fixed_videos_processed_created_on": metrics_data['fixed_videos_processed_created_on'],
            "fixed_videos_error_created_on": metrics_data['fixed_videos_error_created_on'],
            "fixed_site_statics_created_on": metrics_data['fixed_site_statics_created_on'],
            "fixed_videos_not_processed_created_on": metrics_data['fixed_videos_not_processed_created_on'],
            "fixed_positives_created_on": metrics_data['fixed_positives_created_on'],
            "fixed_negatives_created_on": metrics_data['fixed_negatives_created_on'],
            
            "electrical_videos_processed_created_on": metrics_data['electrical_videos_processed_created_on'],
            "electrical_videos_error_created_on": metrics_data['electrical_videos_error_created_on'],
            "electrical_site_statics_created_on": metrics_data['electrical_site_statics_created_on'],
            "electrical_videos_not_processed_created_on": metrics_data['electrical_videos_not_processed_created_on'],
            "electrical_positives_created_on": metrics_data['electrical_positives_created_on'],
            "electrical_negatives_created_on": metrics_data['electrical_negatives_created_on'],
            
            # Asset-specific video_date metrics
            "linear_videos_processed_video_date": metrics_data['linear_videos_processed_video_date'],
            "linear_videos_error_video_date": metrics_data['linear_videos_error_video_date'],
            "linear_site_statics_video_date": metrics_data['linear_site_statics_video_date'],
            "linear_videos_not_processed_video_date": metrics_data['linear_videos_not_processed_video_date'],
            "linear_positives_video_date": metrics_data['linear_positives_video_date'],
            "linear_negatives_video_date": metrics_data['linear_negatives_video_date'],
            
            "fixed_videos_processed_video_date": metrics_data['fixed_videos_processed_video_date'],
            "fixed_videos_error_video_date": metrics_data['fixed_videos_error_video_date'],
            "fixed_site_statics_video_date": metrics_data['fixed_site_statics_video_date'],
            "fixed_videos_not_processed_video_date": metrics_data['fixed_videos_not_processed_video_date'],
            "fixed_positives_video_date": metrics_data['fixed_positives_video_date'],
            "fixed_negatives_video_date": metrics_data['fixed_negatives_video_date'],
            
            "electrical_videos_processed_video_date": metrics_data['electrical_videos_processed_video_date'],
            "electrical_videos_error_video_date": metrics_data['electrical_videos_error_video_date'],
            "electrical_site_statics_video_date": metrics_data['electrical_site_statics_video_date'],
            "electrical_videos_not_processed_video_date": metrics_data['electrical_videos_not_processed_video_date'],
            "electrical_positives_video_date": metrics_data['electrical_positives_video_date'],
            "electrical_negatives_video_date": metrics_data['electrical_negatives_video_date']
        }
    }
    
    # Print summary of key metrics
    print(f"📤 Sending COMBINED metrics for video_date: {metrics_data['video_date']}")
    print(f"   📅 Current date (created_on): {metrics_data['current_date']}")
    print(f"   📅 Video date: {metrics_data['video_date']}")
    print(f"   📊 Generic total videos: {metrics_data['total_videos']}")
    print(f"   📊 Generic processed: {metrics_data['videos_processed']}")
    print(f"   📊 Generic errors: {metrics_data['videos_error']}")
    print(f"   📊 Overall created_on processed: {metrics_data['videos_processed_created_on']}")
    print(f"   📊 Overall video_date processed: {metrics_data['videos_processed_video_date']}")
    print(f"   🎯 Linear created_on: {metrics_data['linear_videos_processed_created_on']}")
    print(f"   🎯 Linear video_date: {metrics_data['linear_videos_processed_video_date']}")
    print(f"   🎯 Fixed created_on: {metrics_data['fixed_videos_processed_created_on']}")
    print(f"   🎯 Fixed video_date: {metrics_data['fixed_videos_processed_video_date']}")
    print(f"   🎯 Electrical created_on: {metrics_data['electrical_videos_processed_created_on']}")
    print(f"   🎯 Electrical video_date: {metrics_data['electrical_videos_processed_video_date']}")
    
    try:
        clean_host = central_host.strip()
        if not clean_host.startswith('http'):
            clean_host = f"https://{clean_host}"
        
        print(f"📡 Sending to: {clean_host}/metrics")
        print(f"📦 Payload size: {len(json.dumps(metrics_payload))} bytes")
        
        response = requests.post(
            f"{clean_host}/metrics", 
            json=metrics_payload, 
            timeout=30,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': f'monitoring-client/{hostname}',
                'Accept': 'application/json'
            },
            verify=True
        )
        
        print(f"📡 Response status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"✅ Combined metrics pushed successfully for video_date: {metrics_data['video_date']}")
            return True
        else:
            print(f"❌ Failed to push combined metrics: HTTP {response.status_code}")
            print(f"❌ Response text: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ Timeout error sending combined metrics")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection error sending combined metrics: {e}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error sending combined metrics: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error sending combined metrics: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return False

def collect_and_push_combined_metrics():
    """Collect and push combined metrics - each video_date sends both created_on and video_date metrics"""
    hostname = socket.gethostname()
    central_host = os.getenv('CENTRAL_HOST', 'https://monitoring.takeleap.in').strip()
    
    print(f"🏷️ Hostname: {hostname}")
    public_ip = get_public_ip()
    client_id = f"{hostname}-{public_ip}"
    print(f"🆔 Client ID: {client_id}")
    
    # Collect system metrics once (same for all requests)
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        
        print(f"📊 System metrics - CPU: {cpu_percent}%, Memory: {memory.percent}%, Disk: {disk_percent:.1f}%")
    except Exception as e:
        print(f"❌ Error collecting system metrics: {e}")
        cpu_percent, memory_percent, disk_percent = 0, 0, 0
    else:
        memory_percent = memory.percent
    
    # Get database connection
    db_conn = get_db_connection()
    if not db_conn:
        print("❌ Failed to connect to database - cannot proceed")
        return False
        
    try:
        cursor = db_conn.cursor()
        
        if not test_table_access(cursor):
            print("❌ Cannot access video_uploads table - cannot proceed")
            return False
        
        success_count = 0
        total_requests = 0
        
        # ========== GET VIDEO DATES AND PROCESS EACH ==========
        print(f"\n{'='*60}")
        print("📅 COLLECTING COMBINED METRICS PER VIDEO DATE")
        print(f"{'='*60}")
        
        # Get distinct video dates from files created today
        try:
            cursor.execute("""
                SELECT DISTINCT DATE(STR_TO_DATE(LEFT(file_name, 8), '%Y%m%d')) AS video_dates
                FROM video_uploads
                WHERE DATE(created_on) = CURDATE()
                ORDER BY video_dates
            """)
            video_dates = [row[0] for row in cursor.fetchall()]
            
            print(f"📅 Found {len(video_dates)} distinct video dates to process")
            for vd in video_dates:
                print(f"   📅 Video date: {vd}")
            
        except Exception as e:
            print(f"❌ Error fetching video dates: {e}")
            video_dates = []
        
        if not video_dates:
            current_date = datetime.now().date()
            print("⚠️ No video dates found for today, using current date as fallback")
            video_dates = [current_date]
        
        # Process each video date with COMBINED metrics
        for video_date_index, video_date in enumerate(video_dates):
            print(f"\n{'-'*60}")
            print(f"📅 PROCESSING COMBINED METRICS FOR VIDEO DATE: {video_date} ({video_date_index + 1}/{len(video_dates)})")
            print(f"🔄 This request will include:")
            print(f"   📊 System metrics (CPU, memory, disk, MySQL)")
            print(f"   📊 Generic metrics (no date filters)")
            print(f"   📅 Created_on metrics (current date: {datetime.now().strftime('%Y-%m-%d')})")
            print(f"   📅 Video_date metrics (video date: {video_date})")
            print(f"   🎯 Both overall and asset-specific variations")
            print(f"{'-'*60}")
            
            combined_metrics = get_combined_metrics(cursor, video_date)
            if combined_metrics:
                total_requests += 1
                if send_combined_metrics_to_server(central_host, client_id, hostname, combined_metrics,
                                                cpu_percent, memory_percent, disk_percent):
                    success_count += 1
                    print(f"✅ Combined metrics sent successfully for video_date: {video_date}")
                else:
                    print(f"❌ Failed to send combined metrics for video_date: {video_date}")
            else:
                print(f"❌ Failed to collect combined metrics for video_date: {video_date}")
            
            # Small delay between video dates
            if video_date_index < len(video_dates) - 1:
                print("⏳ Waiting 2 seconds before next video date...")
                time.sleep(2)
        
        # ========== SUMMARY ==========
        print(f"\n{'='*60}")
        print(f"📊 COMBINED METRICS COLLECTION SUMMARY:")
        print(f"   📅 Video dates processed: {len(video_dates)}")
        print(f"   🔄 Each request included:")
        print(f"      📊 System metrics (CPU, memory, disk, MySQL)")
        print(f"      📊 Generic metrics (no date filters)")
        print(f"      📅 Created_on metrics (current date)")
        print(f"      📅 Video_date metrics (specific video date)")
        print(f"      🎯 Overall + Linear + Fixed + Electrical variations")
        print(f"   📊 Total requests sent: {total_requests}")
        print(f"   ✅ Successful: {success_count}")
        print(f"   ❌ Failed: {total_requests - success_count}")
        print(f"   📈 Success rate: {(success_count/total_requests)*100:.1f}%" if total_requests > 0 else "   📈 Success rate: 0%")
        print(f"   🗄️  Database tables updated per request:")
        print(f"      📊 generic_metrics")
        print(f"      📅 created_on_metrics")
        print(f"      📅 video_date_metrics")
        print(f"      📅 linear_created_on_metrics")
        print(f"      📅 linear_video_date_metrics")
        print(f"      📅 fixed_created_on_metrics")
        print(f"      📅 fixed_video_date_metrics")
        print(f"      📅 electrical_created_on_metrics")
        print(f"      📅 electrical_video_date_metrics")
        print(f"   🎯 Total tables updated: {success_count * 9}")
        print(f"{'='*60}")
        
        return success_count > 0
        
    except Exception as e:
        print(f"❌ Error in collect_and_push_combined_metrics: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return False
    finally:
        try:
            if cursor:
                cursor.close()
            if db_conn and db_conn.is_connected():
                db_conn.close()
                print("🔌 Database connection closed")
        except Exception as e:
            print(f"⚠️ Error closing database connection: {e}")

def test_connection_to_server(central_host):
    """Test connection to the central monitoring server"""
    try:
        clean_host = central_host.strip()
        if not clean_host.startswith('http'):
            clean_host = f"https://{clean_host}"
            
        print(f"🔍 Testing connection to: {clean_host}")
        
        response = requests.get(f"{clean_host}/status", timeout=10)
        if response.status_code == 200:
            print(f"✅ Server is reachable: {clean_host}")
            return True
        else:
            print(f"⚠️ Server responded with status {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ Timeout connecting to server: {clean_host}")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to server: {clean_host}")
        return False
    except Exception as e:
        print(f"❌ Error testing server connection: {e}")
        return False

def run_scheduled_combined_metrics():
    """Wrapper function for scheduled execution"""
    print(f"\n{'🔔'*60}")
    print(f"🔔 SCHEDULED COMBINED METRICS COLLECTION STARTED")
    print(f"🔔 Time: {datetime.now()}")
    print(f"🔔 Mode: Each video_date sends BOTH generic + created_on + video_date metrics")
    print(f"{'🔔'*60}")
    
    success = collect_and_push_combined_metrics()
    
    if success:
        print(f"🔔 SCHEDULED COMBINED METRICS COLLECTION COMPLETED SUCCESSFULLY")
    else:
        print(f"🔔 SCHEDULED COMBINED METRICS COLLECTION FAILED")
    
    print(f"{'🔔'*60}\n")

if __name__ == '__main__':
    hostname = socket.gethostname()
    central_host = os.getenv('CENTRAL_HOST', 'https://monitoring.takeleap.in').strip()
    
    print(f"🚀 Starting COMBINED metrics push-based monitoring client")
    print(f"🏷️ Hostname: {hostname}")
    print(f"🌐 Central monitoring server: {central_host}")
    print(f"📅 Current time: {datetime.now()}")
    
    # Test server connectivity first
    if not test_connection_to_server(central_host):
        print("❌ Cannot reach monitoring server. Please check:")
        print("   1. Server URL is correct")
        print("   2. Network connectivity")
        print("   3. Firewall settings")
        print("   4. Server is running")
        print("⏳ Will retry in scheduled runs...")
    
    # Test database connectivity
    print("\n🔍 Testing database connectivity...")
    test_conn = get_db_connection()
    if test_conn:
        print("✅ Database connection test successful")
        test_conn.close()
    else:
        print("❌ Database connection test failed")
        print("💡 Please check:")
        print("   1. Database host: 192.168.2.34")
        print("   2. Database credentials")
        print("   3. Network connectivity to database")
        print("   4. Database is running")
    
    print(f"\n{'='*70}")
    print("⏰ SCHEDULING COMBINED MONITORING")
    print("📅 Schedule:")
    print(" every 4 hrs starting 8 AM")
    print("🔄 COMBINED approach - Each video_date request includes:")
    print("   📊 System metrics (CPU, memory, disk, MySQL)")
    print("   📊 Generic metrics (no date filters - total counts)")
    print("   📅 Created_on metrics (current date)")
    print("   📅 Video_date metrics (specific video date)")
    print("   🎯 Both overall + asset-specific for all metrics")
    print("   🗄️  Updates 9 database tables per request")
    print(f"{'='*70}")
    
    # Schedule the jobs
    schedule.every().day.at("00:05").do(run_scheduled_combined_metrics)  # Midnight
    schedule.every().day.at("04:00").do(run_scheduled_combined_metrics)  # 4 AM 
    schedule.every().day.at("08:00").do(run_scheduled_combined_metrics)  # Morning
    schedule.every().day.at("12:00").do(run_scheduled_combined_metrics)  # Noon
    schedule.every().day.at("16:00").do(run_scheduled_combined_metrics)  # Night (4 pm)
    schedule.every().day.at("20:00").do(run_scheduled_combined_metrics)  # Noon-test (8 pm)
    schedule.every().day.at("23:55").do(run_scheduled_combined_metrics)  # Night (11:55 PM)
    
    # Run once immediately for testing
    print(f"\n{'='*50}")
    print("🧪 RUNNING INITIAL COMBINED TEST COLLECTION")
    print(f"{'='*50}")
    
    initial_success = collect_and_push_combined_metrics()
    if initial_success:
        print("✅ Initial combined test collection successful")
    else:
        print("❌ Initial combined test collection failed")
    
    print(f"\n{'='*50}")
    print("⏰ STARTING SCHEDULED COMBINED MONITORING LOOP")
    print("💤 Waiting for scheduled times...")
    print("🔍 Next scheduled runs:")
    for job in schedule.jobs:
        print(f"   ⏰ {job.next_run}")
    print(f"{'='*50}")
    
    # Main scheduling loop
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds
            
    except KeyboardInterrupt:
        print("\n🛑 Received interrupt signal, shutting down gracefully...")
        print("📊 Final schedule status:")
        for job in schedule.jobs:
            print(f"   ⏰ Job: {job.job_func.__name__} - Next: {job.next_run}")
    except Exception as e:
        print(f"❌ Unexpected error in scheduling loop: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
    
    print("👋 Combined monitoring client shutdown complete")