# Azure Cognitive Services image recognition
resource "azurerm_cognitive_account" "cognitive" {
  name                = "${var.name}${var.environment}cognitive"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku_name            = "F0"
  kind                = "ComputerVision"
}
