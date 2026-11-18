output "public_ip" {
  description = "Public IP address of the VM."
  value       = azurerm_public_ip.pip.ip_address
}

output "backend_url" {
  description = "Backend base URL (HTTPS, Caddy-terminated; self-signed cert)."
  value       = "https://${azurerm_public_ip.pip.ip_address}"
}

output "backend_ws_url" {
  description = "Backend signaling WebSocket URL (wss), used as the Vite proxy target."
  value       = "wss://${azurerm_public_ip.pip.ip_address}"
}

output "health_url" {
  description = "Backend health check URL (HTTPS, self-signed)."
  value       = "https://${azurerm_public_ip.pip.ip_address}/health"
}

output "ssh_command" {
  description = "Command to SSH into the VM."
  value       = "ssh ${var.admin_username}@${azurerm_public_ip.pip.ip_address}"
}
