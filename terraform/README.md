# Terraform deployment (single Azure VM — backend only)

Deploys the voice-chat **backend** to a single Ubuntu VM on Azure, pulled from
[GHCR](https://github.com/trungaero/fcm-robot-light/pkgs/container/fcm-robot-light).
The **frontend runs locally** on the developer's machine (see the root
[README](../README.md)).

## What this creates

- **Backend** (`network_mode: host`) — FastAPI/aiortc binds the VM NIC directly
  so STUN discovers the public IP and WebRTC media (SRTP/UDP) is reachable.
- **Caddy** (`network_mode: host`) — TLS-terminates the signaling path on
  `:443` (self-signed cert for the VM's public IP) and reverse-proxies to the
  backend at `127.0.0.1:8000`.
- **NSG** opens SSH (22), HTTPS signaling (TCP 443), and WebRTC media
  (UDP `webrtc_udp_port_range`). The backend's plain `:8000` is not exposed.
- **cloud-init** installs Docker and writes:
  - `/opt/voice-chat/docker-compose.yml` (from [../deploy/docker-compose.yml](../deploy/docker-compose.yml))
  - `/opt/voice-chat/Caddyfile` (from [../deploy/Caddyfile](../deploy/Caddyfile),
    with the VM public IP substituted in)
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

curl -kfsS https://<public_ip>/health      # {"status":"ok","api_key_configured":true}
ssh <admin>@<public_ip>                    # then: docker compose -f /opt/voice-chat/docker-compose.yml ps
```

> Caddy uses a self-signed certificate for the VM's public IP, so `curl` needs
> `-k`. For a trusted cert, point a domain at the VM and replace the site
> address in [../deploy/Caddyfile](../deploy/Caddyfile) with that domain.

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
2. **TLS is terminated by Caddy** on the VM using a self-signed certificate for
   the VM's public IP. The local Vite dev proxy accepts it via `secure: false`
   (see [../frontend/vite.config.ts](../frontend/vite.config.ts)); the browser
   itself only talks to `localhost`. To use a trusted certificate, point a
   domain at the VM and set that domain as the Caddyfile site address so Caddy
   can obtain a Let's Encrypt certificate.
3. **Secrets.** The API key is written to the VM's `/opt/voice-chat/.env`. For
   stricter handling, store it in Azure Key Vault and read it via a managed
   identity at boot.

## Teardown

```bash
terraform destroy
```
