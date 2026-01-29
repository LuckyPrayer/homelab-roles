# Docker Log Forwarder Role

Deploys a systemd service that forwards Docker container logs to the Homelab Discord bot for host-based channel routing.

## Features

- ✅ Automatic container log forwarding
- ✅ Host-based channel routing (logs go to host-specific channels)
- ✅ Container-specific channels (auto-created on first log)
- ✅ Log level filtering
- ✅ Batch log sending for efficiency
- ✅ Automatic container discovery
- ✅ Excludes noisy/system containers

## Requirements

- Docker installed and running
- Discord bot deployed with server-as-code features
- Network connectivity to Discord bot webhook endpoint

## Role Variables

```yaml
# Enable the log forwarder service
docker_log_forwarder_enabled: true

# Discord bot webhook URL
discord_bot_webhook_url: "http://192.168.20.200:8085"

# Minimum log level to forward: debug, info, warning, error
docker_log_forwarder_level: info

# Batch settings
docker_log_forwarder_batch_size: 10
docker_log_forwarder_batch_timeout: 5

# Containers to exclude (regex patterns)
docker_log_forwarder_exclude:
  - "^k8s_.*"
  - "^POD$"
  - "log-forwarder"
```

## Dependencies

- `discord-bot` role (for the bot files and scripts)

## Example Playbook

```yaml
- hosts: docker_hosts
  become: true
  vars:
    discord_bot_webhook_url: "http://192.168.20.200:8085"
  roles:
    - docker-log-forwarder
```

## What Gets Installed

| File | Purpose |
|------|---------|
| `/opt/scripts/docker-log-forwarder.sh` | Main log forwarding script |
| `/usr/local/bin/discord-log.sh` | Manual log sending helper |
| `/usr/local/bin/discord-log` | Symlink to helper |
| `/etc/systemd/system/docker-log-forwarder.service` | Systemd service unit |
| `/etc/default/docker-log-forwarder` | Environment configuration |

## Service Management

```bash
# Check status
sudo systemctl status docker-log-forwarder

# View logs
sudo journalctl -u docker-log-forwarder -f

# Restart service
sudo systemctl restart docker-log-forwarder

# Disable forwarding
sudo systemctl stop docker-log-forwarder
sudo systemctl disable docker-log-forwarder
```

## Manual Log Sending

The role also installs a helper script for manual log sending:

```bash
# Basic usage
discord-log.sh myapp "Application started" info

# With container routing (creates container-specific channel)
discord-log.sh traefik "Certificate renewed" info orion-dev traefik

# Pipe logs
tail -f /var/log/app.log | discord-log.sh myapp - error
```

## Channel Routing

Logs are routed based on the server definition:

1. **Container Channel**: If host + container specified, creates/uses container channel
2. **Host System Logs**: If only host specified, goes to host's system_logs channel
3. **Default Logs**: Falls back to general logs channel

## Integration with Backups

The role also copies the `discord-bot-integration.sh` library for use in backup scripts:

```bash
# In your backup script
source /opt/scripts/discord-bot-integration.sh

# Send backup notifications
send_backup_notification "n8n" "success" "Backup completed" "2m 30s" "150MB" "n8n" "redis"

# Send container-specific logs
send_container_log "n8n" "Starting backup process..." "info"
```

## Troubleshooting

### Logs Not Appearing in Discord

1. Check service status: `systemctl status docker-log-forwarder`
2. Verify webhook URL: `curl http://bot-host:8085/health`
3. Check service logs: `journalctl -u docker-log-forwarder -n 50`
4. Test manually: `discord-log.sh test "Hello" info`

### Container Channels Not Being Created

1. Ensure `/server-sync` was run in Discord
2. Check host is defined in `server_definition.yml`
3. Verify container channels are enabled in definition

### High CPU/Memory Usage

1. Increase batch size: Edit `/etc/default/docker-log-forwarder`
2. Increase batch timeout
3. Raise log level filter to `warning` or `error`
4. Add noisy containers to exclude list

## License

MIT

## Author

Homelab Infrastructure Team
