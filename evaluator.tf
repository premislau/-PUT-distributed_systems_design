# Create Private Endpoints
resource "azurerm_private_endpoint" "evaluator" {
  name                = "evaluator-pe"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  subnet_id           = azurerm_subnet.internal.id

  private_service_connection {
    name                           = "evaluator-privatelink"
    private_connection_resource_id = azurerm_linux_function_app.evaluator.id
    is_manual_connection           = false
    subresource_names              = ["sites"]
  }
}


resource "azurerm_private_dns_a_record" "evaluator" {
  name                = "evaluator"
  zone_name           = azurerm_private_dns_zone.privatelink_azurewebsites_net.name
  resource_group_name = azurerm_resource_group.rg.name
  ttl                 = 300
  records             = [data.azurerm_network_interface.evaluator_nic.private_ip_address]
}

data "azurerm_network_interface" "evaluator_nic" {
  name                = azurerm_private_endpoint.evaluator.name
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_linux_function_app" "evaluator" {
  name                       = "${var.name}${var.environment}evaluator"
  resource_group_name        = azurerm_resource_group.rg.name
  location                   = azurerm_resource_group.rg.location

  service_plan_id        = azurerm_service_plan.app_service_plan.id

  storage_account_name       = azurerm_storage_account.appcode.name
  storage_account_access_key = azurerm_storage_account.appcode.primary_access_key

  app_settings = {
    "WEBSITE_RUN_FROM_PACKAGE" = "",
    "FUNCTIONS_WORKER_RUNTIME" = "python",
    "APPINSIGHTS_INSTRUMENTATIONKEY" = azurerm_application_insights.application_insights.instrumentation_key,
    "AzureWebJobsFeatureFlags" = "EnableWorkerIndexing"


  }

  site_config {
    always_on = false
    application_stack {
        python_version = "3.9"
    }
  }

  lifecycle {
    ignore_changes = [
      app_settings["WEBSITE_RUN_FROM_PACKAGE"],
    ]
  }
}