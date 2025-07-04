# Centralized Monitoring System

A Docker-based centralized monitoring solution using Prometheus, Grafana, and auto-registering clients.

## 🚀 Features

- **Auto-Registration**: Clients automatically register with the monitoring server
- **Multi-Architecture**: Supports AMD64, ARM64, and ARMv7
- **Custom Metrics**: CPU, Memory, Disk, MySQL connections, and application metrics
- **Global Access**: Reverse proxy ready for worldwide deployment
- **Persistent Data**: Volumes for data persistence across container restarts

## 📋 Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client 1      │    │   Client 2      │    │   Client N      │
│  (Any Server)   │    │  (Any Server)   │    │  (Any Server)   │
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
                    │  │ Registration API    │  │
                    │  │    (Port 5001)      │  │
                    │  └─────────────────────┘  │
                    └───────────────────────────┘
```

## 🛠️ Quick Start

### Server Deployment

1. **Using Docker Compose (Recommended):**

```bash
git clone https://github.com/yourusername/centralized-monitoring.git
cd centralized-monitoring
docker-compose up -d
```

2. **Using Portainer:**

- Copy `docker-compose.yml` content
- Create new stack in Portainer
- Deploy

### Client Deployment

**On any server you want to monitor:**

```bash
docker run -d \
  --name monitoring-client \
  --network host \
  -e CENTRAL_HOST=your-server-ip \
  -e DB_HOST=localhost \
  -e DB_USER=root \
  -e DB_PASSWORD=your_password \
  -e DB_NAME=your_database \
  nikhilvyamsani/client:latest
```

## 🌐 Global Deployment with Reverse Proxy

### Nginx Configuration

```nginx
# Grafana Dashboard
server {
    listen 80;
    server_name grafana.yourdomain.com;
    location / {
        proxy_pass http://your-server-ip:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Prometheus Metrics
server {
    listen 80;
    server_name prometheus.yourdomain.com;
    location / {
        proxy_pass http://your-server-ip:9090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Client Registration
server {
    listen 80;
    server_name monitoring.yourdomain.com;
    location / {
        proxy_pass http://your-server-ip:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Global Client Registration

```bash
docker run -d \
  --name monitoring-client \
  --network host \
  -e CENTRAL_HOST=monitoring.yourdomain.com \
  nikhilvyamsani/client:latest
```

## 📊 Access Points

- **Grafana Dashboard**: `http://your-server:3000` (admin/admin)
- **Prometheus**: `http://your-server:9090`
- **Registration API**: `http://your-server:5001`

## 🔧 Environment Variables

### Client Configuration

| Variable       | Description                   | Default   |
| -------------- | ----------------------------- | --------- |
| `CENTRAL_HOST` | Monitoring server hostname/IP | Required  |
| `DB_HOST`      | MySQL database host           | localhost |
| `DB_USER`      | Database username             | root      |
| `DB_PASSWORD`  | Database password             | password  |
| `DB_NAME`      | Database name                 | take_leap |
| `DB_PORT`      | Database port                 | 3306      |

## 📈 Custom Metrics

The client exports these custom metrics:

- `host_cpu_usage` - CPU usage percentage
- `host_memory_usage` - Memory usage percentage
- `host_disk_usage` - Disk usage percentage
- `mysql_active_connections` - Active MySQL connections
- `videos_processed_total` - Total videos processed

## 🏗️ Building Images

### Multi-Architecture Build

```bash
# Client
cd client-docker
docker buildx build --platform linux/amd64,linux/arm64,linux/arm/v7 --tag nikhilvyamsani/client:latest --push .

# Server
cd server-docker
docker buildx build --platform linux/amd64,linux/arm64,linux/arm/v7 --tag nikhilvyamsani/server:latest --push .
```

## 📁 Project Structure

```
centralized-monitoring/
├── client-docker/
│   ├── Dockerfile
│   ├── auto-discovery-client.py
│   ├── requirements.txt
│   └── .env
├── server-docker/
│   ├── Dockerfile
│   ├── registration-server.py
│   ├── central-prometheus.yml
│   ├── dashboard.json
│   ├── start.sh
│   └── requirements.txt
├── docker-compose.yml
└── README.md
```

## 🔍 Monitoring & Troubleshooting

### Check Client Registration

```bash
curl http://your-server:5001/clients
```

### Check Prometheus Targets

```bash
curl http://your-server:9090/api/v1/targets
```

### View Container Logs

```bash
docker logs monitoring-server
docker logs monitoring-client
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Support

For issues and questions:

- Create an issue on GitHub
- Check the troubleshooting section
- Review container logs
