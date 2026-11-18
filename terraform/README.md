# Terraform deployment (single Azure VM — backend only)

Deploys the voice-chat **backend** to a single Ubuntu VM on Azure, pulled from
[GHCR](https://github.com/trungaero/fcm-robot-light/pkgs/container/fcm-robot-light).
The **frontend runs locally** on the developer's machine (see the root
[README](../README.md)).

## What this creates

- **Backend** (`network_mode: host`) — FastAPI/aiortc binds the VM NIC directly
  so STUN discovers the public IP and WebRTC media (SRTP/UDP) is reachable.
- **NSG** opens SSH (22), backend signaling (TCP 8000), and WebRTC media
  (UDP `webrtc_udp_port_range`).
- **cloud-init** installs Docker and writes:
  - `/opt/voice-chat/docker-compose.yml` (from [../deploy/docker-compose.yml](../deploy/docker-compose.yml))
  - `/opt/voice-chat/.env` (secrets/vars injected from `terraform.tfvars`)
  - a **systemd timer** (`voice-chat-update.timer`) that pulls the latest
    `:latest` image every 2 minutes and re-creates the container on change.
- **Terraform state** is stored **locally** by default (no backend block in
  [providers.tf](providers.tf)). For team/CI use, add an `azurerm` backend.

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/downloads) ≥ 1.5
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) and an
  Azure subscription
- An SSH key pair
- The backend image already published to GHCR (see
  `../.github/workflows/build-backend.yml` — push to `main` once first).

> If you keep the GHCR package **private**, SSH into the VM after creation and
> `docker login ghcr.io` with a `read:packages` PAT, then pull manually once.
> Easiest is to make the package **public** under *Package settings → visibility*.

## 1. Configure variables

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars: set ssh_public_key (absolute path) and openai_api_key
```

## 2. Init, plan, apply

```bash
terraform init
terraform plan
terraform apply
```

## 3. Verify

```bash
terraform output
# public_ip, backend_url, backend_ws_url, health_url, ssh_command

curl -fsS http://<public_ip>:8000/health   # {"status":"ok","api_key_configured":true}
ssh <admin>@<public_ip>                     # then: docker compose -f /opt/voice-chat/docker-compose.yml ps
```

## Auto-update

The VM's `voice-chat-update.timer` pulls `:latest` every 2 minutes. On the VM:

```bash
systemctl list-timers voice-chat-update.*
journalctl -u voice-chat-update.service
```

Adjust the interval in [templates/cloud-init.yaml.tpl](templates/cloud-init.yaml.tpl).

## Further considerations

1. **WebRTC media needs TURN for reliability.** Azure places VMs behind 1:1 NAT,
   and aiortc binds ephemeral UDP ports. STUN may work for direct (non-symmetric)
   NAT paths, but a TURN relay is strongly recommended. Set `webrtc_turn_url` /
   `webrtc_turn_username` / `webrtc_turn_credential` (e.g. coturn on this VM, or a
   managed provider like Metered/Twilio). The `WebRTC-UDP` NSG rule
   (`webrtc_udp_port_range`, default `32768-65535`) opens the full ephemeral range
   so aiortc's sockets are reachable, but it cannot solve NAT traversal by itself
   when the client is behind symmetric/CGNAT.
2. **HTTPS is not required** while the frontend runs on `localhost`; the Vite
   dev server proxies signaling to the VM. TLS is only needed if you later serve
   the frontend remotely.
3. **Secrets.** The API key is written to the VM's `/opt/voice-chat/.env`. For
   stricter handling, store it in Azure Key Vault and read it via a managed
   identity at boot.

## Teardown

```bash
terraform destroy
```
