# Deploying to DigitalOcean

This guide covers two deployment paths:

1. **App Platform** (recommended) — managed PaaS, auto-deploy from GitHub
2. **Droplet + Docker Compose** — self-managed VM for more control

---

## Option 1: App Platform (Recommended)

DigitalOcean App Platform builds and deploys your Docker image automatically on every push to `main`. Managed PostgreSQL and Redis are provisioned alongside the app.

### Prerequisites

- [DigitalOcean account](https://cloud.digitalocean.com/)
- [`doctl` CLI](https://docs.digitalocean.com/reference/doctl/how-to/install/) installed and authenticated
- GitHub repo connected to your DO account

### Quick Deploy

```bash
# 1. Authenticate doctl
doctl auth init

# 2. Create the app from the spec
doctl apps create --spec .do/app.yaml

# 3. Check deployment status
doctl apps list
doctl apps logs <app-id> --type=run
```

That's it — App Platform will:
- Build the Docker image from your `Dockerfile`
- Provision a managed PostgreSQL 16 database
- Provision a managed Redis 7 instance
- Run Alembic migrations as a pre-deploy job
- Start the API with health checks
- Auto-deploy on every push to `main`

### Configuration

After the first deploy, set a real `MASTER_API_KEY`:

```bash
# Generate a secure key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Update the secret in App Platform
doctl apps update <app-id> --spec .do/app.yaml
# Or use the DigitalOcean web console: App → Settings → Environment Variables
```

### Estimated Cost

| Resource | Spec | Monthly Cost |
|---|---|---|
| API service | basic-xxs (1 vCPU, 512 MB) | ~$5 |
| PostgreSQL | db-s-dev-database (1 GB) | ~$7 |
| Redis | db-s-dev-database | ~$10 |
| **Total** | | **~$22/mo** |

Scale up by changing `instance_size_slug` and `instance_count` in `.do/app.yaml`.

### Custom Domain

```bash
# Add a domain in App Platform
doctl apps update <app-id> --spec .do/app.yaml
# Add under services[0].routes or via the web console

# Point your DNS:
#   CNAME  api.yourdomain.com  →  <app-id>.ondigitalocean.app
```

SSL is automatic via Let's Encrypt.

---

## Option 2: Droplet + Docker Compose

For more control (custom networking, SSH access, cron jobs), deploy to a Droplet.

### 1. Create a Droplet

```bash
# Create a Docker-ready droplet ($6/mo — 1 vCPU, 1 GB RAM)
doctl compute droplet create feature-flags \
  --region nyc1 \
  --size s-1vcpu-1gb \
  --image docker-20-04 \
  --ssh-keys $(doctl compute ssh-key list --format ID --no-header | head -1) \
  --wait
```

### 2. SSH In and Clone

```bash
DROPLET_IP=$(doctl compute droplet get feature-flags --format PublicIPv4 --no-header)
ssh root@$DROPLET_IP

# On the droplet:
git clone https://github.com/Jade-sss/feature-flag-service.git
cd feature-flag-service
```

### 3. Configure Environment

```bash
cp .env.example .env
nano .env
```

Set production values:

```env
ENV=production
DATABASE_URL=postgresql+asyncpg://featureflags:STRONG_PASSWORD@postgres:5432/featureflags
REDIS_URL=redis://redis:6379/0
AUTH_ENABLED=true
MASTER_API_KEY=<generate-with-secrets.token_urlsafe(32)>
LOG_FORMAT=json
CORS_ORIGINS=https://yourdomain.com
ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com
```

Update `docker-compose.yml` postgres password to match:

```bash
sed -i 's/POSTGRES_PASSWORD: featureflags/POSTGRES_PASSWORD: STRONG_PASSWORD/' docker-compose.yml
```

### 4. Deploy

```bash
# Start everything
docker compose up -d --build

# Run migrations
docker compose run --rm migrate

# Verify
curl http://localhost:8000/health
```

### 5. Set Up Reverse Proxy (Nginx + SSL)

```bash
apt update && apt install -y nginx certbot python3-certbot-nginx

# Create Nginx config
cat > /etc/nginx/sites-available/feature-flags << 'EOF'
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

ln -s /etc/nginx/sites-available/feature-flags /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Get SSL certificate
certbot --nginx -d api.yourdomain.com
```

### 6. Auto-restart on Reboot

Docker Compose services already have `restart: unless-stopped`. Enable Docker on boot:

```bash
systemctl enable docker
```

### 7. Updates

```bash
cd /root/feature-flag-service
git pull origin main
docker compose up -d --build
docker compose run --rm migrate
```

---

## Post-deploy Checklist

- [ ] Set a strong `MASTER_API_KEY` (never use the default)
- [ ] Create database-backed API keys via `POST /api-keys/` and distribute to clients
- [ ] Restrict `CORS_ORIGINS` to your actual frontend domains
- [ ] Restrict `ALLOWED_HOSTS` to your actual hostname
- [ ] Verify `GET /health` returns `{"status": "ok", "db": "ok", "cache": "ok"}`
- [ ] Verify `GET /metrics` is returning Prometheus data
- [ ] Set up monitoring alerts on the `/health` endpoint
- [ ] Set up log forwarding (App Platform → Papertrail/Datadog, or Droplet → `journald`)
- [ ] Set up automated database backups (App Platform does this automatically)
- [ ] Run a smoke test:

```bash
# Create a flag
curl -s -X POST https://api.yourdomain.com/flags/ \
  -H "X-API-Key: $MASTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key": "test-flag", "is_enabled": true}' | jq

# Evaluate it
curl -s "https://api.yourdomain.com/flags/evaluate?key=test-flag&user_id=user1" \
  -H "X-API-Key: $MASTER_API_KEY" | jq

# Clean up
curl -s -X DELETE https://api.yourdomain.com/flags/test-flag \
  -H "X-API-Key: $MASTER_API_KEY"
```

---

## Scaling Notes

| Scenario | Action |
|---|---|
| More traffic | Increase `instance_count` in `.do/app.yaml` (App Platform) or add workers behind a load balancer (Droplet) |
| More DB connections | Increase `DB_POOL_SIZE` env var; upgrade managed DB plan |
| Redis memory | Upgrade Redis plan or increase `CACHE_FLAG_TTL` / `CACHE_EVAL_TTL` |
| Global latency | Deploy to multiple DO regions with a global load balancer |
