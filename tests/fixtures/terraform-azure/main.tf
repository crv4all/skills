provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

module "storage" {
  source      = "./modules/storage"
  environment = var.environment
  location    = var.location
}
