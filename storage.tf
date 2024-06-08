resource "azurerm_storage_account" "photos" {
    name                     = "${var.name}${var.environment}photos"
    resource_group_name      = azurerm_resource_group.rg.name
    location                 = azurerm_resource_group.rg.location
    account_tier             = "Standard"
    account_replication_type = "LRS"
}

resource "azurerm_storage_container" "photos" {
    name                  = "images"
    storage_account_name  = azurerm_storage_account.photos.name
    container_access_type = "private"
}

resource "azurerm_storage_table" "photos" {
    name                 = "photosdb"
    storage_account_name = azurerm_storage_account.photos.name
}

resource "azurerm_storage_queue" "photoqueue" {
    name                 = "photoprocess"
    storage_account_name = azurerm_storage_account.photos.name
}
