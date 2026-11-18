locals {
  compose_yaml = file("${path.module}/../deploy/docker-compose.yml")
  caddyfile    = file("${path.module}/../deploy/Caddyfile")

  cloud_init = templatefile("${path.module}/templates/cloud-init.yaml.tpl", {
    compose_yaml             = local.compose_yaml
    caddyfile                = local.caddyfile
    public_ip                = azurerm_public_ip.pip.ip_address
    openai_api_key           = var.openai_api_key
    openai_realtime_model    = var.openai_realtime_model
    openai_realtime_voice    = var.openai_realtime_voice
    openai_instructions      = var.openai_instructions
    openai_safety_identifier = var.openai_safety_identifier
    webrtc_stun_url          = var.webrtc_stun_url
    webrtc_turn_url          = var.webrtc_turn_url
    webrtc_turn_username     = var.webrtc_turn_username
    webrtc_turn_credential   = var.webrtc_turn_credential
  })
}

resource "azurerm_linux_virtual_machine" "vm" {
  name                            = "voice-chat-vm"
  resource_group_name             = azurerm_resource_group.app.name
  location                        = azurerm_resource_group.app.location
  size                            = var.vm_size
  admin_username                  = var.admin_username
  network_interface_ids           = [azurerm_network_interface.nic.id]
  custom_data                     = base64encode(local.cloud_init)
  disable_password_authentication = true
  priority                        = var.vm_priority
  eviction_policy                 = var.vm_eviction_policy
  tags                            = var.vm_tags

  admin_ssh_key {
    username   = var.admin_username
    public_key = file(var.ssh_public_key)
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }
}
