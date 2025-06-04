# Deployment Guide for O2FileSearchPlus Enhanced

This guide covers various deployment scenarios for O2FileSearchPlus Enhanced, from development to production environments.

## 🚀 Quick Deployment

### Local Development
```bash
# Clone and setup
git clone https://github.com/yourusername/O2FileSearchPlus.git
cd O2FileSearchPlus
chmod +x setup.sh
./setup.sh

# Start services
./start_all.sh
```

Access the application at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## 🏭 Production Deployment

### Option 1: Systemd Services (Recommended)

#### Backend Service
1. **Copy service file**:
   ```bash
   sudo cp o2filesearch.service /etc/systemd/system/
   sudo systemctl daemon-reload
   ```

2. **Enable and start service**:
   ```bash
   sudo systemctl enable o2filesearch
   sudo systemctl start o2filesearch
   ```

3. **Check status**:
   ```bash
   sudo systemctl status o2filesearch
   ```

#### Frontend Service
1. **Build production frontend**:
   ```bash
   cd frontend
   npm run build
   ```

2. **Create frontend service**:
   ```bash
   sudo nano /etc/systemd/system/o2filesearch-frontend.service
   ```

   ```ini
   [Unit]
   Description=O2FileSearchPlus Frontend
   After=network.target

   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/path/to/O2FileSearchPlus/frontend
   ExecStart=/usr/bin/npm start
   Restart=always
   RestartSec=10
   Environment=NODE_ENV=production
   Environment=PORT=3000

   [Install]
   WantedBy=multi-user.target
   ```

3. **Enable and start**:
   ```bash
   sudo systemctl enable o2filesearch-frontend
   sudo systemctl start o2filesearch-frontend
   ```

### Option 2: Docker Deployment

#### Backend Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000

CMD ["python", "main.py"]
```

#### Frontend Dockerfile
```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci --only=production

COPY frontend/ .
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
```

#### Docker Compose
```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - /home:/mnt/home:ro
    environment:
      - DATABASE_PATH=/app/data/o2filesearch.db
    restart: unless-stopped

  frontend:
    build:
      context: .
      dockerfile: frontend/Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  data:
```

### Option 3: Reverse Proxy with Nginx

#### Nginx Configuration
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API Documentation
    location /docs {
        proxy_pass http://localhost:8000/docs;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Option 4: Launchd on macOS

For macOS environments, you can run the backend (and optional frontend) using Launchd. Complete the [macOS setup](README.md#macos-setup) first.

#### Backend Plist
1. **Create the plist** (e.g., `~/Library/LaunchAgents/com.o2filesearch.backend.plist`):
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key><string>com.o2filesearch.backend</string>
       <key>WorkingDirectory</key><string>/path/to/O2FileSearchPlus/backend</string>
       <key>ProgramArguments</key>
       <array>
           <string>/usr/local/bin/python3</string>
           <string>main.py</string>
       </array>
       <key>RunAtLoad</key><true/>
       <key>StandardOutPath</key><string>/tmp/o2_backend.log</string>
       <key>StandardErrorPath</key><string>/tmp/o2_backend.err</string>
   </dict>
   </plist>
   ```

2. **Load and unload**:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.o2filesearch.backend.plist
   launchctl unload ~/Library/LaunchAgents/com.o2filesearch.backend.plist
   ```

#### Frontend Plist (Optional)
Create a similar plist that runs `npm start` in the `frontend` directory if you want the frontend managed by Launchd as well.

## 🔧 Configuration

### Environment Variables

#### Backend (.env)
```bash
# Database
DATABASE_PATH=./o2filesearch.db
LOG_LEVEL=INFO
LOG_FILE=./o2filesearch.log

# Server
HOST=0.0.0.0
PORT=8000
WORKERS=1

# Indexing
MAX_FILE_SIZE=10485760  # 10MB
EXCLUDED_DIRS=node_modules,venv,.git,__pycache__
```

#### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=O2FileSearchPlus Enhanced
```

### Production Optimizations

#### Backend Optimizations
1. **Use production ASGI server**:
   ```bash
   pip install gunicorn
   gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

2. **Database optimizations**:
   ```python
   # In main.py
   PRAGMA journal_mode=WAL;
   PRAGMA synchronous=NORMAL;
   PRAGMA cache_size=10000;
   PRAGMA temp_store=memory;
   ```

#### Frontend Optimizations
1. **Build optimization**:
   ```bash
   npm run build
   npm run export  # For static deployment
   ```

2. **CDN Integration**: Configure for static assets

## 🔒 Security Considerations

### SSL/TLS Setup
```bash
# Using Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### Firewall Configuration
```bash
# UFW setup
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### File Permissions
```bash
# Set proper permissions
sudo chown -R www-data:www-data /path/to/O2FileSearchPlus
sudo chmod -R 755 /path/to/O2FileSearchPlus
sudo chmod 600 /path/to/O2FileSearchPlus/backend/o2filesearch.db
```

## 📊 Monitoring

### Log Management
```bash
# Rotate logs
sudo nano /etc/logrotate.d/o2filesearch
```

```
/path/to/O2FileSearchPlus/backend/o2filesearch.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 www-data www-data
    postrotate
        systemctl reload o2filesearch
    endscript
}
```

### Health Checks
```bash
# Backend health check
curl http://localhost:8000/api/status

# Frontend health check
curl http://localhost:3000
```

### Performance Monitoring
```bash
# System resources
htop
iotop
df -h

# Service status
systemctl status o2filesearch
systemctl status o2filesearch-frontend
```

## 🚨 Troubleshooting

### Common Issues

#### Backend Issues
1. **Database locked**:
   ```bash
   sudo systemctl stop o2filesearch
   rm /path/to/o2filesearch.db-wal
   rm /path/to/o2filesearch.db-shm
   sudo systemctl start o2filesearch
   ```

2. **Permission errors**:
   ```bash
   sudo chown -R www-data:www-data /path/to/O2FileSearchPlus
   ```

3. **Port conflicts**:
   ```bash
   sudo netstat -tulpn | grep :8000
   sudo systemctl stop conflicting-service
   ```

#### Frontend Issues
1. **Build failures**:
   ```bash
   cd frontend
   rm -rf node_modules package-lock.json
   npm install
   npm run build
   ```

2. **API connection issues**:
   - Check NEXT_PUBLIC_API_URL environment variable
   - Verify backend is running and accessible
   - Check firewall rules

### Log Analysis
```bash
# Backend logs
tail -f /path/to/O2FileSearchPlus/backend/o2filesearch.log

# System logs
sudo journalctl -u o2filesearch -f
sudo journalctl -u o2filesearch-frontend -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## 📈 Scaling

### Horizontal Scaling
1. **Load balancer setup** with multiple backend instances
2. **Database replication** for read-heavy workloads
3. **CDN integration** for static assets

### Vertical Scaling
1. **Increase worker processes** for backend
2. **Optimize database** with proper indexing
3. **Memory optimization** for large file sets

## 🔄 Updates and Maintenance

### Update Process
```bash
# Backup database
cp /path/to/o2filesearch.db /path/to/backup/

# Pull updates
git pull origin main

# Update dependencies
cd backend && pip install -r requirements.txt
cd frontend && npm install

# Restart services
sudo systemctl restart o2filesearch
sudo systemctl restart o2filesearch-frontend
```

### Backup Strategy
```bash
# Automated backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
cp /path/to/o2filesearch.db /backup/o2filesearch_$DATE.db
find /backup -name "o2filesearch_*.db" -mtime +30 -delete
```

This deployment guide provides comprehensive coverage for various deployment scenarios. Choose the option that best fits your infrastructure and requirements.
