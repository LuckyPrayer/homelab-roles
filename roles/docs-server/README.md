# Documentation Server Ansible Role

This role deploys a containerized documentation web server that converts Homelab markdown documentation to beautiful, searchable HTML using MkDocs with the Material theme.

## Features

- 🚀 Automated deployment via Ansible
- 📚 Converts markdown docs to static HTML
- 🎨 Beautiful Material Design theme
- 🔍 Full-text search capability
- 📱 Responsive design
- 🔄 Optional Traefik integration
- ⚡ Multi-stage Docker build for minimal image size

## Requirements

- Docker installed on target host
- Ansible community.docker collection
- Target host must be in `docker_hosts` group

## Role Variables

Available variables with their defaults (see `defaults/main.yml`):

```yaml
# Enable/disable documentation server
docs_server_enabled: true

# Server configuration
docs_server_port: 8080
docs_server_container_name: homelab-docs
docs_server_image_name: homelab-docs
docs_server_image_tag: latest
docs_server_base_dir: /opt/homelab-docs

# Site metadata
docs_site_name: "Homelab Documentation"
docs_site_description: "Comprehensive documentation for Proxmox + Docker + Traefik Homelab"
docs_site_author: "LuckyPrayer"
docs_repo_url: "https://github.com/LuckyPrayer/Homelab"
docs_repo_name: "LuckyPrayer/Homelab"

# Theme configuration
docs_theme_name: material
docs_theme_primary_color: indigo
docs_theme_accent_color: indigo

# Traefik integration (optional)
docs_traefik_enabled: false
docs_traefik_subdomain: "docs"
docs_traefik_certresolver: "mytls"
```

## Dependencies

This role requires the `community.docker` Ansible collection:

```bash
ansible-galaxy collection install community.docker
```

## Example Playbook

### Basic Usage (standalone)

```yaml
- hosts: docker_hosts
  roles:
    - role: docs-server
```

### With Custom Configuration

```yaml
- hosts: docker_hosts
  roles:
    - role: docs-server
      vars:
        docs_server_port: 9090
        docs_theme_primary_color: blue
        docs_traefik_enabled: true
        docs_traefik_subdomain: "documentation"
```

### Integrated with Existing Docker Stack

```yaml
- hosts: docker_hosts
  roles:
    - docker-host
    - infisical
    - homelab-compose
    - docs-server  # Add after other services
      vars:
        docs_traefik_enabled: true
```

## Traefik Integration

To integrate with Traefik reverse proxy, set these variables:

```yaml
docs_traefik_enabled: true
docs_traefik_subdomain: "docs"  # Will create docs.dev.yourdomain.com
```

The documentation will be accessible at:
- Direct: `http://<host-ip>:8080`
- Traefik: `https://docs.<env>.<base_domain>`

## What This Role Does

1. Creates base directory structure at `/opt/homelab-docs`
2. Copies all documentation files from `docs/` directory
3. Copies main `README.md` as the documentation index
4. Templates the MkDocs configuration file
5. Templates the docker-compose configuration
6. Builds the Docker image using multi-stage build
7. Starts the documentation container
8. Waits for health check to pass
9. Displays access information

## Directory Structure Created

```
/opt/homelab-docs/
├── Dockerfile
├── docker-compose.yml
├── mkdocs.yml
└── docs/
    ├── index.md (copied from README.md)
    ├── QUICKSTART.md
    ├── DEPLOYMENT_GUIDE.md
    ├── troubleshooting/
    └── ... (all other docs)
```

## Accessing the Documentation

After deployment, access your documentation at:

```bash
http://<docker-host-ip>:8080
```

Or if Traefik is enabled:

```bash
https://docs.<env>.<base_domain>
```

## Updating Documentation

To update the documentation after changes:

```bash
ansible-playbook deploy-all.yml --tags docs-server
```

Or target specific hosts:

```bash
ansible-playbook deploy-all.yml -l docker-host-01-dev --tags docs-server
```

## Customization

### Change Theme Colors

```yaml
docs_theme_primary_color: blue  # Options: red, pink, purple, indigo, blue, etc.
docs_theme_accent_color: cyan
```

### Change Port

```yaml
docs_server_port: 9000
```

### Change Site Information

```yaml
docs_site_name: "My Custom Docs"
docs_site_description: "My custom documentation site"
```

## Troubleshooting

### Container fails to start

Check logs:
```bash
ssh <docker-host> docker logs homelab-docs
```

### Documentation not rendering correctly

Rebuild the image:
```bash
ansible-playbook deploy-all.yml -l <host> --tags docs-server -e docs_force_rebuild=true
```

### Port conflict

Change the port in your playbook:
```yaml
docs_server_port: 9090
```

## License

Part of the Homelab project.
