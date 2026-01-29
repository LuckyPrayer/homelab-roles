# Proxmox VM Role

This Ansible role provisions Virtual Machines on Proxmox from cloud-init templates. It retrieves cloud-init credentials securely from Infisical.

## Features

- **Cloud-Init Integration**: Clones VMs from pre-built cloud-init templates
- **Secure Credential Management**: Retrieves user credentials, passwords, and SSH keys from Infisical
- **Flexible Configuration**: Supports custom CPU, memory, disk, and network settings
- **Environment-Aware**: Uses environment-specific credentials (dev/prod)
- **Automatic Provisioning**: Configures static IPs, starts VMs, and waits for SSH availability

## Requirements

- Proxmox VE server with API access
- Infisical CLI installed on the control node
- Cloud-init templates created (use `proxmox-cloud-init-template` role)
- Python libraries: `proxmoxer`, `requests`
- Ansible collection: `community.general`

## Infisical Secrets

This role requires the following secrets in Infisical:

### Path: `/users/ansible/proxmox` (env=prod)
- `PROXMOX_TOKEN_ID`: Proxmox API token ID
- `PROXMOX_TOKEN_SECRET`: Proxmox API token secret

### Path: `/infrastructure/vms/<vm-base-name>` (env=dev or prod)

Each VM requires its own set of credentials at a VM-specific path. The `<vm-base-name>` is the VM name without the environment suffix.

**Examples:**
- VM `orion-dev` uses path `/infrastructure/vms/orion` in the `dev` environment
- VM `orion-prod` uses path `/infrastructure/vms/orion` in the `prod` environment
- VM `docker-host-01-dev` uses path `/infrastructure/vms/docker-host-01` in the `dev` environment

**Required secrets per VM:**
- `VM_CI_USER`: Username for the cloud-init user
- `VM_CI_PASSWORD`: Password for the cloud-init user
- `VM_CI_SSH_KEY`: SSH public key for authentication

For setup instructions, see: [INFISICAL_CLOUD_INIT_SETUP.md](../../../docs/INFISICAL_CLOUD_INIT_SETUP.md)

## Role Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `vm_name` | Name of the VM to create | `docker-host-01` |
| `proxmox_node` | Proxmox node name | `proxmoxve` |
| `ansible_host` | Proxmox host IP/hostname | `192.168.20.10` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `vm_ip` | `null` | Static IP address for the VM |
| `vm_template_name` | `debian-13-generic-dev` | Template to clone from |
| `vm_cpu_cores` | `2` | Number of CPU cores |
| `vm_memory_mb` | `4096` | Memory in MB |
| `vm_disk_gb` | `40` | Disk size in GB |
| `vm_override_disk` | `true` | Whether to resize disk |
| `vm_bridge` | `vmbr0` | Network bridge |
| `vm_vlan` | `null` | VLAN tag (optional) |
| `vm_net_prefix` | `24` | Network prefix length |
| `vm_net_gateway` | `192.168.20.1` | Default gateway |
| `proxmox_storage` | `local-lvm` | Storage for VM disk |
| `env` | `dev` | Environment (dev/prod) |

## Dependencies

- Role: `proxmox-cloud-init-template` (for creating templates)
- Collection: `community.general`

## Example Playbook

### Simple VM Provisioning

```yaml
---
- name: Provision Docker Host VM
  hosts: gaia
  connection: local
  gather_facts: false
  roles:
    - role: proxmox-vm
      vars:
        vm_name: docker-host-01
        vm_ip: 192.168.20.101
        vm_cpu_cores: 4
        vm_memory_mb: 8192
        vm_disk_gb: 100
        env: dev
```

### Multiple VMs with Loop

```yaml
---
- name: Provision Multiple VMs
  hosts: gaia
  connection: local
  gather_facts: false
  tasks:
    - name: Provision each VM
      ansible.builtin.include_role:
        name: proxmox-vm
      vars:
        vm_name: "{{ item.name }}"
        vm_ip: "{{ item.ip }}"
        vm_cpu_cores: "{{ item.cores | default(2) }}"
        vm_memory_mb: "{{ item.memory | default(4096) }}"
        env: "{{ item.env | default('dev') }}"
      loop:
        - name: docker-host-01
          ip: 192.168.20.101
          cores: 4
          memory: 8192
          env: dev
        - name: docker-host-02
          ip: 192.168.20.102
          cores: 2
          memory: 4096
          env: dev
```

### Using Inventory Variables

```yaml
---
# In inventory (inventories/dev/hosts.yml)
all:
  children:
    proxmox:
      hosts:
        gaia:
          ansible_host: 192.168.20.10
    docker_hosts:
      hosts:
        docker-host-01:
          ansible_host: 192.168.20.101
          vm_ip: 192.168.20.101
          vm_cpu_cores: 4
          vm_memory_mb: 8192
          vm_disk_gb: 100
          env: dev

# In playbook
- name: Provision VMs from Inventory
  hosts: gaia
  connection: local
  gather_facts: false
  tasks:
    - name: Provision each Docker host
      ansible.builtin.include_role:
        name: proxmox-vm
      vars:
        vm_name: "{{ item }}"
        vm_ip: "{{ hostvars[item].vm_ip }}"
        vm_cpu_cores: "{{ hostvars[item].vm_cpu_cores | default(2) }}"
        vm_memory_mb: "{{ hostvars[item].vm_memory_mb | default(4096) }}"
        env: "{{ hostvars[item].env }}"
      loop: "{{ groups['docker_hosts'] }}"
```

## What the Role Does

