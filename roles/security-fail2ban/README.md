# Security Fail2ban Role

Installs and configures fail2ban for intrusion prevention across all homelab hosts.

## Features

- ✅ SSH brute-force protection (enabled by default)
- ✅ Traefik auth failure protection (optional)
- ✅ Docker-aware configuration
- ✅ Discord webhook notifications (optional)
- ✅ Whitelist support for trusted IPs

## Requirements

- Debian/Ubuntu-based system
- systemd

## Variables

### Default Variables (`defaults/main.yml`)

```yaml
# Enable/disable fail2ban entirely
fail2ban_enabled: true

# Global settings
fail2ban_ignoreip: "127.0.0.1/8 ::1 192.168.2.0/24"  # Management VLAN always whitelisted
fail2ban_bantime: "1h"
fail2ban_findtime: "10m"
fail2ban_maxretry: 5

# SSH jail (enabled by default)
fail2ban_sshd_enabled: true
fail2ban_sshd_port: "ssh"
fail2ban_sshd_maxretry: 3
fail2ban_sshd_bantime: "24h"

# Traefik jail (for auth failures)
fail2ban_traefik_enabled: false
fail2ban_traefik_logpath: "/opt/stacks/traefik/logs/access.log"

# Discord notifications
fail2ban_discord_enabled: false
# FAIL2BAN_DISCORD_WEBHOOK from Infisical /infrastructure/fail2ban/
```

## Jails Included

| Jail | Default | Description |
|------|---------|-------------|
| `sshd` | Enabled | Bans IPs after SSH auth failures |
| `traefik-auth` | Disabled | Bans IPs after Traefik 401/403 responses |

## Usage

Enable in host inventory:

```yaml
orion-dev:
  fail2ban_enabled: true
  fail2ban_sshd_maxretry: 3
  fail2ban_traefik_enabled: true  # If running Traefik
```

## Checking Status

```bash
# View all jails
sudo fail2ban-client status

# View specific jail
sudo fail2ban-client status sshd

# Unban an IP
sudo fail2ban-client set sshd unbanip 192.168.1.100
```

## Tags

- `security` - All security tasks
- `fail2ban` - Only fail2ban tasks
