# Homelab Ansible Roles

Reusable Ansible roles for homelab infrastructure automation.

## Installation

Add to your `requirements.yml`:

```yaml
roles:
  - src: git+https://github.com/LuckyPrayer/homelab-roles.git
    version: main
    name: homelab-roles
```

Then install:

```bash
ansible-galaxy install -r requirements.yml
```

## Available Roles

### Infrastructure

| Role | Description |
|------|-------------|
| `proxmox-vm` | Provision VMs on Proxmox VE |
| `proxmox-cloud-init-template` | Create cloud-init templates |
| `proxmox-network-config` | Configure Proxmox networking |
| `router-vm` | Configure router VMs with NAT/routing |

### Docker & Containers

| Role | Description |
|------|-------------|
| `docker-host` | Install and configure Docker |
| `docker-backup` | Setup backup infrastructure |
| `docker-log-forwarder` | Configure log forwarding |
| `flush-docker-handlers` | Utility role for handler management |
| `homelab-apps` | Deploy apps from homelab-apps manifest |
| `homelab-compose` | Generic Docker Compose deployment |

### Services

| Role | Description |
|------|-------------|
| `harbor` | Deploy Harbor container registry |
| `komodo` | Deploy Komodo management platform |
| `traefik-proxy` | Deploy Traefik reverse proxy |
| `docs-server` | Deploy documentation server |

### Security & Networking

| Role | Description |
|------|-------------|
| `dns-cloudflare` | Manage Cloudflare DNS records |
| `infisical` | Setup Infisical secret management |
| `security-fail2ban` | Configure fail2ban |
| `security-users` | Manage system users and SSH keys |
| `tailscale` | Install and configure Tailscale VPN |

### Monitoring

| Role | Description |
|------|-------------|
| `monitoring-stack` | Deploy Prometheus/Grafana stack |
| `node-exporter` | Install Node Exporter |

### Other

| Role | Description |
|------|-------------|
| `ai-support-agent` | Deploy AI support Discord bot |
| `github-runner` | Setup GitHub Actions self-hosted runner |

## Role Variables

Each role has its own `defaults/main.yml` with configurable variables. See individual role READMEs for details.

## Usage Example

```yaml
- name: Configure Docker host
  hosts: docker_hosts
  roles:
    - role: docker-host
    - role: infisical
    - role: homelab-apps
      vars:
        homelab_apps_restore: true
```

## Requirements

- Ansible 2.15+
- Collections:
  - `community.general`
  - `community.docker`
  - `community.proxmox`
  - `ansible.posix`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with molecule (if available)
5. Submit a pull request

## License

MIT
