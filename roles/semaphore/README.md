# Semaphore Ansible Role

This role deploys [Ansible Semaphore](https://semaphoreui.com/) as a Docker container for managing Ansible playbook execution through a modern web UI.

## Overview

Semaphore provides a web-based interface for:
- Running Ansible playbooks with visual feedback
- Managing inventories, SSH keys, and credentials
- Scheduling automated playbook runs
- Tracking deployment history and logs
- Controlling access to deployment systems

## Requirements

- Docker installed on target host
- Infisical configured with Semaphore secrets
- Target host must be in `docker_hosts` group
- Traefik for HTTPS reverse proxy (optional)

## Role Variables

Available variables with their defaults (see `defaults/main.yml`):

```yaml
# Enable/disable Semaphore
semaphore_enabled: true

# Version and image
semaphore_version: "v2.10.22"
semaphore_image: "semaphoreui/semaphore:{{ semaphore_version }}"

# Directories
semaphore_base_dir: /opt/infrastructure/semaphore
semaphore_data_dir: "{{ semaphore_base_dir }}/data"

# Network
semaphore_port: 3100           # Host-mapped port
semaphore_container_port: 3000 # Internal container port
semaphore_hostname: "semaphore.{{ env }}.{{ base_domain }}"

# Traefik integration
semaphore_traefik_enabled: true
semaphore_traefik_certresolver: "mytls"
```

## Required Infisical Secrets

Create the following secrets at `/services/semaphore`:

| Secret | Description |
|--------|-------------|
| `SEMAPHORE_ADMIN_PASSWORD` | Admin user password |
| `SEMAPHORE_ACCESS_KEY_ENCRYPTION` | Encryption key for stored credentials |

```bash
# Generate and store secrets
infisical secrets set SEMAPHORE_ADMIN_PASSWORD="$(openssl rand -base64 24)" \
  --path=/services/semaphore --env=dev
infisical secrets set SEMAPHORE_ACCESS_KEY_ENCRYPTION="$(openssl rand -base64 32)" \
  --path=/services/semaphore --env=dev
```

## Usage

### Via deploy-all.yml (Phase 9A)

Semaphore is deployed automatically as part of the hephaestus host configuration:

```bash
./scripts/deployment/run-playbook.sh --env=dev deploy-all --limit hephaestus-dev
```

### Standalone

```bash
ansible-playbook -i inventories/dev/hosts.yml playbooks/deploy-all.yml \
  --limit hephaestus-dev --tags semaphore
```

## Access

After deployment:
- **External**: `https://semaphore.{env}.thebozic.com`
- **Direct**: `http://{host_ip}:3100`

## Architecture Notes

Semaphore is deployed as **infrastructure** (via an Ansible role) rather than an application (via homelab-apps manifest). This is because Semaphore will be the orchestrator that triggers playbooks to provision application services — it cannot be managed by the system it manages.

## Files

```
/opt/infrastructure/semaphore/
├── docker-compose.yml    # Templated by Ansible
├── .env                  # Secrets from Infisical
└── data/                 # BoltDB database and config
    └── database.boltdb
```
