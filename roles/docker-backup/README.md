# Docker Backup Role

Ansible role for automated Docker container backup and restore using Restic and Backblaze B2.

## Features

- ✅ Incremental backups with restic
- ✅ Automatic daily scheduling via systemd timer
- ✅ Backblaze B2 cloud storage integration
- ✅ Discord webhook notifications
- ✅ Automatic container stop/start during backup
- ✅ Retention management (30 days default)
- ✅ One-command restore from latest or specific snapshot
- ✅ Encrypted backups

## Requirements

- Docker and Docker Compose installed
- Infisical CLI installed (for secret management)
- Backblaze B2 account and bucket
- Discord webhook URL (optional, for notifications)

## Role Variables

### Required Variables

These must be set in Infisical at path `/infrastructure/backup`:

- `B2_ACCOUNT_ID` - Backblaze B2 Application Key ID
- `B2_ACCOUNT_KEY` - Backblaze B2 Application Key
- `B2_BUCKET` - Backblaze B2 bucket name
- `RESTIC_PASSWORD` - Encryption password for restic repository

### Optional Variables

Available in `defaults/main.yml`:

```yaml
# Enable/disable backup
backup_enabled: true

# Backup schedule
backup_schedule: "daily"  # daily, weekly, or cron format
backup_time: "02:00"      # 24-hour format

# Retention
backup_retention_days: 30

# Containers to backup
backup_containers:
  - n8n
  - mealie
  - traefik
  - mentalhospital-mc
  - pihole
  - harbor-db           # Harbor PostgreSQL database
  - harbor-redis        # Harbor Redis cache
  - harbor-core         # Harbor core services
  - harbor-jobservice   # Harbor job service
  - harbor-registry     # Harbor registry
  - harbor-portal       # Harbor web UI
  - harbor-log          # Harbor logging
  - trivy-adapter       # Harbor vulnerability scanner
  - nginx               # Harbor nginx proxy
  - registryctl         # Harbor registry controller

# Harbor-specific backup (automatically includes Harbor data directories)
backup_harbor_enabled: true
backup_harbor_data_dir: "/opt/harbor/data"
backup_harbor_config_dir: "/opt/harbor-installer/harbor"

# Restore settings (for automated restore during deployment)
restore_enabled: false
restore_snapshot_id: "latest"

# Discord webhook (optional)
backup_discord_webhook: "{{ lookup('infisical', 'DISCORD_WEBHOOK_URL', ...) }}"
```

## Dependencies

None. This role can be used standalone or as part of a larger playbook.

## Example Playbook

```yaml
---
- name: Setup Docker backup
  hosts: docker_hosts
  become: true
  roles:
    - role: docker-backup
      backup_enabled: true
      backup_schedule: "daily"
      backup_time: "02:00"
      backup_retention_days: 30
```

## Usage

### Deploy Backup System

```bash
# Deploy to all docker hosts
ansible-playbook -i inventories/prod/hosts.yml playbooks/deploy-all.yml --tags backup

# Deploy to specific host
ansible-playbook -i inventories/prod/hosts.yml playbooks/deploy-all.yml --tags backup --limit orion-prod
```

### Manual Backup

```bash
ssh orion-prod
sudo /opt/backup-scripts/docker-backup.sh
```

### Restore from Backup

```bash
# Restore from latest snapshot
ssh orion-prod
sudo /opt/backup-scripts/docker-restore.sh

# Interactive restore (choose snapshot)
sudo /opt/backup-scripts/docker-restore.sh --interactive

# Restore specific snapshot
sudo /opt/backup-scripts/docker-restore.sh <snapshot-id>
```

### Automated Restore During Deployment

Set in host_vars or group_vars:

```yaml
restore_enabled: true
restore_snapshot_id: "latest"
```

Then run playbook:

```bash
ansible-playbook -i inventories/prod/hosts.yml playbooks/deploy-all.yml --tags backup
```

## File Structure

```
docker-backup/
├── defaults/
│   └── main.yml              # Default variables
├── tasks/
│   ├── main.yml              # Main tasks (install, configure)
│   └── restore.yml           # Restore tasks
├── templates/
│   ├── docker-backup.sh.j2   # Backup script
│   ├── docker-restore.sh.j2  # Restore script
│   ├── docker-backup.service.j2  # Systemd service
│   ├── docker-backup.timer.j2    # Systemd timer
│   └── backup.env.j2         # Environment variables
├── handlers/
│   └── main.yml              # Handlers (reload systemd)
└── README.md                 # This file
```

## Scripts Deployed

### `/opt/backup-scripts/docker-backup.sh`

Main backup script that:
1. Stops Docker containers
2. Creates incremental backup with restic
3. Uploads to Backblaze B2
4. Restarts containers
5. Prunes old backups
6. Sends Discord notification

### `/opt/backup-scripts/docker-restore.sh`

Restore script that:
1. Lists available snapshots (if interactive)
2. Stops containers
3. Backs up current state
4. Restores from snapshot
5. Restarts containers
6. Sends Discord notification

