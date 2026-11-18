output "public_ip" {
  description = "Public IP address of the VM."
  value       = azurerm_public_ip.pip.ip_address
}

output "backend_url" {
  description = "Backend base URL (HTTP)."
  value       = "http://${azurerm_public_ip.pip.ip_address}:8000"
}

output "backend_ws_url" {
  description = "Backend signaling WebSocket URL, used as the Vite proxy target."
  value       = "ws://${azurerm_public_ip.pip.ip_address}:8000"
}

output "health_url" {
  description = "Backend health check URL."
  value       = "http://${azurerm_public_ip.pip.ip_address}:8000/health"
}

output "ssh_command" {
  description = "Command to SSH into the VM."
  value       = "ssh ${var.admin_username}@${azurerm_public_ip.pip.ip_address}"
}
