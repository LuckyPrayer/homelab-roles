# Harbor Container Registry - README

## Quick Start

Harbor is now configured and ready to deploy to your homelab as a private container registry!

### One-Command Deployment

```bash
# Set your Infisical credentials
export INFISICAL_TOKEN="your-service-token"
export INFISICAL_PROJECT_ID="your-project-id"

# Run the deployment script
cd scripts
./deploy-harbor.sh
```

The script will:
1. ✅ Check prerequisites
2. ✅ Create/verify Infisical secrets
3. ✅ Deploy Harbor to orion-dev
4. ✅ Update Traefik proxy on hermes-dev
5. ✅ Update DNS records

## What You Get

🐳 **Private Docker Registry**
- Store unlimited container images
- No rate limits or external dependencies
- Full control over image lifecycle

🛡️ **Vulnerability Scanning**
- Automatic Trivy scanning
- CVE detection for all images
- Security policy enforcement

🔒 **Access Control**
- Role-based access control (RBAC)
- Project-level permissions
- User and robot accounts

📊 **Web UI**
- Modern management interface
- Image browsing and search
- Vulnerability reports
- User administration

📦 **Helm Chart Repository**
- Store Helm charts alongside images
- Full Helm repository support

🔗 **REST API**
- Complete automation support
- CI/CD integration ready
- Swagger documentation

## Access Information

After deployment:

- **URL**: https://harbor.dev.thebozic.com
- **Username**: `admin`
- **Password**: Check `~/harbor-admin-password.txt` or Infisical

## Manual Deployment Steps

If you prefer manual deployment:

### 1. Create Secrets

```bash
# Generate and store secrets in Infisical
infisical secrets set HARBOR_ADMIN_PASSWORD="$(openssl rand -base64 32)" \
  --path=/infrastructure/harbor --env=dev

infisical secrets set HARBOR_DB_PASSWORD="$(openssl rand -base64 32)" \
  --path=/infrastructure/harbor --env=dev

infisical secrets set HARBOR_SECRET_KEY="$(openssl rand -hex 8)" \
  --path=/infrastructure/harbor --env=dev
```

### 2. Deploy Harbor

```bash
ansible-playbook -i inventories/dev/hosts.yml \
  playbooks/deploy-harbor.yml \
  --limit orion-dev
```

### 3. Update Traefik Proxy

```bash
ansible-playbook -i inventories/dev/hosts.yml \
  playbooks/provision-routers.yml \
  --limit hermes-dev \
  --tags proxy
```

### 4. Update DNS

```bash
ansible-playbook -i inventories/dev/hosts.yml \
  playbooks/provision-routers.yml \
  --limit hermes-dev \
  --tags dns
```

## Using Harbor

### Docker Login

```bash
docker login harbor.dev.thebozic.com
Username: admin
Password: <your-password>
```

### Push Images

```bash
# Tag image
docker tag nginx:latest harbor.dev.thebozic.com/homelab/nginx:latest

# Push to Harbor
docker push harbor.dev.thebozic.com/homelab/nginx:latest
```

### Pull Images

```bash
docker pull harbor.dev.thebozic.com/homelab/nginx:latest
```

### Use in Docker Compose

```yaml
version: '3.9'
services:
  web:
    image: harbor.dev.thebozic.com/homelab/nginx:latest
    # ...
```

## Documentation

📚 **Comprehensive Guides Available**:

1. **[HARBOR_DEPLOYMENT_GUIDE.md](../docs/HARBOR_DEPLOYMENT_GUIDE.md)**
   - Complete deployment instructions
   - Post-deployment configuration
   - CI/CD integration examples
   - Operations and maintenance
   - Troubleshooting guide
   - Security best practices

2. **[HARBOR_QUICK_REF.md](../docs/HARBOR_QUICK_REF.md)**
   - Common commands
   - API examples
   - Quick troubleshooting
   - Configuration locations

3. **[HARBOR_IMPLEMENTATION_SUMMARY.md](../docs/HARBOR_IMPLEMENTATION_SUMMARY.md)**
   - What was implemented
   - Architecture overview
   - File structure
   - Integration details

4. **[Role README](../playbooks/roles/harbor/README.md)**
   - Ansible role documentation
   - Variable reference
   - Usage examples

## Architecture

