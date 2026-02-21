# Tailscale Role

This Ansible role installs and configures [Tailscale](https://tailscale.com/) VPN for secure remote access to the homelab.

## Features

- Installs Tailscale from official repository
- Configures subnet routing for internal network access
- Fetches auth key from Infisical (or uses provided key)
- Configures firewall rules for Tailscale traffic
- Supports exit node configuration
- Enables Tailscale SSH for keyless SSH access

## Requirements

- Debian-based Linux distribution (tested on Debian 13)
- Root access (become: yes)
- Tailscale account with auth key
- (Optional) Infisical for secrets management

## Role Variables

### Required Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `tailscale_enabled` | Enable/disable Tailscale | `false` |
| `tailscale_auth_key` | Tailscale auth key (if not using Infisical) | `""` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `tailscale_hostname` | Node hostname in Tailscale | `{{ inventory_hostname }}` |
| `tailscale_advertise_routes` | Subnets to advertise | `[]` |
| `tailscale_accept_routes` | Accept routes from other nodes | `true` |
| `tailscale_exit_node` | Advertise as exit node | `false` |
| `tailscale_accept_dns` | Accept Tailscale DNS (MagicDNS) | `false` |
| `tailscale_ssh` | Enable Tailscale SSH | `true` |
| `tailscale_tags` | ACL tags for the node | `[]` |
| `tailscale_force_reauth` | Force re-authentication | `false` |

### Infisical Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `tailscale_infisical_enabled` | Fetch auth key from Infisical | `true` |
| `tailscale_infisical_path` | Infisical secret path | `/infrastructure/vpn/tailscale` |
| `tailscale_infisical_key_name` | Secret key name | `TAILSCALE_AUTH_KEY` |

## Dependencies

- `infisical` role (optional, for secrets management)

## Example Usage

### Inventory Configuration (host_vars)

```yaml
# In inventories/prod/hosts.yml under hermes-prod
tailscale_enabled: true
tailscale_hostname: "hermes-prod"
tailscale_advertise_routes:
  - "192.168.10.0/24"  # Production VLAN
  - "192.168.68.0/24"   # Management network
tailscale_accept_routes: true
tailscale_exit_node: false
tailscale_accept_dns: false  # Keep using Pi-hole
tailscale_ssh: true
```

### Playbook Usage

```yaml
- name: Deploy Tailscale
  hosts: routers
  become: yes
  roles:
    - role: infisical
    - role: tailscale
```

### Standalone Deployment

```bash
# Deploy to dev environment
ansible-playbook -i inventories/dev/hosts.yml playbooks/deploy-tailscale.yml

# Deploy to specific host
ansible-playbook -i inventories/prod/hosts.yml playbooks/deploy-tailscale.yml --limit hermes-prod

# Force re-authentication
ansible-playbook -i inventories/dev/hosts.yml playbooks/deploy-tailscale.yml -e tailscale_force_reauth=true
```

## Setup Instructions

### 1. Generate Tailscale Auth Key

1. Go to [Tailscale Admin Console](https://login.tailscale.com/admin/settings/keys)
2. Click "Generate auth key"
3. Configure:
   - **Reusable**: Yes (recommended for Ansible)
   - **Expiration**: Set appropriate expiry
   - **Pre-authorized**: Yes (skip manual approval)
   - **Tags**: Optional, for ACL policies
4. Copy the generated key

### 2. Store Auth Key in Infisical

Create secret in Infisical:
- **Path**: `/infrastructure/vpn/tailscale`
- **Key**: `TAILSCALE_AUTH_KEY`
- **Value**: Your auth key from step 1

### 3. Deploy Tailscale

```bash
ansible-playbook -i inventories/prod/hosts.yml playbooks/deploy-tailscale.yml
```

### 4. Approve Subnet Routes

After deployment:
1. Go to [Tailscale Machines](https://login.tailscale.com/admin/machines)
2. Find your node (e.g., `hermes-prod`)
3. Click the "..." menu → "Edit route settings"
4. Enable the advertised subnets

### 5. Connect Client Devices

1. Install Tailscale on your devices: https://tailscale.com/download
2. Sign in with the same Tailscale account
3. Access internal services via their internal IPs

## Post-Deployment Access

After deployment and route approval:

```bash
# SSH directly to internal VMs (from any Tailscale-connected device)
ssh root@192.168.10.100  # orion-prod
ssh root@192.168.20.100  # orion-dev

# Or use Tailscale IPs
ssh root@100.x.x.x       # hermes-prod Tailscale IP

# Access web services
http://192.168.10.100:5678  # n8n
http://192.168.68.11:8080    # Pi-hole
```

## Troubleshooting

### Check Tailscale Status

```bash
# On the router VM
tailscale status
tailscale ip
tailscale netcheck
```

### View Tailscale Logs

```bash
journalctl -u tailscaled -f
```

### Force Re-authentication

```bash
ansible-playbook -i inventories/prod/hosts.yml playbooks/deploy-tailscale.yml \
  -e tailscale_force_reauth=true
```

### Manual Tailscale Commands

```bash
# Bring up Tailscale
tailscale up --authkey=tskey-xxx --hostname=hermes-prod --advertise-routes=192.168.10.0/24

# Update settings
tailscale set --advertise-routes=192.168.10.0/24,192.168.68.0/24

# Logout
tailscale logout
```

## Security Considerations

1. **Auth Key Security**: Store auth keys securely in Infisical, not in plain text
2. **Subnet Routes**: Only advertise necessary subnets
3. **ACL Policies**: Use Tailscale ACLs to restrict access between nodes
4. **Exit Node**: Be cautious enabling exit node - routes all traffic
5. **DNS**: Consider keeping `accept_dns: false` to use local Pi-hole

## Files Created

```
playbooks/roles/tailscale/
├── defaults/main.yml      # Default variables
├── handlers/main.yml      # Service handlers
├── tasks/
│   ├── main.yml          # Entry point
│   ├── install.yml       # Installation tasks
│   ├── configure.yml     # Configuration tasks
│   └── firewall.yml      # Firewall rules
└── README.md             # This file
```

## License

MIT
