resource "azurerm_resource_group" "app" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.vm_tags
}

resource "azurerm_virtual_network" "vnet" {
  name                = "voice-chat-vnet"
  resource_group_name = azurerm_resource_group.app.name
  location            = azurerm_resource_group.app.location
  address_space       = ["10.0.0.0/16"]
  tags                = var.vm_tags
}

resource "azurerm_subnet" "subnet" {
  name                 = "voice-chat-subnet"
  resource_group_name  = azurerm_resource_group.app.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_public_ip" "pip" {
  name                = "voice-chat-pip"
  resource_group_name = azurerm_resource_group.app.name
  location            = azurerm_resource_group.app.location
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = var.vm_tags
}

resource "azurerm_network_interface" "nic" {
  name                = "voice-chat-nic"
  resource_group_name = azurerm_resource_group.app.name
  location            = azurerm_resource_group.app.location
  tags                = var.vm_tags

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.subnet.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.pip.id
  }
}

resource "azurerm_network_security_group" "nsg" {
  name                = "voice-chat-nsg"
  resource_group_name = azurerm_resource_group.app.name
  location            = azurerm_resource_group.app.location
  tags                = var.vm_tags

  security_rule {
    name                       = "SSH"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  # HTTPS signaling WebSocket + /health, terminated by Caddy on the VM.
  # The local frontend's Vite dev server proxies /ws and /health (over wss/https)
  # to this port. The backend's plain :8000 is no longer exposed publicly.
  security_rule {
    name                       = "HTTPS"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "WebRTC-UDP"
    priority                   = 120
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Udp"
    source_port_range          = "*"
    destination_port_range     = var.webrtc_udp_port_range
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_network_interface_security_group_association" "nic_nsg" {
  network_interface_id      = azurerm_network_interface.nic.id
  network_security_group_id = azurerm_network_security_group.nsg.id
}
