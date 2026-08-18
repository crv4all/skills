resource "azurerm_storage_account" "data" {
  name                     = "crvdata${var.environment}"
  resource_group_name      = "data-platform-${var.environment}"
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "ZRS"
  min_tls_version          = "TLS1_2"
}
