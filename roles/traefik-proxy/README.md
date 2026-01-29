# Traefik Proxy Role

This Ansible role deploys Traefik as a reverse proxy on router VMs (e.g., hermes-dev) to enable cross-VLAN service access. It allows services from the management network to proxy traffic to services running in other VLANs (e.g., development or production VLANs).

## Use Case

In a multi-VLAN homelab environment:
- **hermes-dev** runs on management VLAN (192.168.2.0/24)
- **orion-dev** runs Docker services on development VLAN (192.168.20.0/24)
- Users on the management network need to access services on orion-dev

This role deploys Traefik on hermes-dev to proxy HTTPS traffic to backend services on orion-dev.

## Architecture

```
Management Network (192.168.2.0/24)
    │
    └─ hermes-dev (192.168.2.10)
       ├─ Traefik Proxy :80/:443
       │  ├─ n8n.dev.thebozic.com → http://192.168.20.100:5678
       │  ├─ mealie.dev.thebozic.com → http://192.168.20.100:9000
       │  └─ traefik.dev.thebozic.com → Traefik Dashboard on orion
       │
       └─ Routes via VLAN gateway to ↓

Development Network (192.168.20.0/24)
    │
    └─ orion-dev (192.168.20.100)
       ├─ n8n container :5678
       ├─ mealie container :9000
       └─ traefik container (local routing)
```

## Features

- **Reverse proxy** from management VLAN to service VLANs
- **TLS termination** with Let's Encrypt (DNS-01 challenge)
- **Security headers** (HSTS, XSS protection, etc.)
- **Health checks** for backend services
- **Dashboard** for monitoring proxy status
- **Dynamic configuration** via file provider

## Requirements

- Docker and docker-compose installed on the router VM
- DNS records pointing to the router VM IP
- Cloudflare API token (if using DNS challenge)
- Network routing configured between VLANs

## Role Variables

### Required Variables

```yaml
# Base domain for services
base_domain: "thebozic.com"

# Environment (dev, prod, etc.)
env: "dev"

# Backend services to proxy
traefik_proxy_backends:
  - name: "n8n"
    host: "n8n.dev.thebozic.com"
    backend_url: "http://192.168.20.100:5678"
    description: "n8n automation service"
  
  - name: "mealie"
    host: "mealie.dev.thebozic.com"
    backend_url: "http://192.168.20.100:9000"
    description: "Mealie recipe manager"
```

### Optional Variables

See `defaults/main.yml` for all available options:

```yaml
traefik_proxy_image: "traefik:2.11"
traefik_proxy_base_dir: "/opt/traefik-proxy"
traefik_proxy_email: "admin@{{ base_domain }}"
traefik_proxy_enable_dashboard: true
traefik_proxy_use_dns_challenge: true
traefik_proxy_dns_provider: "cloudflare"
traefik_proxy_http_port: 80
traefik_proxy_https_port: 443
```

## Usage

### 1. Configure Inventory

Add backend configuration to your router host in `inventories/dev/hosts.yml`:

```yaml
routers:
  hosts:
    hermes-dev:
      # ... existing config ...
      
      # Traefik proxy backends
      traefik_proxy_backends:
        - name: "n8n"
          host: "n8n.dev.thebozic.com"
          backend_url: "http://192.168.20.100:5678"
          description: "n8n automation service"
        
        - name: "mealie"
          host: "mealie.dev.thebozic.com"
          backend_url: "http://192.168.20.100:9000"
          description: "Mealie recipe manager"
        
        - name: "traefik-orion"
          host: "traefik.dev.thebozic.com"
          backend_url: "http://192.168.20.100:8080"
          description: "Traefik dashboard on orion"
          health_check_path: "/api/version"
```

### 2. Ensure Backend Services Expose Ports

On orion-dev, make sure services expose their ports so Traefik on hermes can reach them:

**Option A: Expose ports directly in docker-compose.yml**

```yaml
services:
  n8n:
    # ... existing config ...
    ports:
      - "5678:5678"  # Expose to host
  
  mealie:
    # ... existing config ...
    ports:
      - "9000:9000"  # Expose to host
```

