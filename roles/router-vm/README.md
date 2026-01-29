# Router VM Role

This Ansible role configures Debian 13 VMs as routers/gateways for your homelab network. The role handles IP forwarding, NAT, firewall configuration, DHCP, and DNS forwarding.

## Features

- **IP Forwarding**: Enable IPv4/IPv6 packet forwarding between network interfaces
- **Multiple Network Interfaces**: Configure additional interfaces for VLAN routing
- **NAT Configuration**: Optional NAT/masquerading for WAN connectivity
- **Firewall Management**: iptables-based firewall with configurable rules
- **DHCP Server**: Optional DHCP service for network segments
- **DNS Forwarding**: Optional DNS caching/forwarding with dnsmasq
- **Static Routes**: Configure custom routing tables
- **Cloud-init Based**: Uses Debian 13 cloud-init templates for rapid deployment

## Requirements

- Proxmox VE host with cloud-init enabled templates
- Debian 13 cloud-init template (created by `proxmox-cloud-init-template` role)
- Ansible 2.9+
- Required Ansible collections:
  - `community.general`
  - `ansible.posix`

## Role Variables

### VM Configuration (inherited from proxmox-vm role)

```yaml
vm_name: "{{ inventory_hostname }}"
vm_template_name: "debian-13-generic-dev"  # Cloud-init template to clone
vm_cpu_cores: 2
vm_memory_mb: 2048
vm_disk_gb: 20
vm_ip: null  # Primary management IP

# Network settings
vm_bridge: vmbr0
vm_vlan: null  # Management VLAN
vm_net_prefix: 24
vm_net_gateway: 192.168.2.1

# Proxmox settings
proxmox_node: proxmoxve
proxmox_storage: local-lvm
```

### Router-Specific Configuration

```yaml
# IP Forwarding
router_enable_ip_forwarding: true

# NAT Configuration
router_enable_nat: false
router_nat_interface: eth0  # WAN interface for NAT

# Firewall
router_enable_firewall: true
router_firewall_default_policy: DROP
router_allowed_services:
  - ssh
  - dhcp
  - dns

# Additional Network Interfaces
router_interfaces:
  - name: eth1
    bridge: vmbr0
    vlan: 10
    ip: 192.168.10.1
    netmask: 255.255.255.0
  - name: eth2
    bridge: vmbr0
    vlan: 20
    ip: 192.168.20.1
    netmask: 255.255.255.0

# DHCP Server
router_enable_dhcp: false
router_dhcp_interfaces:
  - interface: eth1
    range_start: 192.168.10.100
    range_end: 192.168.10.200
    subnet: 192.168.10.0
    netmask: 255.255.255.0
    gateway: 192.168.10.1
    dns_servers:
      - 8.8.8.8
      - 1.1.1.1

# DNS Forwarding
router_enable_dns_forwarding: false
router_dns_upstream:
  - 8.8.8.8
  - 1.1.1.1
router_dns_listen_interfaces:
  - eth1
  - eth2

# DNS records are now defined in environment-specific group_vars
# See: inventories/{env}/group_vars/all.yml
# Example DNS records structure:
# dns_records:
#   - hostname: "orion-dev"           # Short hostname (creates both orion-dev and orion-dev.thebozic.com)
#     ip: "192.168.20.100"
#     description: "Dev Docker host"
#   - hostname: "service.dev.thebozic.com"  # FQDN (creates only FQDN entry)
#     ip: "192.168.20.100"
#     description: "Dev service"
#   - hostname: "*.apps.thebozic.com"       # Wildcard (creates catch-all entry)
#     ip: "192.168.20.100"
#     description: "Wildcard apps domain"

# Static Routes
router_static_routes:
  - network: 10.0.0.0/8
    gateway: 192.168.2.1
    interface: eth0
```

## Usage

### 1. Add Router Hosts to Inventory

Add router VMs to your inventory files (`inventories/dev/hosts.yml` or `inventories/prod/hosts.yml`):

```yaml
routers:
  vars:
    vm_template_name: debian-13-generic-dev
  hosts:
    router-dev:
      ansible_user: ansible
      ansible_host: 192.168.2.10
      env: dev
      vm_ip: 192.168.2.10
      vm_vlan: 2
      router_enable_ip_forwarding: true
      router_interfaces:
        - name: eth1
          bridge: vmbr0
          vlan: 10
          ip: 192.168.10.1
          netmask: 255.255.255.0
```

### 2. Create a Playbook

Create a playbook to provision and configure routers:

```yaml
---
- name: Provision Router VMs
  hosts: proxmox
  gather_facts: no
  tasks:
    - name: Create router VMs from template
      include_role:
        name: proxmox-vm
      vars:
        vm_name: "{{ item }}"
      loop: "{{ groups['routers'] }}"

- name: Configure Router VMs
  hosts: routers
  become: yes
  roles:
    - router-vm
```

### 3. Run the Playbook

```bash
ansible-playbook -i inventories/dev/hosts.yml playbooks/provision-routers.yml
```

## Network Architecture Example

This role is designed to work with a VLAN-based network architecture:

