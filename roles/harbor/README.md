# Harbor Container Registry Role

This role deploys Harbor, a private container registry, to your homelab Docker hosts using the **official Harbor installer**.

## Description

Harbor is an open-source container registry that secures artifacts with policies and role-based access control, ensures images are scanned and free from vulnerabilities, and signs images as trusted.

This role uses Harbor's official installer package, which provides:
- Automated configuration generation via `prepare` script
- Proper permissions and directory structure
- Internal TLS certificate generation
- Official docker-compose orchestration
- Easier upgrades and maintenance

## Features

- **Private Container Registry**: Store and distribute Docker images securely
- **Vulnerability Scanning**: Built-in Trivy scanner for security analysis
- **Access Control**: Role-based access control (RBAC) for projects and users
- **Replication**: Support for multi-registry replication
- **Helm Chart Repository**: Store Helm charts alongside Docker images
- **Web UI**: User-friendly web interface for management
- **API**: Full REST API for automation
- **Official Installer**: Uses Harbor's tested installation method

## Requirements

- Docker and docker-compose installed on the target host
- Sufficient disk space for container images (recommend 100GB+)
- Infisical CLI installed (for secrets management)
- Traefik proxy configured (for HTTPS access)

## Role Variables

### Required Variables

```yaml
# Base domain for services
base_domain: "thebozic.com"

# Environment (dev, prod, etc.)
env: "dev"

# Infisical configuration
infisical_service_token: "{{ lookup('env', 'INFISICAL_TOKEN') }}"
infisical_project_id: "{{ lookup('env', 'INFISICAL_PROJECT_ID') }}"
infisical_env_slug: "dev"
```

### Optional Variables

See `defaults/main.yml` for all available options:

```yaml
harbor_version: "v2.11.1"
harbor_install_dir: "/opt/harbor-installer"  # Where installer is extracted
harbor_data_dir: "/opt/harbor/data"          # Where data is stored
harbor_http_port: 8082
harbor_hostname: "harbor.{{ env }}.{{ base_domain }}"
harbor_trivy_enabled: true
harbor_log_level: "info"
```

## Infisical Secrets

This role expects the following secrets in Infisical:

**Path**: `/infrastructure/harbor`  
**Environment**: `dev` or `prod`

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `HARBOR_ADMIN_PASSWORD` | Admin user password (min 8 chars) | `SuperSecurePassword123!` |
| `HARBOR_DB_PASSWORD` | PostgreSQL database password | `DbPassword123!` |
| `HARBOR_SECRET_KEY` | Encryption key (16 characters) | `1234567890abcdef` |

### Creating Secrets

```bash
# Generate secure passwords
ADMIN_PASS=$(openssl rand -base64 32)
DB_PASS=$(openssl rand -base64 32)
SECRET_KEY=$(openssl rand -hex 8)  # 16 hex chars = 8 bytes

# Set secrets in Infisical
infisical secrets set HARBOR_ADMIN_PASSWORD="$ADMIN_PASS" \
  --path="/infrastructure/harbor" --env=dev

infisical secrets set HARBOR_DB_PASSWORD="$DB_PASS" \
  --path="/infrastructure/harbor" --env=dev

infisical secrets set HARBOR_SECRET_KEY="$SECRET_KEY" \
  --path="/infrastructure/harbor" --env=dev

# Save admin password for later use
echo "Harbor Admin Password: $ADMIN_PASS" | tee ~/harbor-admin-password.txt
chmod 600 ~/harbor-admin-password.txt
```

## Usage

### 1. Add to Inventory

Add Harbor configuration to your host in `inventories/dev/hosts.yml`:

```yaml
docker_hosts:
  hosts:
    orion-dev:
      # ... existing config ...
      
      # Harbor configuration
      harbor_enabled: true
      harbor_http_port: 8082
```

### 2. Add to Playbook

Include the role in your playbook:

```yaml
- name: Deploy Harbor
  hosts: docker_hosts
  become: yes
  roles:
    - role: harbor
      when: harbor_enabled | default(false)
```

### 3. Configure Traefik Proxy

Add Harbor backend to hermes-dev in `inventories/dev/hosts.yml`:

```yaml
routers:
  hosts:
    hermes-dev:
      traefik_proxy_backends:
        - name: "harbor"
          host: "harbor.dev.thebozic.com"
          backend_url: "http://192.168.20.100:8082"
          description: "Harbor container registry on orion-dev"
          health_check_path: "/api/v2.0/systeminfo"
```

### 4. Add DNS Record

Add DNS record in `inventories/dev/group_vars/all.yml`:

```yaml
dns_records:
  - hostname: "harbor.dev.thebozic.com"
    ip: "192.168.2.10"
    description: "Harbor container registry (proxied to orion-dev)"
```

### 5. Deploy

```bash
# Deploy Harbor to docker host
ansible-playbook -i inventories/dev/hosts.yml \
  playbooks/deploy-harbor.yml \
  --limit orion-dev

# Update Traefik proxy on hermes-dev
ansible-playbook -i inventories/dev/hosts.yml \
  playbooks/provision-routers.yml \
  --limit hermes-dev \
  --tags proxy

# Update DNS records
ansible-playbook -i inventories/dev/hosts.yml \
  playbooks/deploy-dns.yml
```

## Post-Deployment

### Access Harbor

1. **Web UI**: https://harbor.dev.thebozic.com
2. **Default credentials**:
   - Username: `admin`
   - Password: Check Infisical at `/infrastructure/harbor/HARBOR_ADMIN_PASSWORD`

