#cloud-config

package_update: true

packages:
  - ca-certificates
  - curl
  - gnupg
  - lsb-release
  - openssl

write_files:
  - path: /opt/voice-chat/docker-compose.yml
    permissions: "0644"
    owner: root:root
    content: |
      ${replace(trimspace(compose_yaml), "\n", "\n      ")}

  - path: /opt/voice-chat/Caddyfile
    permissions: "0644"
    owner: root:root
    content: |
      ${replace(trimspace(caddyfile), "\n", "\n      ")}

  - path: /opt/voice-chat/.env
    permissions: "0600"
    owner: root:root
    content: |
      OPENAI_API_KEY=${openai_api_key}
      OPENAI_REALTIME_MODEL=${openai_realtime_model}
      OPENAI_REALTIME_VOICE=${openai_realtime_voice}
      OPENAI_INSTRUCTIONS=${openai_instructions}
      OPENAI_SAFETY_IDENTIFIER=${openai_safety_identifier}
      WEBRTC_STUN_URL=${webrtc_stun_url}
      WEBRTC_TURN_URL=${webrtc_turn_url}
      WEBRTC_TURN_USERNAME=${webrtc_turn_username}
      WEBRTC_TURN_CREDENTIAL=${webrtc_turn_credential}

  # Auto-update: periodically pull the latest backend image from GHCR and
  # recreate the container when a new image is pushed.
  - path: /etc/systemd/system/voice-chat-update.service
    permissions: "0644"
    owner: root:root
    content: |
      [Unit]
      Description=Pull latest voice-chat backend image and restart if changed
      Wants=network-online.target
      After=network-online.target docker.service

      [Service]
      Type=oneshot
      WorkingDirectory=/opt/voice-chat
      ExecStart=/usr/bin/docker compose -f /opt/voice-chat/docker-compose.yml pull
      ExecStart=/usr/bin/docker compose -f /opt/voice-chat/docker-compose.yml up -d --remove-orphans

  - path: /etc/systemd/system/voice-chat-update.timer
    permissions: "0644"
    owner: root:root
    content: |
      [Unit]
      Description=Periodically update the voice-chat backend

      [Timer]
      OnBootSec=2min
      OnUnitActiveSec=2min
      RandomizedDelaySec=30s
      Persistent=true

      [Install]
      WantedBy=timers.target

runcmd:
  - |
    set -eux
    install -d -m 0755 /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
    install -d -m 0700 /opt/voice-chat/certs
    openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes \
      -keyout /opt/voice-chat/certs/privkey.pem \
      -out /opt/voice-chat/certs/fullchain.pem \
      -days 3650 \
      -subj "/CN=${public_ip}" \
      -addext "subjectAltName=IP:${public_ip},DNS:localhost" \
      -addext "keyUsage=digitalSignature,keyEncipherment" \
      -addext "extendedKeyUsage=serverAuth"
    docker compose -f /opt/voice-chat/docker-compose.yml up -d
    systemctl daemon-reload
    systemctl enable --now voice-chat-update.timer
