#!/usr/bin/env python3
import requests
import socket
import json
import time
import os
from prometheus_client import start_http_server, Gauge
import psutil
import mysql.connector

# Metrics
CPU_USAGE = Gauge('host_cpu_usage', 'CPU usage %', ['hostname', 'client_id'])
MEMORY_USAGE = Gauge('host_memory_usage', 'Memory usage %', ['hostname', 'client_id'])
DISK_USAGE = Gauge('host_disk_usage', 'Disk usage %', ['hostname', 'client_id'])
DB_CONNECTIONS = Gauge('mysql_active_connections', 'Active MySQL connections', ['hostname', 'client_id'])
VIDEOS_PROCESSED = Gauge('videos_processed_total', 'Total videos processed', ['hostname', 'client_id'])

def get_public_ip():
    """Get the public IP address"""
    try:
        # Try multiple services to get public IP
        services = [
            'https://ifconfig.me/ip',
            'https://api.ipify.org',
            'https://ipecho.net/plain',
            'https://icanhazip.com'
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
        
        # Fallback to local IP if public IP detection fails
        print("⚠️ Could not detect public IP, using local IP")
        return get_local_ip()
    except Exception as e:
        print(f"❌ Error getting public IP: {e}")
        return get_local_ip()

def get_local_ip():
    """Get the local IP address (fallback)"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return socket.gethostbyname(socket.gethostname())

def register_with_central(central_host, max_retries=3):
    """Register this client with central monitoring"""
    hostname = socket.gethostname()
    public_ip = get_public_ip()
    
    # Get port from environment variable
    port = int(os.getenv('METRICS_PORT', 8118))
    
    client_info = {
        "hostname": hostname,
        "ip": public_ip,
        "port": port,
        "metrics_path": "/metrics"
    }
    
    for attempt in range(max_retries):
        try:
            # Use the CENTRAL_HOST environment variable directly
            response = requests.post(f"{central_host}/register", 
                                   json=client_info, timeout=10)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Registration successful: {result.get('message', 'OK')}")
                return True
            else:
                print(f"❌ Registration failed (attempt {attempt + 1}): {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Registration error (attempt {attempt + 1}): {e}")
        
        if attempt < max_retries - 1:
            time.sleep(5)  # Wait before retry
    
    print(f"❌ Failed to register after {max_retries} attempts")
    return False

def collect_metrics():
    """Collect system metrics"""
    hostname = socket.gethostname()
    client_id = f"{hostname}-{get_public_ip()}"
    
    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    CPU_USAGE.labels(hostname, client_id).set(cpu_percent)
    
    # Memory
    memory = psutil.virtual_memory()
    MEMORY_USAGE.labels(hostname, client_id).set(memory.percent)
    
    # Disk
    disk = psutil.disk_usage('/')
    disk_percent = (disk.used / disk.total) * 100
    DISK_USAGE.labels(hostname, client_id).set(disk_percent)
    
    # Database metrics
    db_connections, videos_processed = get_db_metrics()
    DB_CONNECTIONS.labels(hostname, client_id).set(db_connections)
    VIDEOS_PROCESSED.labels(hostname, client_id).set(videos_processed)
    
    print(f"Metrics: CPU={cpu_percent}%, Memory={memory.percent}%, Disk={disk_percent:.1f}%, DB_Conn={db_connections}, Videos={videos_processed}")

def get_db_metrics():
    """Get MySQL database metrics"""
    try:
        # Database connection parameters from environment
        db_host = os.getenv('DB_HOST', 'localhost')
        db_user = os.getenv('DB_USER', 'root')
        db_password = os.getenv('DB_PASSWORD', 'password')
        db_name = os.getenv('DB_NAME', 'take_leap')
        db_port = int(os.getenv('DB_PORT', '3306'))
        
        conn = mysql.connector.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            port=db_port,
            connect_timeout=5
        )
        cursor = conn.cursor()
        
        # Get active connections
        cursor.execute("SHOW STATUS LIKE 'Threads_connected'")
        connections = int(cursor.fetchone()[1])
        
        # Get processed videos count - try multiple table names
        try:
            cursor.execute("SELECT COUNT(*) FROM video_uploads WHERE is_processed = 1 AND progress_value = 100")
            videos_processed = cursor.fetchone()[0]
        except mysql.connector.Error:
            # Fallback to different table structure
            try:
                cursor.execute("SELECT COUNT(*) FROM uploads WHERE status = 'completed'")
                videos_processed = cursor.fetchone()[0]
            except mysql.connector.Error:
                videos_processed = 0
        
        cursor.close()
        conn.close()
        
        return connections, videos_processed
        
    except Exception as e:
        print(f"Database error: {e}")
        return 0, 0

if __name__ == '__main__':
    hostname = socket.gethostname()
    central_host = os.getenv('CENTRAL_HOST', 'https://monitoring.takeleap.in')
    metrics_port = int(os.getenv('METRICS_PORT', 8118))
    
    print(f"🚀 Starting client exporter: {hostname}")
    print(f"🌐 Central monitoring: {central_host}")
    print(f"📊 Metrics port: {metrics_port}")
    print(f"🔍 Detecting public IP for registration...")
    
    # Start metrics server on all interfaces (0.0.0.0) so it's accessible from outside container
    print(f"🚀 Starting metrics server on port {metrics_port}...")
    start_http_server(metrics_port, addr='0.0.0.0')
    print(f"✅ Metrics server started on port {metrics_port} (accessible from outside container)")
    
    # Register with central (with retry)
    registration_success = register_with_central(central_host)
    
    # Re-register periodically in case server restarts
    last_registration = time.time()
    registration_interval = 300  # 5 minutes
    
    # Collect metrics loop
    while True:
        try:
            collect_metrics()
            
            # Re-register periodically
            if time.time() - last_registration > registration_interval:
                if register_with_central(central_host):
                    last_registration = time.time()
            
            time.sleep(15)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)