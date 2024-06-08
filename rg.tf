resource "azurerm_resource_group" "rg" {
  name     = "rg-${var.name}${var.environment}-001"
  location = var.location

  tags = {
    contact = "Przemyslaw Czajka"
  }
}
