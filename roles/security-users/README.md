# Security Users Role

Creates dedicated service accounts and configures sudoers for least privilege access across the homelab environment.

## Purpose

This role reduces root usage by:
- Creating dedicated service accounts for different functions
- Configuring least-privilege sudo rules
- Setting up SSH key-based authentication for Ansible
- Optionally disabling root SSH access

## Service Accounts Created

| Account | UID | Purpose | Home Directory |
|---------|-----|---------|----------------|
| `backup-svc` | 3001 | Docker backup operations | `/var/lib/backup-svc` |
| `docker-svc` | 3002 | Docker container services | `/var/lib/docker-svc` |
| `harbor-svc` | 3003 | Harbor registry services | `/var/lib/harbor-svc` |
| `ansible` | 2000 | Ansible automation (optional) | `/home/ansible` |

All service accounts are members of the `docker` group for Docker socket access.

## Variables

### Default Variables (`defaults/main.yml`)

```yaml
# Service accounts configuration
service_users:
  - name: backup-svc
    uid: 3001
    system: true
    home: /var/lib/backup-svc
    shell: /bin/bash
    groups: [docker]
    comment: "Docker Backup Service Account"

# Ansible user configuration  
create_ansible_user: true          # Set to false to skip ansible user creation
ansible_user_name: ansible
ansible_user_uid: 2000
ansible_user_groups: [docker, sudo]
ansible_user_shell: /bin/bash
ansible_user_ssh_key: ""          # Set via environment or inventory

# SSH security settings
disable_root_ssh: false            # Set to true after migrating to ansible user
ssh_password_authentication: false
ssh_permit_empty_password: false

# Sudoers configuration
configure_sudoers: true
sudoers_dir: /etc/sudoers.d
```

### Required Environment Variables

```bash
# For ansible user SSH key
export ANSIBLE_SSH_KEY="ssh-rsa AAAAB3... your-key-here"
```

## Usage

### Basic Usage

Include in your playbook:

```yaml
- hosts: docker_hosts
  roles:
    - security-users
```

### With Custom Variables

```yaml
- hosts: docker_hosts
  roles:
    - role: security-users
      vars:
        create_ansible_user: true
        disable_root_ssh: false  # Keep root SSH enabled initially
```

### Create Ansible User with SSH Key

```yaml
- hosts: docker_hosts
  roles:
    - role: security-users
      vars:
        create_ansible_user: true
        ansible_user_ssh_key: "{{ lookup('env', 'ANSIBLE_SSH_KEY') }}"
```

### Deploy Only Security Users

```bash
ansible-playbook -i inventories/dev/hosts.yml playbooks/deploy-all.yml \
  --tags security-users --limit orion-dev
```

## Sudoers Configuration

The role creates three sudoers files in `/etc/sudoers.d/`:

### 1. `ansible-user` - Ansible Automation

Grants permissions for:
- System management (systemctl)
- Package management (apt)
- Docker operations
- File operations
- Network configuration
- User management

### 2. `backup-svc` - Backup Operations

Grants permissions for:
- Restic backup tool
- Docker container stop/start
- Docker compose operations
- Limited file operations on backup directories

### 3. `docker-svc` - Docker Services

Grants permissions for:
- Docker compose operations
- Docker status/logs/inspect commands
- Service management for docker services

## Security Considerations

### Docker Group Membership

All service accounts are members of the `docker` group, which grants broad access to Docker. This is necessary for their functions but does grant significant privileges.

**Future improvement:** Implement a Docker socket proxy to restrict API access.

### Root SSH Access

By default, root SSH access remains enabled. After testing the ansible user:

1. Update inventory to use ansible user:
   ```yaml
   ansible_user: ansible
   ```

2. Set `disable_root_ssh: true` in role variables

3. Redeploy the role

### Sudo Access

Service accounts have targeted sudo permissions. Review the sudoers templates to ensure they match your security requirements.

## Dependencies

None. This role can run independently.

## Example Playbook

```yaml
---
- name: Configure security users
  hosts: all
  become: true
  
  roles:
    - role: security-users
      vars:
        create_ansible_user: true
        ansible_user_ssh_key: "{{ lookup('file', '~/.ssh/id_rsa.pub') }}"
        disable_root_ssh: false
        configure_sudoers: true
```

## Testing

### Verify Users Created

```bash
id backup-svc
id docker-svc
id harbor-svc
id ansible  # If created
```

### Test Sudo Access

```bash
# Test backup-svc
sudo -u backup-svc -l
sudo -u backup-svc restic version

# Test docker-svc
sudo -u docker-svc -l
sudo -u docker-svc docker ps

# Test ansible user
sudo -u ansible -l
```

### Verify SSH Configuration

```bash
# Check sshd config
sudo sshd -T | grep -E 'permitrootlogin|passwordauthentication'

# Test ansible user SSH
ssh ansible@hostname
```

## Handlers

- `Restart sshd`: Restarts SSH daemon when configuration changes

## Tags

- `security`
- `security-users`

## Files

```
security-users/
├── defaults/
│   └── main.yml              # Default variables
├── handlers/
│   └── main.yml              # Service handlers
├── tasks/
│   └── main.yml              # Main task file
├── templates/
│   ├── sudoers-ansible.j2    # Ansible user sudoers
│   ├── sudoers-backup-svc.j2 # Backup service sudoers
│   └── sudoers-docker-svc.j2 # Docker service sudoers
└── README.md                 # This file
```

## License

MIT

## Author

Homelab Security Improvements - December 2025
