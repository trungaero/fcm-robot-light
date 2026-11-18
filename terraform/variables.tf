variable "location" {
  description = "Azure region to deploy the app resources into."
  type        = string
  default     = "southeastasia"
}

variable "resource_group_name" {
  description = "Name of the resource group for app resources (separate from the state RG)."
  type        = string
  default     = "voice-chat-rg"
}

variable "vm_size" {
  description = "Azure VM size."
  type        = string
  default     = "Standard_D2s_v5"
}

variable "vm_priority" {
  description = "Azure VM priority. Use \"Spot\" for lower-cost interruptible VMs."
  type        = string
  default     = "Spot"

  validation {
    condition     = contains(["Regular", "Spot"], var.vm_priority)
    error_message = "vm_priority must be either \"Regular\" or \"Spot\"."
  }
}

variable "vm_eviction_policy" {
  description = "Eviction policy for Spot VMs (ignored for Regular priority)."
  type        = string
  default     = "Deallocate"

  validation {
    condition     = contains(["Deallocate", "Delete"], var.vm_eviction_policy)
    error_message = "vm_eviction_policy must be either \"Deallocate\" or \"Delete\"."
  }
}

variable "admin_username" {
  description = "Admin username for the Linux VM."
  type        = string
  default     = "azureuser"
}

variable "ssh_public_key" {
  description = "Absolute path to the public SSH key used to log into the VM."
  type        = string
}

variable "openai_api_key" {
  description = "OpenAI API key injected into the backend .env on the VM."
  type        = string
  sensitive   = true
}

variable "openai_realtime_model" {
  description = "OpenAI Realtime model."
  type        = string
  default     = "gpt-realtime-mini"
}

variable "openai_realtime_voice" {
  description = "OpenAI Realtime output voice."
  type        = string
  default     = "marin"
}

variable "openai_instructions" {
  description = "System prompt for the assistant."
  type        = string
  default     = "You are a friendly, concise voice assistant. Keep replies short and conversational."
}

variable "openai_safety_identifier" {
  description = "Privacy-preserving end-user id sent to OpenAI."
  type        = string
  default     = "voice-chat-demo"
}

variable "webrtc_stun_url" {
  description = "STUN server URL used for ICE candidate discovery."
  type        = string
  default     = "stun:stun.l.google.com:19302"
}

variable "webrtc_turn_url" {
  description = "Optional TURN server URL (recommended for reliable media)."
  type        = string
  default     = ""
}

variable "webrtc_turn_username" {
  description = "Optional TURN server username."
  type        = string
  default     = ""
}

variable "webrtc_turn_credential" {
  description = "Optional TURN server credential."
  type        = string
  sensitive   = true
  default     = ""
}

variable "webrtc_udp_port_range" {
  description = "Inbound UDP port range opened for WebRTC media (aiortc uses ephemeral ports; see README)."
  type        = string
  default     = "40000-40100"
}

variable "vm_tags" {
  description = "Tags applied to provisioned resources."
  type        = map(string)
  default     = {}
}
