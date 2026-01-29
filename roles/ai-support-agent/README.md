# Oracle AI Support Agent Role

Oracle is the homelab's AI support agent, powered by Claude Code CLI. Named after the Oracle of Delphi, Oracle provides all-knowing support for your infrastructure.

## Features

- **Claude Code CLI Integration**: Uses Claude's agentic capabilities to search code, run commands, and analyze issues
- **Codebase Awareness**: Mounts the homelab repository so Claude can search documentation and configuration
- **SSH Remote Access**: Oracle user with SSH keys for accessing all homelab hosts
- **Environment-Based Permissions**: 
  - **Dev**: Full Write/Edit access to codebase (can create and modify files)
  - **Prod/Staging**: Read-only access (safe mode)
- **Auto-Provisioned Channel**: Automatically creates a `#oracle-{env}` channel for conversations
- **Conversational Interface**: Chat directly with Oracle in the agent channel
- **Incident Tracking**: Creates Discord threads for each incident with full investigation history
- **Cost Tracking**: Reports API costs for transparency

## Prerequisites

1. **Discord Bot Application**
   - Create at https://discord.com/developers/applications
   - Enable "Message Content Intent" under Privileged Gateway Intents
   - Invite bot with appropriate permissions (including Manage Channels for auto-provisioning)

2. **Anthropic API Key**
   - Get from https://console.anthropic.com/
   - Required for Claude Code CLI

3. **Infisical Secrets** (at `/infrastructure/monitoring/oracle/`)
   - `DISCORD_BOT_TOKEN`: Discord bot token
   - `ANTHROPIC_API_KEY`: Anthropic API key
   - `ORACLE_SSH_PRIVATE_KEY`: SSH private key (ed25519) for remote host access

## Generating SSH Keys for Oracle

Generate a dedicated SSH keypair for Oracle:

```bash
# Generate ed25519 keypair
ssh-keygen -t ed25519 -C "oracle@homelab" -f oracle_id_ed25519 -N ""

# View the private key (add to Infisical as ORACLE_SSH_PRIVATE_KEY)
cat oracle_id_ed25519

# View the public key (add to authorized_keys on all hosts)
cat oracle_id_ed25519.pub
```

Add the **private key** to Infisical at `/infrastructure/monitoring/oracle/ORACLE_SSH_PRIVATE_KEY`.

The role will automatically:
1. Create the `oracle` user on the host running Oracle
2. Deploy the SSH key to `/home/oracle/.ssh/id_ed25519`
3. Configure SSH to use ProxyJump through hermes-dev for VLAN 20 hosts

## Setting Up Oracle User on Remote Hosts

For Oracle to SSH to other hosts, run the setup task on all docker hosts:

```yaml
- hosts: docker_hosts
  tasks:
    - name: Setup Oracle user for remote access
      ansible.builtin.include_role:
        name: ai-support-agent
        tasks_from: setup-oracle-user.yml
      vars:
        oracle_ssh_public_key: "{{ lookup('file', 'oracle_id_ed25519.pub') }}"
```

## Configuration

Add to your host inventory (argus-dev):

```yaml
# Oracle AI Support Agent Configuration
oracle_enabled: true
oracle_guild_id: "YOUR_GUILD_ID"

# Path to your homelab codebase on the host
oracle_codebase_path: "/opt/homelab"
oracle_sync_codebase: true

# Channel provisioning (auto-creates oracle channel)
oracle_auto_provision_channels: true
oracle_category_name: "Homelab AI"
oracle_channel_name: "oracle"  # Will become #oracle-dev or #oracle-prod

# Behavior settings
oracle_auto_respond: true      # Automatically respond to alerts
oracle_auto_remediate: true    # Attempt automatic fixes

# Infisical path for secrets
oracle_infisical_path: "/infrastructure/monitoring/oracle/"
```

## Discord Commands

| Command | Description |
|---------|-------------|
| `/oracle-status` | Show Oracle status, environment, and capabilities |
| `/ask-oracle <question>` | Ask Oracle about the homelab |
| `/investigate <incident_id>` | Manually trigger investigation |
| `/run-task <task>` | Run a custom task (admin only) |
| `/toggle-auto <feature>` | Toggle auto-respond/remediate (admin only) |
| `/incidents` | List active incidents |

## Conversational Mode

In the auto-provisioned `#oracle-{env}` channel, you can chat directly with Oracle:
- Just type your message - no command needed
- Oracle will search the codebase and run diagnostic commands
- In dev environment, Oracle can create/edit files when asked
- Cost is reported after each response

## Remote Diagnostics

Oracle can SSH to any homelab host to run diagnostics:

```bash
# From inside the container, Oracle can run:
ssh hephaestus-dev "docker ps"
ssh orion-dev "docker logs homelab-minecraft --tail 20"
ssh hermes-dev "systemctl status traefik"
```

The SSH config handles:
- ProxyJump through hermes-dev for VLAN 20 hosts
- Using the oracle SSH key
- Disabling host key checking for automation

## Safety Features

1. **Environment-Based Edit Tools**:
   - `dev`: Write/Edit/MultiEdit tools ENABLED (can modify codebase)
   - `prod`/`staging`: Write/Edit/MultiEdit tools DISABLED (read-only)
2. **Volume Mount Protection**: Codebase mounted as read-write only in dev
3. **Dedicated Oracle User**: Restricted user with only docker access
4. **Incident Tracking**: Full audit trail in Discord threads
5. **Cost Visibility**: API costs reported for each operation

## Deployment

```bash
# Deploy Oracle to dev
ansible-playbook playbooks/deploy-all.yml --limit argus-dev --tags ai-support-agent

# Force rebuild with latest code
ansible-playbook playbooks/deploy-all.yml --limit argus-dev --tags ai-support-agent -e "oracle_force_rebuild=true"
```

## Container Details

- **Container Name**: `homelab-oracle`
- **Image**: `homelab-oracle:latest`
- **User**: `oracle` (UID 3003)
- **Network**: `homelab`
- **Volumes**:
  - `/opt/oracle/logs` → `/app/logs`
  - `/opt/homelab` → `/app/codebase`
  - `/var/run/docker.sock` → Docker socket (read-only)
  - `/home/oracle/.ssh` → SSH credentials
  - `/opt/oracle/ssh_config` → SSH configuration
