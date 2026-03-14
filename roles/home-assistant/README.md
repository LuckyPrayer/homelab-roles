# Home Assistant OS Role

Deploys [Home Assistant OS (HAOS)](https://www.home-assistant.io/installation/alternative#install-home-assistant-operating-system) as a dedicated Proxmox VM.

## Overview

Home Assistant OS is a purpose-built operating system that includes the Home Assistant Supervisor. Unlike a Docker container deployment, HAOS provides:

- **Built-in Supervisor** — manage add-ons, updates, and snapshots from the HA UI
- **Automatic backups** — HAOS handles its own backup/restore (no external Docker backup needed)
- **Add-on ecosystem** — install community add-ons (Z-Wave JS, Zigbee2MQTT, ESPHome, etc.) directly
- **USB passthrough** — native support for Zigbee/Z-Wave dongles via Proxmox

This role runs on the Ansible controller and provisions the VM on Proxmox by:
1. Downloading the official HAOS `.qcow2` image
2. Creating a UEFI (OVMF) VM with the imported disk
3. Configuring resources (CPU, memory, disk, network)
4. Starting the VM and waiting for the web UI

## Variables

| Variable | Default | Description |
|---|---|---|
| `homeassistant_enabled` | `true` | Feature toggle |
| `haos_version` | `14.2` | HAOS release version |
| `haos_vm_id` | `""` | Proxmox VMID (auto-assigned if empty) |
| `haos_vm_machine_type` | `q35` | Proxmox machine type |
| `haos_vm_bios` | `ovmf` | UEFI boot (required for HAOS) |
| `haos_vm_cpu_type` | `host` | CPU type |
| `vm_cpu_cores` | `2` | CPU cores |
| `vm_memory_mb` | `4096` | Memory in MB |
| `vm_disk_gb` | `40` | Disk size in GB |
| `vm_bridge` | `vmbr0` | Network bridge |
| `vm_vlan` | `""` | VLAN tag |
| `vm_ip` | `""` | Static IP |
| `homeassistant_port` | `8123` | Web UI port |
| `haos_usb_devices` | `{}` | USB passthrough (e.g., `usb0: "host=1234:5678"`) |

## Usage

```bash
# Deploy to dev
ansible-playbook -i inventories/dev/hosts.yml playbooks/deploy-hera.yml --limit hera-dev

# Deploy to prod
ansible-playbook -i inventories/prod/hosts.yml playbooks/deploy-hera.yml --limit hera-prod
```

## Access

After deployment, HAOS will boot and download Home Assistant Core (~10-20 minutes on first run).

Access the web UI at: `http://<vm-ip>:8123`

You'll be guided through the onboarding wizard to create your admin account and configure integrations.

## USB Passthrough

To pass through a Zigbee/Z-Wave USB dongle, find the vendor/product ID on the Proxmox host:

```bash
lsusb
# Example: Bus 001 Device 003: ID 10c4:ea60 Silicon Labs CP210x UART Bridge
```

Then set in the inventory:

```yaml
haos_usb_devices:
  usb0: "host=10c4:ea60"
```
