# WireGuard Tunnel Role

This role deploys and configures WireGuard for creating secure tunnels between a VPS (server) and homelab routers (clients), enabling incoming traffic to bypass home network port forwarding.

## Architecture

```
Internet → Pharos (VPS) → WireGuard Tunnel → Hermes (Router) → Internal Services
                ↓                                    ↓
         Public IP:80/443                    192.168.x.x (VLANs)
```

### Components

1. **Server Mode (pharos-dev/pharos-prod)**
   - VPS with public IP address
   - Accepts incoming WireGuard connections from homelab
   - Forwards traffic through the tunnel to internal services
   - Runs Traefik for HTTPS termination

2. **Client Mode (hermes-dev/hermes-prod)**
   - Homelab router with access to internal VLANs
   - Initiates persistent WireGuard connection to VPS
   - Receives traffic from VPS and routes to internal services
   - No port forwarding required on home network

## Variables

### Common Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `wireguard_enabled` | `false` | Enable/disable WireGuard |
| `wireguard_mode` | `client` | Mode: `server` or `client` |
| `wireguard_interface` | `wg0` | WireGuard interface name |
| `wireguard_port` | `51820` | WireGuard UDP port |
| `wireguard_network` | `10.200.200.0/24` | VPN network CIDR |

### Server-Specific Variables (pharos)

| Variable | Default | Description |
|----------|---------|-------------|
| `wireguard_server_address` | `10.200.200.1/24` | Server's WireGuard IP |
| `wireguard_server_private_key` | `` | Server private key (from Infisical) |
| `wireguard_clients` | `[]` | List of client peers |

### Client-Specific Variables (hermes)

| Variable | Default | Description |
|----------|---------|-------------|
| `wireguard_client_address` | `10.200.200.2/24` | Client's WireGuard IP |
| `wireguard_client_private_key` | `` | Client private key (from Infisical) |
| `wireguard_server_public_key` | `` | Server's public key |
| `wireguard_server_endpoint` | `` | Server's public IP:port |
| `wireguard_persistent_keepalive` | `25` | Keepalive interval (seconds) |

### Infisical Integration

| Variable | Default | Description |
|----------|---------|-------------|
| `wireguard_use_infisical` | `true` | Fetch keys from Infisical |
| `wireguard_infisical_path` | `/infrastructure/vpn/wireguard` | Infisical secret path |

## Key Management

WireGuard keys should be stored in Infisical:

```
/infrastructure/vpn/wireguard/
├── WG_SERVER_PRIVATE_KEY      # pharos server private key
├── WG_SERVER_PUBLIC_KEY       # pharos server public key
├── WG_DEV_CLIENT_PRIVATE_KEY  # hermes-dev private key
├── WG_DEV_CLIENT_PUBLIC_KEY   # hermes-dev public key
├── WG_PROD_CLIENT_PRIVATE_KEY # hermes-prod private key
└── WG_PROD_CLIENT_PUBLIC_KEY  # hermes-prod public key
```

### Generate Keys Manually

```bash
# Generate server keys
wg genkey | tee server_private.key | wg pubkey > server_public.key

# Generate client keys (dev)
wg genkey | tee dev_client_private.key | wg pubkey > dev_client_public.key

# Generate client keys (prod)
wg genkey | tee prod_client_private.key | wg pubkey > prod_client_public.key
```

## Usage

### Deploy to Pharos (VPS Server)

```bash
ansible-playbook -i inventories/prod/hosts.yml playbooks/deploy-wireguard.yml --limit pharos-prod
```

### Deploy to Hermes (Homelab Router)

```bash
ansible-playbook -i inventories/prod/hosts.yml playbooks/deploy-wireguard.yml --limit hermes-prod
```

### Deploy All WireGuard Hosts

```bash
ansible-playbook -i inventories/prod/hosts.yml playbooks/deploy-wireguard.yml
```

## Port Forwarding Configuration

The WireGuard tunnel enables forwarding specific ports from the VPS to internal services:

```yaml
wireguard_port_forwards:
  - name: "HTTP to Traefik"
    external_port: 80
    internal_ip: "192.168.10.1"  # hermes internal IP
    internal_port: 80
    protocol: tcp
  - name: "HTTPS to Traefik"
    external_port: 443
    internal_ip: "192.168.10.1"
    internal_port: 443
    protocol: tcp
```

## Troubleshooting

### Check WireGuard Status

```bash
# On server or client
sudo wg show

# Check interface
ip addr show wg0

# Check routing
ip route | grep wg0
```

### Test Connectivity

```bash
# From pharos (server), ping hermes through tunnel
ping 10.200.200.2

# From hermes (client), ping pharos through tunnel
ping 10.200.200.1
```

### View Logs

```bash
# WireGuard kernel module logs
dmesg | grep wireguard

# Connection issues
journalctl -u wg-quick@wg0
```

## Security Considerations

1. **Key Security**: Private keys are stored in Infisical, never in git
2. **Firewall Rules**: Only required ports are opened
3. **Network Isolation**: Tunnel traffic is separate from regular VPS traffic
4. **Persistent Keepalive**: Ensures NAT traversal for homelab behind CGNAT/firewall
