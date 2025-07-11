#!/usr/bin/env python3
import requests
import socket
import json
import time
import os
import psutil
import mysql.connector

def get_public_ip():
    """Get the public IP address"""
    try:
        services = [
            'https://ifconfig.me/ip',
            'https://api.ipify.org',
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
                continue
        
        return get_local_ip()
    except Exception as e:
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

def get_db_metrics():
    """Get MySQL database metrics"""
    try:
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
        
        # Get processed videos count
        try:
            cursor.execute("SELECT COUNT(*) FROM video_uploads WHERE is_processed = 1 AND progress_value = 100")
            videos_processed = cursor.fetchone()[0]
        except mysql.connector.Error:
            try:
                cursor.execute("SELECT COUNT(*) FROM uploads WHERE status = 'completed'")
                videos_processed = cursor.fetchone()[0]
            except mysql.connector.Error:
                videos_processed = 0
        
        # Get error videos count
        try:
            cursor.execute("SELECT COUNT(*) FROM video_uploads WHERE error_message IS NOT NULL")
            videos_error = cursor.fetchone()[0]
        except mysql.connector.Error:
            try:
                cursor.execute("SELECT COUNT(*) FROM uploads WHERE error_message IS NOT NULL")
                videos_error = cursor.fetchone()[0]
            except mysql.connector.Error:
                videos_error = 0
        
        # Get site statistics count
        try:
            cursor.execute("SELECT COUNT(*) FROM video_uploads WHERE site_statics_uploaded = 1")
            site_statics = cursor.fetchone()[0]
        except mysql.connector.Error:
            try:
                cursor.execute("SELECT COUNT(*) FROM uploads WHERE site_statics_uploaded = 1")
                site_statics = cursor.fetchone()[0]
            except mysql.connector.Error:
                site_statics = 0
        
        # Get videos not processed count
        try:
            cursor.execute("SELECT COUNT(*) FROM video_uploads WHERE is_processed = 0 OR progress_value < 100")
            videos_not_processed = cursor.fetchone()[0]
        except mysql.connector.Error:
            try:
                cursor.execute("SELECT COUNT(*) FROM uploads WHERE status != 'completed'")
                videos_not_processed = cursor.fetchone()[0]
            except mysql.connector.Error:
                videos_not_processed = 0
        
        cursor.close()
        conn.close()
        
        return connections, videos_processed, videos_error, site_statics, videos_not_processed
        
    except Exception as e:
        print(f"Database error: {e}")
        return 0, 0, 0, 0, 0

def collect_and_push_metrics(central_host):
    """Collect metrics and push to server"""
    hostname = socket.gethostname()
    client_id = f"{hostname}-{get_public_ip()}"
    
    # Collect system metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    disk_percent = (disk.used / disk.total) * 100
    
    # Database metrics
    db_connections, videos_processed, videos_error, site_statics, videos_not_processed = get_db_metrics()
    
    # Prepare metrics payload
    metrics_data = {
        "client_id": client_id,
        "hostname": hostname,
        "timestamp": int(time.time()),
        "metrics": {
            "cpu_usage": cpu_percent,
            "memory_usage": memory.percent,
            "disk_usage": disk_percent,
            "mysql_connections": db_connections,
            "videos_processed": videos_processed,
            "videos_error": videos_error,
            "site_statics": site_statics,
            "videos_not_processed": videos_not_processed
        }
    }
    
    try:
        # Push metrics to server
        response = requests.post(f"{central_host}/metrics", 
                               json=metrics_data, timeout=10)
        if response.status_code == 200:
            print(f"✅ Metrics pushed: CPU={cpu_percent}%, Memory={memory.percent}%, Disk={disk_percent:.1f}%")
            return True
        else:
            print(f"❌ Failed to push metrics: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error pushing metrics: {e}")
        return False

if __name__ == '__main__':
    hostname = socket.gethostname()
    central_host = os.getenv('CENTRAL_HOST', 'https://monitoring.takeleap.in')
    
    print(f"🚀 Starting push-based client: {hostname}")
    print(f"🌐 Central monitoring: {central_host}")
    
    # Main loop - push metrics every 15 seconds
    while True:
        try:
            collect_and_push_metrics(central_host)
            time.sleep(15)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)