### `/opt/backup-scripts/.backup.env`

Environment file containing:
- Restic repository URL
- Restic password
- Backblaze B2 credentials
- Discord webhook URL

## Systemd Services

### docker-backup.timer

Timer that triggers backup daily at 2 AM (configurable).

```bash
# Check timer status
systemctl status docker-backup.timer

# View next scheduled run
systemctl list-timers docker-backup.timer

# Enable/disable timer
systemctl enable docker-backup.timer
systemctl disable docker-backup.timer
```

### docker-backup.service

Service that runs the backup script.

```bash
# Check service status
systemctl status docker-backup.service

# View logs
journalctl -u docker-backup.service -n 50

# Run manually (via systemctl)
systemctl start docker-backup.service
```

## Monitoring

### Check Backup Status

```bash
# Timer status
systemctl status docker-backup.timer

# Last backup time
systemctl status docker-backup.service

# Backup logs
journalctl -u docker-backup.service -n 100
tail -f /var/log/docker-backup.log
```

### Verify Backups

```bash
# List snapshots
source /opt/backup-scripts/.backup.env
restic snapshots

# Show latest snapshot
restic snapshots --latest 1

# Repository statistics
restic stats

# Check repository integrity
restic check
```

## Notifications

Discord notifications are sent for:

- ✅ **Success** - Green embed with snapshot ID, size, and duration
- ⚠️ **Warning** - Orange embed for non-critical issues
- ❌ **Failure** - Red embed for backup failures
- 🔄 **In Progress** - Blue embed when restore starts

## Troubleshooting

### Backup not running

```bash
# Check timer is enabled
systemctl is-enabled docker-backup.timer

# Check timer is active
systemctl is-active docker-backup.timer

# Enable and start
sudo systemctl enable --now docker-backup.timer
```

### Repository access error

```bash
# Verify credentials
source /opt/backup-scripts/.backup.env
echo $B2_ACCOUNT_ID
echo $RESTIC_REPOSITORY

# Test connection
restic snapshots
```

### Restore fails

```bash
# Check available snapshots
restic snapshots

# Verify repository integrity
restic check

# Try restoring to temp location
restic restore latest --target /tmp/test-restore
```

## Harbor-Specific Backup

Harbor container registry has special backup considerations:

### What Gets Backed Up

1. **Harbor Database** (`harbor-db` PostgreSQL container)
   - User accounts and permissions
   - Project configurations
   - Image metadata and tags
   - Vulnerability scan results
   - Audit logs

2. **Harbor Data Directory** (`/opt/harbor/data`)
   - Registry storage (Docker image layers)
   - Database files
   - Redis data
   - Job service data
   - Scanner cache

3. **Harbor Configuration** (`/opt/harbor-installer/harbor`)
   - harbor.yml configuration
   - docker-compose.yml
   - Generated certificates
   - Internal configs

### Harbor Backup Process

The backup script automatically handles Harbor's unique structure:

1. Stops all Harbor containers (managed separately from main docker-compose)
2. Backs up both `/opt/harbor/data` and `/opt/harbor-installer/harbor`
3. Backs up Harbor container volumes
4. Restarts Harbor containers after backup

### Harbor Restore Considerations

When restoring Harbor:

1. Harbor configuration and data are restored to their original locations
2. All Harbor containers are stopped before restore
3. After restore, Harbor is started via its own docker-compose
4. Database migrations are handled automatically by Harbor on startup

### Manual Harbor Backup

If you need to backup Harbor separately:

```bash
# Stop Harbor
cd /opt/harbor-installer/harbor
docker compose down

# Backup Harbor data and config
tar czf harbor-backup-$(date +%Y%m%d).tar.gz \
  /opt/harbor/data \
  /opt/harbor-installer/harbor

# Restart Harbor
docker compose up -d
```

### Manual Harbor Restore

```bash
# Stop Harbor
cd /opt/harbor-installer/harbor
docker compose down

# Extract backup
tar xzf harbor-backup-YYYYMMDD.tar.gz -C /

# Start Harbor
docker compose up -d
```

## Security

- Backup scripts run as root with restricted permissions (0750)
- Environment file is not world-readable (0600)
- Data is encrypted before upload using restic
- Credentials stored in Infisical, not in code
- Systemd service has security restrictions enabled
- Harbor database password encrypted in transit and at rest

## Cost

Backblaze B2 pricing:
- Storage: $0.005/GB/month
- Downloads: First 3× average storage free
- 10 GB free tier

Example: 100 GB backup = ~$0.50/month

## Links

- [Full Documentation](../../docs/DOCKER_BACKUP_RESTORE.md)
- [Restic Documentation](https://restic.readthedocs.io/)
- [Backblaze B2 Documentation](https://www.backblaze.com/b2/docs/)

## License

Part of the Homelab project.

## Author

Created for automated homelab backup and disaster recovery.