```
Internet/LAN
     ↓
[hermes-dev] 192.168.2.10
Traefik Proxy + HTTPS
     ↓
harbor.dev.thebozic.com
     ↓
VLAN Bridge
     ↓
[orion-dev] 192.168.20.100
     ↓
Harbor Stack (9 containers)
├── PostgreSQL Database
├── Redis Cache
├── Docker Registry
├── Web UI (Portal)
├── Core API
├── Job Service
├── Registry Controller
├── Trivy Scanner
└── Nginx (internal)
```

## Features

### Security
- ✅ HTTPS via Traefik with Let's Encrypt
- ✅ Secrets managed by Infisical
- ✅ VLAN network isolation
- ✅ RBAC for access control
- ✅ Vulnerability scanning with Trivy
- ✅ Audit logging

### Storage
- ✅ Filesystem storage (local disk)
- ✅ PostgreSQL database
- ✅ Redis caching
- 📦 S3/MinIO support (optional)

### Management
- ✅ Web UI for administration
- ✅ REST API for automation
- ✅ User and project management
- ✅ Robot accounts for CI/CD
- ✅ Webhook notifications

### Integration
- ✅ Docker and docker-compose
- ✅ Helm chart repository
- ✅ GitHub Actions
- ✅ CI/CD pipelines

## Configuration

### Inventory Files

**Docker Host** - `inventories/dev/hosts.yml`:
```yaml
docker_hosts:
  hosts:
    orion-dev:
      # Harbor runs here on port 8082
```

**Traefik Backend** - `inventories/dev/hosts.yml`:
```yaml
traefik_proxy_backends:
  - name: "harbor"
    host: "harbor.dev.thebozic.com"
    backend_url: "http://192.168.20.100:8082"
    health_check_path: "/api/v2.0/systeminfo"
```

**DNS Record** - `inventories/dev/group_vars/all.yml`:
```yaml
dns_records:
  - hostname: "harbor.dev.thebozic.com"
    ip: "192.168.2.10"
    description: "Harbor container registry"
```

### Role Variables

Located in `playbooks/roles/harbor/defaults/main.yml`:

```yaml
harbor_version: "v2.11.1"
harbor_base_dir: "/opt/harbor"
harbor_http_port: 8082
harbor_hostname: "harbor.{{ env }}.{{ base_domain }}"
harbor_trivy_enabled: true
harbor_log_level: "info"
# ... many more configurable options
```

## Resource Requirements

**Minimum**:
- 2 CPU cores
- 4 GB RAM
- 50 GB disk

**Recommended**:
- 4+ CPU cores
- 8+ GB RAM
- 100+ GB disk

**Current Setup (orion-dev)**:
- ✅ 2 CPU cores
- ✅ 6 GB RAM
- ⚠️ 40 GB disk (may need expansion)

## Common Commands

### Check Status

```bash
# Health check
curl https://harbor.dev.thebozic.com/api/v2.0/health

# System info
curl https://harbor.dev.thebozic.com/api/v2.0/systeminfo

# View logs
ssh root@192.168.20.100 'cd /opt/harbor && docker-compose logs -f'
```

### Management

```bash
# Restart Harbor
ssh root@192.168.20.100 'cd /opt/harbor && docker-compose restart'

# Stop Harbor
ssh root@192.168.20.100 'cd /opt/harbor && docker-compose down'

# Start Harbor
ssh root@192.168.20.100 'cd /opt/harbor && docker-compose up -d'

# Check containers
ssh root@192.168.20.100 'docker ps | grep harbor'
```

### Secrets

```bash
# Get admin password
infisical secrets get HARBOR_ADMIN_PASSWORD \
  --path=/infrastructure/harbor --env=dev --plain

# List all Harbor secrets
infisical secrets list \
  --path=/infrastructure/harbor --env=dev
```

## Troubleshooting

### Cannot Access Harbor

```bash
# Check Harbor is running
ssh root@192.168.20.100 'docker ps | grep harbor'

# Check Traefik proxy
ssh root@192.168.2.10 'docker logs traefik-proxy | grep harbor'

# Verify DNS
nslookup harbor.dev.thebozic.com
# Should return: 192.168.2.10
```

### Cannot Login

```bash
# Get correct password
infisical secrets get HARBOR_ADMIN_PASSWORD \
  --path=/infrastructure/harbor --env=dev --plain

# Check Harbor logs
ssh root@192.168.20.100 'docker logs harbor-core | tail -50'
```

### Harbor Not Starting

```bash
# Check container status
ssh root@192.168.20.100 'cd /opt/harbor && docker-compose ps'

# View all logs
ssh root@192.168.20.100 'cd /opt/harbor && docker-compose logs'

# Check disk space
ssh root@192.168.20.100 'df -h /opt/harbor'
```

