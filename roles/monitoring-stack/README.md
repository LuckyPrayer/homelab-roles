# Monitoring Stack Role

This role deploys a complete monitoring and observability stack for the homelab environment.

## Components

| Component | Purpose | Port |
|-----------|---------|------|
| **Grafana** | Dashboards and visualization | 3000 |
| **Prometheus** | Metrics collection and alerting | 9090 |
| **Loki** | Log aggregation | 3100 |
| **Alertmanager** | Alert routing and management | 9093 |
| **Alloy** | Log collection agent | 12345 |
| **Node Exporter** | Host metrics | 9100 |
| **cAdvisor** | Container metrics | 8081 |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Argus VM                                  │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌─────────────┐  │
│  │  Grafana  │  │Prometheus │  │   Loki    │  │Alertmanager │  │
│  │   :3000   │  │   :9090   │  │   :3100   │  │    :9093    │  │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └──────┬──────┘  │
│        │              │              │               │          │
│        └──────────────┼──────────────┼───────────────┘          │
│                       │              │                          │
│  ┌───────────┐  ┌─────┴─────┐  ┌─────┴─────┐                   │
│  │   Alloy   │  │   Node    │  │ cAdvisor  │                   │
│  │  :12345   │  │  Exporter │  │   :8081   │                   │
│  └───────────┘  │   :9100   │  └───────────┘                   │
│                 └───────────┘                                   │
└─────────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
    ┌───────────────────┐   ┌───────────────────┐
    │    Other Hosts    │   │   Discord Bot     │
    │  (node_exporter)  │   │  /webhook/alert   │
    └───────────────────┘   └───────────────────┘
```

## Requirements

- Docker and Docker Compose installed (handled by docker-host role)
- Infisical CLI installed for secrets management
- Network connectivity to monitored hosts

## Variables

### Grafana

```yaml
grafana_enabled: true
grafana_port: 3000
grafana_admin_user: "admin"
# grafana_admin_password: fetched from Infisical
```

### Prometheus

```yaml
prometheus_enabled: true
prometheus_port: 9090
prometheus_retention_days: 30
prometheus_scrape_interval: "15s"
prometheus_scrape_targets:
  - job_name: "node"
    targets:
      - "192.168.20.100:9100"
      - "192.168.20.200:9100"
```

### Loki

```yaml
loki_enabled: true
loki_port: 3100
loki_retention_days: 30
```

### Alertmanager

```yaml
alertmanager_enabled: true
alertmanager_port: 9093
alertmanager_discord_webhook: "http://192.168.20.200:8085/webhook/alert"
```

## Infisical Secrets

Store the following secrets in Infisical at `/infrastructure/monitoring/grafana/`:

| Secret Name | Description |
|-------------|-------------|
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin password |

## Usage

### Deploy monitoring stack only

```bash
ansible-playbook playbooks/deploy-all.yml -i inventories/dev/hosts.yml \
  --tags monitoring --limit argus-dev
```

### Access Services

After deployment:

- **Grafana**: https://grafana.dev.thebozic.com (via Traefik proxy)
- **Prometheus**: https://prometheus.dev.thebozic.com
- **Alertmanager**: https://alertmanager.dev.thebozic.com

Or directly:

- **Grafana**: http://192.168.20.50:3000
- **Prometheus**: http://192.168.20.50:9090
- **Loki**: http://192.168.20.50:3100

## Adding Metrics from Other Hosts

To collect metrics from other hosts, deploy node_exporter on them:

```bash
# On target host
docker run -d \
  --name node-exporter \
  --restart unless-stopped \
  --net host \
  --pid host \
  -v "/:/host:ro,rslave" \
  prom/node-exporter:latest \
  --path.rootfs=/host
```

Then add the target to `prometheus_scrape_targets` in the inventory.

## Forwarding Logs from Other Hosts

Deploy Promtail on other hosts to forward logs to Loki:

```yaml
# promtail-config.yml on remote host
clients:
  - url: http://192.168.20.50:3100/loki/api/v1/push
```

## Alert Routing

Alerts are sent to the Discord bot webhook at `/webhook/alert`. The alert payload includes:

- Alert name and severity
- Instance and job information
- Description and summary annotations

## Dashboards

Pre-configured dashboards:

1. **Homelab Overview** - CPU, Memory, Disk usage across all hosts
2. Import additional dashboards from [Grafana Dashboard Library](https://grafana.com/grafana/dashboards/)

## Troubleshooting

### Check service status

```bash
ssh root@192.168.20.50 "docker compose -f /opt/monitoring/docker-compose.yml ps"
```

### View logs

```bash
ssh root@192.168.20.50 "docker logs grafana"
ssh root@192.168.20.50 "docker logs prometheus"
ssh root@192.168.20.50 "docker logs loki"
```

### Test Prometheus targets

Visit http://192.168.20.50:9090/targets to see scrape target status.

### Test Loki

```bash
curl -G -s "http://192.168.20.50:3100/loki/api/v1/labels" | jq
```