```
                    ┌─────────────────┐
                    │  Proxmox Host   │
                    │    (vmbr0)      │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
       VLAN 2           VLAN 10          VLAN 20
    (Management)      (Production)        (Dev)
    192.168.2.0/24   192.168.10.0/24   192.168.20.0/24
            │                │                │
            │                │                │
      ┌─────┴─────┐    ┌────┴────┐     ┌────┴────┐
      │  router-  │    │  prod   │     │   dev   │
      │    dev    │    │  hosts  │     │  hosts  │
      │  eth0: .10│    │         │     │         │
      │  eth1: .1 ├────┤         │     │         │
      │  eth2: .1 ├────┼─────────┼─────┤         │
      └───────────┘    └─────────┘     └─────────┘
```

## Common Scenarios

### Scenario 1: Simple Inter-VLAN Router

Route traffic between production and development VLANs:

```yaml
router-dev:
  router_enable_ip_forwarding: true
  router_enable_nat: false
  router_interfaces:
    - name: eth1
      vlan: 10
      ip: 192.168.10.1
      netmask: 255.255.255.0
    - name: eth2
      vlan: 20
      ip: 192.168.20.1
      netmask: 255.255.255.0
```

### Scenario 2: Router with DHCP

Provide DHCP services to network segments:

```yaml
router-dev:
  router_enable_dhcp: true
  router_dhcp_interfaces:
    - interface: eth1
      range_start: 192.168.10.100
      range_end: 192.168.10.200
      subnet: 192.168.10.0
      netmask: 255.255.255.0
      gateway: 192.168.10.1
```

### Scenario 3: Router with NAT (WAN Gateway)

Provide internet access with NAT:

```yaml
router-dev:
  router_enable_nat: true
  router_nat_interface: eth0  # WAN interface
  router_interfaces:
    - name: eth1
      ip: 192.168.10.1
      netmask: 255.255.255.0
```

### Scenario 4: Router with DNS Forwarding

Provide local DNS caching and resolution:

```yaml
router-dev:
  router_enable_dns_forwarding: true
  router_dns_upstream:
    - 8.8.8.8
    - 1.1.1.1
  router_dns_listen_interfaces:
    - eth1
    - eth2
  base_domain: thebozic.com  # Base domain for short hostname expansion
  # DNS records are now managed centrally in inventories/{env}/group_vars/all.yml
  # The role automatically reads from the 'dns_records' variable
```

**DNS Record Behavior**:
- **Short hostnames** (no dots): Creates both short name and FQDN entries
  - `orion-dev` → Creates `address=/orion-dev/IP` AND `address=/orion-dev.thebozic.com/IP`
- **FQDNs** (with dots): Creates only the specified entry
  - `traefik.dev.thebozic.com` → Creates `address=/traefik.dev.thebozic.com/IP`
- **Wildcards** (with asterisk): Creates catch-all entries
  - `*.apps.thebozic.com` → Creates `address=/apps.thebozic.com/IP`

### Managing DNS Records

DNS records are now managed centrally in environment-specific files:
- Development: `inventories/dev/group_vars/all.yml`
- Production: `inventories/prod/group_vars/all.yml`

Example DNS records file structure:
```yaml
---
# Development Environment DNS Records
dns_records:
  - hostname: "hermes-dev"
    ip: "192.168.2.10"
    description: "Dev environment router and DNS server"
  
  - hostname: "orion-dev"
    ip: "192.168.20.100"
    description: "Dev environment Docker host"
  
  - hostname: "traefik.dev.thebozic.com"
    ip: "192.168.20.100"
    description: "Traefik reverse proxy dashboard"
```

**Benefits of centralized DNS management**:
- Single source of truth for all environment DNS records
- Easier to maintain and update records across multiple routers
- Clear separation between dev and prod environments
- Better documentation with description fields
- Simplified troubleshooting and auditing

## Security Considerations

1. **Firewall Rules**: Default policy is DROP. Only explicitly allowed services are accessible.
2. **SSH Access**: SSH is allowed by default. Consider restricting to management VLAN only.
3. **Service Hardening**: DHCP and DNS services should only listen on internal interfaces.
4. **Regular Updates**: Keep the router VM updated with security patches.

## Troubleshooting

### Check IP Forwarding

```bash
sysctl net.ipv4.ip_forward
# Should return: net.ipv4.ip_forward = 1
```

### Check Network Interfaces

```bash
ip addr show
ip link show
```

### Check Routing Table

```bash
ip route show
```

### Check Firewall Rules

```bash
iptables -L -v -n
iptables -t nat -L -v -n
```

### Check DHCP Status

```bash
systemctl status isc-dhcp-server
journalctl -u isc-dhcp-server -f
```

### Check DNS Forwarding

```bash
systemctl status dnsmasq
journalctl -u dnsmasq -f
```

### Test Connectivity

```bash
# From router VM
ping -c 4 192.168.10.100  # Test VLAN 10
ping -c 4 192.168.20.100  # Test VLAN 20

# From client VM in VLAN 10
ping -c 4 192.168.10.1    # Test gateway
ping -c 4 192.168.20.100  # Test routing to VLAN 20
```

## Integration with Existing Roles

This role works alongside:

- **proxmox-vm**: Creates the VM from cloud-init template
- **proxmox-cloud-init-template**: Creates the base Debian 13 template
- **docker-host**: Can be used on the same VM if needed

## Dependencies

This role depends on the `proxmox-vm` role to provision the VM before configuring it as a router.

## License

MIT

## Author

Created for the Homelab automation project.