## Backup & Recovery

### Backup

```bash
# Database backup
ssh root@192.168.20.100 \
  'docker exec harbor-db pg_dump -U harbor registry > /opt/backup/harbor-db-$(date +%Y%m%d).sql'

# Full backup (stop Harbor first)
ssh root@192.168.20.100 'cd /opt/harbor && docker-compose down'
ssh root@192.168.20.100 \
  'tar czf /opt/backup/harbor-backup-$(date +%Y%m%d).tar.gz /opt/harbor/data /opt/harbor/docker-compose.yml /opt/harbor/.env'
ssh root@192.168.20.100 'cd /opt/harbor && docker-compose up -d'
```

### Restore

```bash
# Stop Harbor
ssh root@192.168.20.100 'cd /opt/harbor && docker-compose down'

# Restore from backup
ssh root@192.168.20.100 'tar xzf /opt/backup/harbor-backup-YYYYMMDD.tar.gz -C /'

# Start Harbor
ssh root@192.168.20.100 'cd /opt/harbor && docker-compose up -d'
```

## Maintenance

### Garbage Collection

Removes unused image layers. Runs automatically daily at midnight.

**Manual GC**:
```bash
# Via API
curl -X POST -u admin:password \
  https://harbor.dev.thebozic.com/api/v2.0/system/gc/schedule

# Or via UI: Administration → Garbage Collection → GC Now
```

### Upgrade Harbor

```bash
# Update version in playbooks/roles/harbor/defaults/main.yml
harbor_version: "v2.12.0"

# Re-run deployment
ansible-playbook -i inventories/dev/hosts.yml \
  playbooks/deploy-harbor.yml \
  --limit orion-dev
```

## Integration Examples

### GitHub Actions

```yaml
- name: Login to Harbor
  uses: docker/login-action@v2
  with:
    registry: harbor.dev.thebozic.com
    username: ${{ secrets.HARBOR_USERNAME }}
    password: ${{ secrets.HARBOR_PASSWORD }}

- name: Build and push
  uses: docker/build-push-action@v4
  with:
    push: true
    tags: harbor.dev.thebozic.com/homelab/myapp:${{ github.sha }}
```

### Helm Charts

```bash
# Add Harbor as Helm repo
helm repo add homelab https://harbor.dev.thebozic.com/chartrepo/homelab \
  --username admin --password <password>

# Push chart
helm push my-chart-0.1.0.tgz homelab

# Install from Harbor
helm install my-release homelab/my-chart
```

## Support

### Getting Help

1. Check the [Troubleshooting section](#troubleshooting)
2. Review logs: `ssh root@192.168.20.100 'cd /opt/harbor && docker-compose logs'`
3. Consult documentation in `docs/` directory
4. Visit Harbor documentation: https://goharbor.io/docs/

### Useful Links

- **Harbor Official Docs**: https://goharbor.io/docs/
- **Harbor GitHub**: https://github.com/goharbor/harbor
- **Harbor API**: https://goharbor.io/docs/latest/build-customize-contribute/configure-swagger/
- **Trivy Scanner**: https://github.com/aquasecurity/trivy

## File Locations

| Item | Location |
|------|----------|
| Deployment Script | `scripts/deploy-harbor.sh` |
| Deployment Playbook | `playbooks/deploy-harbor.yml` |
| Ansible Role | `playbooks/roles/harbor/` |
| Docker Compose | `/opt/harbor/docker-compose.yml` (on orion-dev) |
| Harbor Data | `/opt/harbor/data/` (on orion-dev) |
| Harbor Logs | `/opt/harbor/logs/` (on orion-dev) |
| Documentation | `docs/HARBOR_*.md` |

## What's Next?

After deploying Harbor:

1. **Login** to the web UI and change the admin password (optional)
2. **Create projects** to organize your images
3. **Create users** or configure LDAP/OIDC authentication
4. **Configure Docker** on your development machines
5. **Start pushing images** to your private registry
6. **Integrate with CI/CD** pipelines
7. **Setup automated backups** for Harbor data

## Summary

✅ **Complete Harbor deployment configured**  
✅ **Automated deployment script**  
✅ **Comprehensive documentation**  
✅ **Integrated with existing infrastructure**  
✅ **Security best practices**  
✅ **Production-ready setup**

Harbor is ready to deploy! Run `./scripts/deploy-harbor.sh` to get started.

---

**Version**: Harbor v2.11.1  
**Created**: November 27, 2025  
**Status**: Ready for Deployment
