terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }

  # Remote state in Azure Storage. Values are supplied at init time via
  # `terraform init -backend-config=backend.hcl` (see backend.hcl.example).
  #   backend "azurerm" {}
}

provider "azurerm" {
  features {}
}
