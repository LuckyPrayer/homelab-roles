# GitHub Actions Self-Hosted Runner Role

Deploys and configures a GitHub Actions self-hosted runner as a systemd service.

## Requirements

- Target must have Docker installed (for docker-based actions)
- GitHub repository with Actions enabled
- Runner registration token from GitHub

## Role Variables

### Required Variables

| Variable | Description |
|----------|-------------|
| `github_runner_repo_url` | Full URL to GitHub repository (e.g., `https://github.com/user/repo`) |
| `github_runner_token` | Runner registration token from GitHub |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `github_runner_version` | `latest` | Runner version to install |
| `github_runner_arch` | `x64` | Architecture (`x64`, `arm`, `arm64`) |
| `github_runner_user` | `github-runner` | System user for the runner |
| `github_runner_groups` | `[docker]` | Additional groups for runner user |
| `github_runner_dir` | `/opt/actions-runner` | Installation directory |
| `github_runner_name` | `{{ inventory_hostname }}` | Runner name in GitHub |
| `github_runner_labels` | `[self-hosted, Linux, X64, homelab, {{ env }}]` | Runner labels |
| `github_runner_force_reconfigure` | `false` | Force reconfiguration |

## Getting the Runner Token

1. Go to your GitHub repository
2. Navigate to **Settings** → **Actions** → **Runners**
3. Click **New self-hosted runner**
4. Copy the token from the configuration command

**Important:** The token expires after ~1 hour. For automation, store it in Infisical and retrieve it at deploy time.

### Storing Token in Infisical

```bash
# Add to Infisical at /infrastructure/github-runner/
GITHUB_RUNNER_TOKEN=your-token-here
GITHUB_RUNNER_REPO_URL=https://github.com/yourusername/Homelab
```

## Example Playbook

```yaml
- hosts: hephaestus-dev
  roles:
    - role: github-runner
      vars:
        github_runner_repo_url: "{{ lookup('env', 'GITHUB_RUNNER_REPO_URL') }}"
        github_runner_token: "{{ lookup('env', 'GITHUB_RUNNER_TOKEN') }}"
        github_runner_labels:
          - self-hosted
          - Linux
          - X64
          - homelab
          - dev
          - docker
```

## Dependencies

None.

## Post-Installation

After the runner is installed, verify it appears in GitHub:

1. Go to **Settings** → **Actions** → **Runners**
2. Runner should show as "Idle" (green dot)

## Managing the Runner

```bash
# SSH to the host
ssh -J root@192.168.2.10 root@192.168.20.200

# Check service status
systemctl status actions.runner.*

# View logs
journalctl -u actions.runner.* -f

# Restart runner
cd /opt/actions-runner && ./svc.sh restart

# Stop runner
cd /opt/actions-runner && ./svc.sh stop

# Uninstall runner
cd /opt/actions-runner && ./svc.sh uninstall
./config.sh remove --token YOUR_TOKEN
```

## License

MIT