1. **Retrieve Credentials**: Fetches Proxmox API tokens and cloud-init credentials from Infisical
2. **Install Dependencies**: Ensures `proxmoxer` library is installed
3. **Clone Template**: Creates a full clone of the specified cloud-init template
4. **Configure Resources**: Sets CPU cores and memory
5. **Resize Disk**: Expands the disk to the specified size (if enabled)
6. **Configure Cloud-Init**: Sets username, password, and SSH keys
7. **Configure Network**: Assigns static IP if specified
8. **Start VM**: Powers on the VM
9. **Wait for SSH**: Waits for the VM to become accessible via SSH
10. **Register Host**: Adds the VM to the `docker_hosts` group for subsequent plays

## VM Access

After provisioning, you can access the VM using:

### SSH (Recommended)
```bash
ssh <VM_CI_USER>@<vm_ip>
```

### Console Login
- Username: Value from `VM_CI_USER` in Infisical
- Password: Value from `VM_CI_PASSWORD` in Infisical

## Environment-Specific Behavior

The role uses the `env` variable to determine which Infisical environment to use:

- `env: dev` → Uses secrets from Infisical dev environment
- `env: prod` → Uses secrets from Infisical prod environment

This allows different credentials per environment while using the same playbook.

## Security Features

1. **No Hardcoded Credentials**: All sensitive data retrieved from Infisical
2. **Sensitive Data Protection**: Uses `no_log: true` for passwords and tokens
3. **Environment Isolation**: Separate credentials for dev and prod
4. **SSH Key Authentication**: Primary authentication method

## Troubleshooting

### VM Clone Fails

**Error**: "Template not found"

**Solution**: Ensure the template exists and name matches:
```bash
# List templates on Proxmox
qm list | grep -i template
```

### Infisical Secrets Not Found

**Error**: "failed_when: infisical_vm_ci_user.stdout == ''"

**Solution**: Verify secrets exist in Infisical for the specific VM:
```bash
# For VM "orion-dev", check secrets at path /infrastructure/vms/orion in dev environment
infisical secrets get VM_CI_USER --path="/infrastructure/vms/orion" --env=dev
infisical secrets get VM_CI_PASSWORD --path="/infrastructure/vms/orion" --env=dev
infisical secrets get VM_CI_SSH_KEY --path="/infrastructure/vms/orion" --env=dev

# For VM "docker-host-01-prod", check secrets at path /infrastructure/vms/docker-host-01 in prod environment
infisical secrets get VM_CI_USER --path="/infrastructure/vms/docker-host-01" --env=prod
infisical secrets get VM_CI_PASSWORD --path="/infrastructure/vms/docker-host-01" --env=prod
infisical secrets get VM_CI_SSH_KEY --path="/infrastructure/vms/docker-host-01" --env=prod
```

**Create missing secrets**:
```bash
# Example for VM "orion" in dev environment
infisical secrets set VM_CI_USER="ansible" --path="/infrastructure/vms/orion" --env=dev
infisical secrets set VM_CI_PASSWORD="$(openssl rand -base64 32)" --path="/infrastructure/vms/orion" --env=dev
infisical secrets set VM_CI_SSH_KEY="$(cat ~/.ssh/id_rsa.pub)" --path="/infrastructure/vms/orion" --env=dev
```

See [INFISICAL_CLOUD_INIT_SETUP.md](../../../docs/INFISICAL_CLOUD_INIT_SETUP.md) for setup instructions.

### SSH Connection Timeout

**Symptoms**: "Timeout waiting for SSH"

**Possible Causes**:
1. Network configuration incorrect (gateway, IP address)
2. VM didn't boot properly
3. Cloud-init failed to configure SSH
4. Firewall blocking port 22

**Debug Steps**:
```bash
# Check VM is running in Proxmox
qm status <vmid>

# Check console output
qm terminal <vmid>

# Verify network config
# (In VM console)
ip addr show
ip route show
```

### Disk Resize Fails

**Error**: "Disk resize failed"

**Solution**: 
- Ensure disk size is larger than template disk
- Check storage has enough space
- Verify VM is stopped (or use online resize if supported)

## Advanced Usage

### Custom Network Configuration

```yaml
- role: proxmox-vm
  vars:
    vm_name: custom-network-vm
    vm_ip: 10.0.1.100
    vm_net_prefix: 16
    vm_net_gateway: 10.0.0.1
    vm_bridge: vmbr1
    vm_vlan: 10
```

### Using Different Template

```yaml
- role: proxmox-vm
  vars:
    vm_name: ubuntu-vm
    vm_template_name: ubuntu-22.04-cloud-init
```

### Skip Disk Resize

```yaml
- role: proxmox-vm
  vars:
    vm_name: small-vm
    vm_override_disk: false
```

## Integration with Other Roles

This role is designed to work with:

1. **proxmox-cloud-init-template**: Creates the base templates
2. **docker-host**: Configures Docker on provisioned VMs
3. **homelab-compose**: Deploys Docker Compose applications

Example workflow:
```yaml
---
# 1. Create templates
- import_playbook: create-templates.yml

# 2. Provision VMs
- import_playbook: provision.yml

# 3. Configure Docker
- name: Configure Docker hosts
  hosts: docker_hosts
  roles:
    - docker-host
    - homelab-compose
```

## Files

```
playbooks/roles/proxmox-vm/
├── defaults/
│   └── main.yml          # Default variables
├── tasks/
│   └── main.yml          # Main tasks
└── README.md             # This file
```

## License

MIT

## Author

Homelab Infrastructure Team

## See Also

- [Cloud-Init Templates Guide](../../../docs/CLOUD_INIT_TEMPLATES.md)
- [Infisical Setup Guide](../../../docs/INFISICAL_CLOUD_INIT_SETUP.md)
- [Proxmox VM Provisioning Playbook](../../provision.yml)
