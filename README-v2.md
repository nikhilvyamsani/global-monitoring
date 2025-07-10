# Centralized Monitoring System v2 - Push-Based Architecture

A Docker-based centralized monitoring solution using **push-based metrics collection** for global deployment without firewall/NAT issues.

## 🚀 What's New in v2

- **Push-Based Architecture**: Clients push metrics to server (no inbound ports needed)
- **Global Deployment Ready**: Works behind NAT/CGNAT/firewalls
- **HTTPS Communication**: Secure metrics transmission
- **Auto-Cleanup**: Automatic stale data removal
- **Simplified Networking**: No port forwarding required

## 📋 Architecture v2

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client 1      │    │   Client 2      │    │   Client N      │
│  (Any Server)   │    │  (Any Server)   │    │  (Any Server)   │
│                 │    │                 │    │                 │
│  Push Metrics   │    │  Push Metrics   │    │  Push Metrics   │
│     HTTPS       │    │     HTTPS       │    │     HTTPS       │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │   Monitoring Server       │
                    │  ┌─────────────────────┐  │
                    │  │    Prometheus       │  │
                    │  │    (Port 9090)      │  │
                    │  └─────────────────────┘  │
                    │  ┌─────────────────────┐  │
                    │  │     Grafana         │  │
                    │  │    (Port 3000)      │  │
                    │  └─────────────────────┘  │
                    │  ┌─────────────────────┐  │
                    │  │ Metrics Receiver    │  │
                    │  │    (Port 5001)      │  │
                    │  └─────────────────────┘  │
                    └───────────────────────────┘
```

## 🛠️ Quick Start

### Server Deployment (Portainer/Docker Compose)

```yaml
version: '3.8'

services:
  monitoring-server:
    image: nikhilvyamsani/server:latest
    container_name: monitoring-server
    restart: unless-stopped
    ports:
      - "0.0.0.0:9090:9090"  # Prometheus
      - "0.0.0.0:3000:3000"  # Grafana
      - "0.0.0.0:5001:5001"  # Metrics Receiver
    volumes:
      - prometheus-data:/app/prometheus-data
      - grafana-data:/app/grafana-data

volumes:
  prometheus-data:
  grafana-data:
```

### Client Deployment (Any Server Worldwide)

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Deploy monitoring client
docker run -d \
  --name monitoring-client \
  --network host \
  --restart unless-stopped \
  -e CENTRAL_HOST=https://monitoring.yourdomain.com \
  -e DB_HOST=localhost \
  -e DB_USER=your_db_user \
  -e DB_PASSWORD=your_db_password \
  -e DB_NAME=your_db_name \
  -e DB_PORT=3306 \
  nikhilvyamsani/client:latest
```

## 🌐 Key Advantages

### v1 vs v2 Comparison

| Feature | v1 (Pull-Based) | v2 (Push-Based) |
|---------|----------------|-----------------|
| **Network Requirements** | Inbound ports open | Only outbound HTTPS |
| **Firewall Issues** | ❌ Requires configuration | ✅ No issues |
| **NAT/CGNAT Support** | ❌ Limited | ✅ Full support |
| **Global Deployment** | ❌ Complex | ✅ Simple |
| **Port Forwarding** | ❌ Required | ✅ Not needed |
| **Security** | HTTP endpoints | ✅ HTTPS only |

## 📊 Access Points

- **Grafana Dashboard**: `https://grafana.yourdomain.com` (admin/admin)
- **Prometheus**: `https://prometheus.yourdomain.com`
- **Metrics API**: `https://monitoring.yourdomain.com/metrics`
- **Status API**: `https://monitoring.yourdomain.com/status`

## 🔧 Environment Variables

### Client Configuration

| Variable       | Description                   | Default   | Required |
| -------------- | ----------------------------- | --------- | -------- |
| `CENTRAL_HOST` | Monitoring server URL         | -         | ✅       |
| `DB_HOST`      | MySQL database host           | localhost | ❌       |
| `DB_USER`      | Database username             | root      | ❌       |
| `DB_PASSWORD`  | Database password             | password  | ❌       |
| `DB_NAME`      | Database name                 | take_leap | ❌       |
| `DB_PORT`      | Database port                 | 3306      | ❌       |

## 📈 Metrics Collected

- `host_cpu_usage` - CPU usage percentage
- `host_memory_usage` - Memory usage percentage  
- `host_disk_usage` - Disk usage percentage
- `mysql_active_connections` - Active MySQL connections
- `videos_processed_total` - Total videos processed

## 🔄 How Push-Based Works

1. **Client** collects system metrics every 15 seconds
2. **Client** pushes metrics via HTTPS POST to server
3. **Server** stores metrics in memory (60-second retention)
4. **Prometheus** scrapes stored metrics from server
5. **Grafana** displays real-time dashboards

## 🏗️ Building Images

```bash
# Build and push both client and server
./build-and-push.sh
```

## 📁 Project Structure

```
centralized-monitoring/
├── client-docker/
│   ├── Dockerfile
│   ├── auto-discovery-client.py  # v1 pull-based (legacy)
│   ├── push-client.py           # v2 push-based (default)
│   ├── requirements.txt
│   └── .env
├── server-docker/
│   ├── Dockerfile
│   ├── registration-server.py    # Enhanced with push endpoints
│   ├── central-prometheus.yml    # Updated for push-based
│   ├── dashboard.json
│   ├── start.sh
│   └── requirements.txt
├── docker-compose.yml
├── build-and-push.sh
├── README.md                     # v1 documentation
└── README-v2.md                  # v2 documentation (this file)
```

## 🔍 Monitoring & Troubleshooting

### Check Client Status

```bash
# Check if client is pushing metrics
docker logs monitoring-client

# Verify server is receiving metrics
curl https://monitoring.yourdomain.com/status

# View current metrics
curl https://monitoring.yourdomain.com/metrics
```

### Common Issues

1. **Client not pushing**: Check CENTRAL_HOST URL and network connectivity
2. **Metrics not appearing**: Verify server is running and accessible
3. **Stale data**: Metrics older than 60 seconds are automatically cleaned up

## 🚀 Deployment Examples

### Single Client
```bash
docker run -d --name monitoring-client --network host \
  -e CENTRAL_HOST=https://monitoring.takeleap.in \
  nikhilvyamsani/client:latest
```

### Multiple Clients (Different Servers)
```bash
# Server 1
docker run -d --name monitoring-client \
  -e CENTRAL_HOST=https://monitoring.takeleap.in \
  -e DB_HOST=10.0.1.100 \
  nikhilvyamsani/client:latest

# Server 2  
docker run -d --name monitoring-client \
  -e CENTRAL_HOST=https://monitoring.takeleap.in \
  -e DB_HOST=10.0.2.100 \
  nikhilvyamsani/client:latest
```

## 📄 Migration from v1

1. **Update server**: Deploy new server image with push endpoints
2. **Update clients**: Deploy new client image with push-based architecture
3. **Update Prometheus config**: Point to server's `/metrics` endpoint
4. **No data loss**: Existing Prometheus data remains intact

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Test with both client and server
4. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Support

For issues and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review container logs

---

**v2.0.0** - Push-based architecture for global monitoring without network complexity