**Option B: Use existing Traefik on orion**

If you want to keep Traefik on orion for service discovery, you can proxy to Traefik's dashboard API endpoint.

### 3. Run the Playbook

```bash
# Deploy Traefik proxy to hermes-dev
ansible-playbook -i inventories/dev/hosts.yml playbooks/provision-routers.yml
```

Or if using the run-playbook.sh script:

```bash
./scripts/run-playbook.sh provision-routers --env=dev
```

### 4. Verify Deployment

Check that Traefik is running:

```bash
# SSH to hermes-dev
ssh root@192.168.2.10

# Check container status
docker ps | grep traefik-proxy

# Check logs
docker logs traefik-proxy

# Verify configuration
cat /opt/traefik-proxy/config/proxy-rules.yml
```

### 5. Test Service Access

From a machine on the management network:

```bash
# Test HTTPS access
curl -k https://n8n.dev.thebozic.com
curl -k https://mealie.dev.thebozic.com
curl -k https://traefik.dev.thebozic.com

# Or open in browser
https://n8n.dev.thebozic.com
https://mealie.dev.thebozic.com
https://traefik.dev.thebozic.com
```

## Service Port Requirements

For this proxy setup to work, backend services must be accessible from hermes-dev. You have two options:

### Option 1: Direct Port Exposure (Recommended)

Expose service ports on orion-dev so hermes can directly connect to them:

```yaml
# On orion-dev docker-compose.yml
services:
  n8n:
    ports:
      - "5678:5678"
  mealie:
    ports:
      - "9000:9000"
```

### Option 2: Proxy to Orion's Traefik

Keep Traefik on orion handling service routing internally, and proxy to Traefik's HTTP endpoint:

```yaml
# Proxy to orion's Traefik
traefik_proxy_backends:
  - name: "n8n"
    host: "n8n.dev.thebozic.com"
    backend_url: "http://192.168.20.100:80"  # Orion's Traefik HTTP port
```

This requires orion's Traefik to handle the Host header correctly.

## Troubleshooting

### Traefik container not starting

```bash
# Check logs
docker logs traefik-proxy

# Check config syntax
docker run --rm -v /opt/traefik-proxy/config:/config traefik:2.11 \
  --configFile=/config/proxy-rules.yml --validateConfig
```

### Certificate issues

```bash
# Check acme.json permissions
ls -la /opt/traefik-proxy/acme.json
# Should be -rw------- (600)

# Check Cloudflare token
docker exec traefik-proxy env | grep CF_DNS_API_TOKEN

# Check certificate generation logs
docker logs traefik-proxy | grep -i acme
```

### Backend service unreachable

```bash
# From hermes-dev, test backend connectivity
curl -I http://192.168.20.100:5678
telnet 192.168.20.100 5678

# Check routing
ip route get 192.168.20.100

# Check firewall rules
iptables -L -v -n
```

### DNS resolution issues

```bash
# Test DNS from client machine
nslookup n8n.dev.thebozic.com
dig n8n.dev.thebozic.com

# Should resolve to 192.168.2.10 (hermes)
```

## Security Considerations

1. **TLS certificates**: Use DNS challenge to avoid exposing services to the internet
2. **Backend access**: Ensure backend services are only accessible from router VM
3. **Firewall rules**: Restrict access to proxy ports (80, 443) as needed
4. **Security headers**: Enabled by default in proxy-rules.yml
5. **Health checks**: Monitor backend service availability

## Integration with Existing Setup

This role is designed to work alongside:
- **router-vm**: Configures network routing and firewalls
- **homelab-compose**: Deploys services on orion-dev
- **dns-cloudflare**: Manages DNS records

The complete flow:
1. `router-vm` sets up hermes-dev with networking
2. `traefik-proxy` deploys the reverse proxy on hermes-dev
3. `homelab-compose` deploys services on orion-dev
4. DNS records point to hermes-dev (192.168.2.10)
5. Traefik proxies traffic to orion-dev backends

## License

MIT

## Author

Created for the Homelab automation project.
