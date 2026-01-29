# Cloudflare DNS Role - Infisical Integration

## Overview

The `dns-cloudflare` role manages DNS records in Cloudflare. It has been updated to retrieve the Cloudflare API token securely from Infisical instead of environment variables.

## Infisical Configuration

### Required Secret

The role expects the following secret in Infisical:

**Path**: `/infrastructure/dns/cloudflare`  
**Environment**: `prod` (default, configurable)  
**Secret Name**: `CLOUDFLARE_API_TOKEN`  
**Secret Value**: Your Cloudflare API token with DNS edit permissions

### Creating the Secret in Infisical

1. **Via Infisical CLI:**
   ```bash
   infisical secrets set CLOUDFLARE_API_TOKEN="your_cloudflare_api_token_here" \
     --path="/infrastructure/dns/cloudflare" \
     --env=prod
   ```

2. **Via Infisical Web UI:**
   - Navigate to your project
   - Go to environment: `prod`
   - Navigate to path: `/infrastructure/dns/cloudflare`
   - Create secret: `CLOUDFLARE_API_TOKEN`
   - Set value: Your Cloudflare API token

### Getting a Cloudflare API Token

1. Log in to Cloudflare Dashboard
2. Go to: Profile → API Tokens
3. Click "Create Token"
4. Use template: "Edit zone DNS" or create custom with:
   - Permissions: `Zone → DNS → Edit`
   - Zone Resources: `Include → Specific zone → thebozic.com`
5. Copy the token and store it in Infisical

## Role Variables

### Infisical Settings

```yaml
# Path in Infisical where the Cloudflare token is stored
cloudflare_infisical_path: "/infrastructure/dns/cloudflare"

# Infisical environment (prod/dev)
cloudflare_infisical_env: "prod"
```

### DNS Configuration

```yaml
# Domain/zone to manage
cloudflare_zone: "thebozic.com"

# Auto-generate DNS records from inventory
auto_generate_dns_records: true

# DNS record TTL (1 = auto, 300-86400 = seconds)
dns_ttl: 300

# Cloudflare proxy (orange cloud)
dns_proxied: false

# Public IP for external DNS records
public_ip: "{{ lookup('env', 'PUBLIC_IP') | default('', true) }}"
```

### Manual DNS Records

If you don't want auto-generated records, you can define them manually:

```yaml
dns_records:
  - name: "*.dev.thebozic.com"
    type: "A"
    content: "192.168.20.100"
    proxied: false
    ttl: 300
  - name: "*.prod.thebozic.com"
    type: "A"
    content: "YOUR_PUBLIC_IP"
    proxied: true
    ttl: 1
```

## Usage

### In a Playbook

```yaml
- name: Configure DNS Records
  hosts: localhost
  connection: local
  gather_facts: false
  
  roles:
    - role: dns-cloudflare
```

### Running the Playbook

The playbook is already integrated into `configure-network.yml`:

```bash
cd /home/luckyprayer/Homelab
./scripts/run-playbook.sh --env=dev
# Select: 1) Configure network infrastructure
```

**Important**: Ensure your Infisical token is set:
```bash
export INFISICAL_TOKEN="your_token_here"
export INFISICAL_PROJECT_ID="your_project_id_here"
```

Or the script will prompt you for them.

## Auto-Generated DNS Records

By default, the role automatically generates DNS records based on your inventory:

### Development Environment

- **Record**: `*.dev.thebozic.com`
- **Type**: A
- **Content**: IP of first dev docker host (e.g., `orion-dev`)
- **Example**: `traefik.dev.thebozic.com` → `192.168.20.100`

### Production Environment (Internal)

- **Record**: `*.prod.thebozic.com`
- **Type**: A
- **Content**: IP of first prod docker host (e.g., `orion-prod`)
- **Example**: `n8n.prod.thebozic.com` → `192.168.10.100`

### Production Environment (External)

If `public_ip` is set:
- **Record**: `*.prod.thebozic.com`
- **Type**: A
- **Content**: Your public IP
- **Proxied**: Based on `dns_proxied` setting
- **Example**: `mealie.prod.thebozic.com` → Your public IP

## Security Considerations

### Why Infisical?

1. **No plaintext secrets**: API tokens are never stored in playbooks or environment variables
2. **Centralized management**: All secrets in one secure location
3. **Audit trail**: Infisical logs all secret access
4. **Rotation**: Easy to rotate tokens without changing playbooks
5. **Access control**: Fine-grained permissions on who can access secrets

### Secret Hiding

The role uses `no_log: true` on tasks that handle the API token to prevent it from appearing in Ansible output.

## Troubleshooting

### Error: "Cloudflare API token not retrieved from Infisical"

**Causes:**
1. Secret doesn't exist in Infisical
2. Wrong path or environment
3. Infisical token not set or expired

**Solution:**
```bash
# Check if secret exists
infisical secrets get CLOUDFLARE_API_TOKEN \
  --path="/infrastructure/dns/cloudflare" \
  --env=prod

# If not found, create it
infisical secrets set CLOUDFLARE_API_TOKEN="your_token" \
  --path="/infrastructure/dns/cloudflare" \
  --env=prod
```

### Error: "Failed to authenticate with Cloudflare"

**Causes:**
1. Invalid API token
2. Token doesn't have DNS edit permissions
3. Token is for wrong zone

**Solution:**
1. Verify token in Cloudflare Dashboard
2. Check token permissions include `Zone → DNS → Edit`
3. Ensure token is scoped to correct zone (`thebozic.com`)

### DNS Records Not Created

**Causes:**
1. `auto_generate_dns_records: false`
2. No hosts found in inventory matching pattern
3. Cloudflare zone doesn't exist

**Solution:**
1. Check `auto_generate_dns_records` is `true`
2. Verify inventory has hosts with `-dev` or `-prod` suffix
3. Ensure zone `thebozic.com` exists in Cloudflare

## Examples

### Custom DNS Records

Override auto-generation with custom records:

```yaml
- name: Configure custom DNS records
  hosts: localhost
  roles:
    - role: dns-cloudflare
      vars:
        auto_generate_dns_records: false
        dns_records:
          - name: "api.thebozic.com"
            type: "A"
            content: "192.168.10.50"
            proxied: false
            ttl: 300
          - name: "www.thebozic.com"
            type: "CNAME"
            content: "thebozic.com"
            proxied: true
            ttl: 1
```

### Different Infisical Path

Use a different Infisical path for dev environment:

```yaml
- name: Configure DNS with dev token
  hosts: localhost
  roles:
    - role: dns-cloudflare
      vars:
        cloudflare_infisical_path: "/infrastructure/dns/cloudflare-dev"
        cloudflare_infisical_env: "dev"
```

## Migration from Environment Variables

If you were previously using environment variables:

**Old method:**
```bash
export CLOUDFLARE_API_TOKEN="your_token"
ansible-playbook playbooks/configure-network.yml
```

**New method:**
```bash
# Store in Infisical once
infisical secrets set CLOUDFLARE_API_TOKEN="your_token" \
  --path="/infrastructure/dns/cloudflare" \
  --env=prod

# Run playbook (token retrieved automatically)
./scripts/run-playbook.sh --env=dev
```

## Related Documentation

- [Infisical Setup Guide](QUICK_INFISICAL_SETUP.md)
- [Network Architecture](NETWORK_ARCHITECTURE.md)
- [Automated Network Setup](AUTOMATED_NETWORK_SETUP.md)
