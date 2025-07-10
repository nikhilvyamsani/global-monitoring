#!/usr/bin/env python3
import socket
import requests
import subprocess
import sys

def get_public_ip():
    """Get public IP address"""
    try:
        response = requests.get('https://ifconfig.me/ip', timeout=10)
        return response.text.strip()
    except:
        return None

def check_port_internal(port):
    """Check if port is listening internally"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        return result == 0
    except:
        return False

def check_port_external(ip, port):
    """Check if port is accessible externally"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except:
        return False

def scan_common_ports():
    """Scan common ports for public accessibility"""
    common_ports = [22, 80, 443, 3000, 5000, 8000, 8080, 8118, 9000]
    public_ip = get_public_ip()
    
    if not public_ip:
        print("❌ Could not detect public IP")
        return
    
    print(f"🌐 Public IP: {public_ip}")
    print(f"🔍 Scanning common ports...\n")
    
    print("Port\tInternal\tExternal\tStatus")
    print("-" * 40)
    
    for port in common_ports:
        internal = check_port_internal(port)
        external = check_port_external(public_ip, port) if internal else False
        
        internal_status = "✅ OPEN" if internal else "❌ CLOSED"
        external_status = "✅ PUBLIC" if external else "❌ BLOCKED"
        
        if internal and external:
            status = "🌐 ACCESSIBLE"
        elif internal and not external:
            status = "🔒 FIREWALLED"
        else:
            status = "⭕ NOT RUNNING"
        
        print(f"{port}\t{internal_status}\t{external_status}\t{status}")

def check_specific_port(port):
    """Check specific port accessibility"""
    public_ip = get_public_ip()
    
    if not public_ip:
        print("❌ Could not detect public IP")
        return
    
    print(f"🌐 Public IP: {public_ip}")
    print(f"🔍 Checking port {port}...\n")
    
    internal = check_port_internal(port)
    external = check_port_external(public_ip, port) if internal else False
    
    print(f"Internal listening: {'✅ YES' if internal else '❌ NO'}")
    print(f"External accessible: {'✅ YES' if external else '❌ NO'}")
    
    if internal and external:
        print(f"🎉 Port {port} is publicly accessible!")
        print(f"🔗 Test URL: http://{public_ip}:{port}")
    elif internal and not external:
        print(f"🔒 Port {port} is blocked by firewall/router")
        print(f"💡 Open firewall: sudo ufw allow {port}")
    else:
        print(f"⭕ No service running on port {port}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
            check_specific_port(port)
        except ValueError:
            print("❌ Invalid port number")
    else:
        scan_common_ports()