### Initial Setup

1. **Change admin password** (if not using strong password)
2. **Create projects** for organizing images
3. **Create users** or configure LDAP/OIDC authentication
4. **Configure vulnerability scanning** settings
5. **Set up replication** (optional)

### Using Harbor

#### Docker Login

```bash
# Login to Harbor
docker login harbor.dev.thebozic.com
Username: admin
Password: <your-password>

# Login successful
```

#### Push Images

```bash
# Tag an image
docker tag nginx:latest harbor.dev.thebozic.com/library/nginx:latest

# Push to Harbor
docker push harbor.dev.thebozic.com/library/nginx:latest
```

#### Pull Images

```bash
# Pull from Harbor
docker pull harbor.dev.thebozic.com/library/nginx:latest
```

## Management

### Harbor Commands

All management is done via docker-compose in the Harbor installation directory:

```bash
# SSH to the host
ssh root@192.168.20.100

# Navigate to Harbor directory
cd /opt/harbor-installer/harbor

# View container status
docker compose ps

# View logs (all services)
docker compose logs -f

# View logs (specific service)
docker compose logs -f harbor-core
docker compose logs -f harbor-registry
docker compose logs -f harbor-jobservice

# Stop Harbor
docker compose stop

# Start Harbor
docker compose start

# Restart Harbor
docker compose restart

# Stop and remove containers (data preserved)
docker compose down

# Start Harbor again
docker compose up -d
```

### Upgrading Harbor

```bash
# The role will handle upgrades automatically:
# 1. Downloads new version
# 2. Stops old version
# 3. Runs prepare script
# 4. Starts new version

# Just update the version in defaults/main.yml and re-run playbook
ansible-playbook -i inventories/dev/hosts.yml \
  playbooks/deploy-harbor.yml \
  --limit orion-dev
```

## Monitoring

### Health Check

```bash
# Check Harbor health
curl https://harbor.dev.thebozic.com/api/v2.0/health

# Check system info
curl -u admin:password https://harbor.dev.thebozic.com/api/v2.0/systeminfo

# Check direct (without Traefik)
curl http://192.168.20.100:8082/api/v2.0/health
```

### Container Status

```bash
ssh root@192.168.20.100
docker ps --filter "name=harbor" --format "table {{.Names}}\t{{.Status}}"
```

### Disk Usage

```bash
# Check Harbor data directory size
du -sh /opt/harbor/data

# Check registry size
du -sh /opt/harbor/data/registry
```

## Maintenance

### Backup

```bash
# Stop Harbor
docker-compose -f /opt/harbor/docker-compose.yml down

# Backup data
tar czf harbor-backup-$(date +%Y%m%d).tar.gz \
  /opt/harbor/data \
  /opt/harbor/docker-compose.yml \
  /opt/harbor/.env

# Start Harbor
docker-compose -f /opt/harbor/docker-compose.yml up -d
```

### Restore

```bash
# Stop Harbor
docker-compose -f /opt/harbor/docker-compose.yml down

# Restore data
tar xzf harbor-backup-YYYYMMDD.tar.gz -C /

# Start Harbor
docker-compose -f /opt/harbor/docker-compose.yml up -d
```

### Garbage Collection

Harbor automatically runs garbage collection daily at midnight. To run manually:

1. Go to Harbor UI → Administration → Garbage Collection
2. Click "GC Now"
3. Or use API:
   ```bash
   curl -X POST -u admin:password \
     https://harbor.dev.thebozic.com/api/v2.0/system/gc/schedule
   ```

### Upgrade

```bash
# Update version in defaults/main.yml
harbor_version: "v2.12.0"

# Re-run playbook
ansible-playbook -i inventories/dev/hosts.yml \
  playbooks/deploy-harbor.yml \
  --limit orion-dev
```

## Troubleshooting

### Container Not Starting

```bash
# Check logs
docker logs harbor-core
docker logs harbor-db

# Check disk space
df -h /opt/harbor/data

# Verify secrets are set
cd /opt/harbor
cat .env | grep -v "^#"
```

### Cannot Login

- Verify admin password in Infisical
- Check Harbor logs: `docker logs harbor-core`
- Ensure database is healthy: `docker exec harbor-db pg_isready`

### Slow Image Push/Pull

- Check network connectivity between client and Harbor
- Monitor disk I/O: `iostat -x 5`
- Check available disk space: `df -h`
- Consider increasing resources (CPU/RAM) if needed

### Certificate Issues

- Harbor SSL is handled by Traefik proxy on hermes-dev
- Verify Traefik is running and configured correctly
- Check DNS resolution: `nslookup harbor.dev.thebozic.com`

## Security Best Practices

1. **Use Strong Passwords**: Generate cryptographically secure passwords
2. **Enable Vulnerability Scanning**: Keep Trivy database updated
3. **Implement RBAC**: Create separate users/projects for different teams
4. **Regular Backups**: Automate backup of Harbor data
5. **Monitor Access**: Review audit logs regularly
6. **Content Trust**: Enable Docker Content Trust (Notary) for production
7. **Network Isolation**: Keep Harbor on isolated VLAN
8. **Update Regularly**: Keep Harbor and base images up to date

## References

- [Harbor Documentation](https://goharbor.io/docs/)
- [Harbor GitHub](https://github.com/goharbor/harbor)
- [Harbor API](https://goharbor.io/docs/latest/api/)
