# PUT-distributed_systems_design
An Azure-based project made for distributed systems design (projektowanie systemów rozproszonych, PSR) at Poznań University of Technology (PUT). Code from https://github.com/mescam/psr2024 was used as basis for this project.

Upon deployment this project allows to post and store photos using infrastructure provided by Azure. The photoS are tagged using Azure Cognitive Services. Users can insert keywords to "/matched_photo" endpoint of main app to get a photo, of which tags suit the provided query. Evaluator microservice uses word2vec capabilities of Gensim library to evaluate proximity of searched keywords to provided tags (evaluator's endpoint is used by main app).

# Deployment
**Warning:** Certain names are required to be globally unique within Azure Cloud; therefore value of "name" in vars.tf should be changed by each Azure user, who deploys this project.

In following terminal listings ${var.name}${var.environment} should be substituted with adequate values from vars.tf
## Terraform
In \PUT-distributed_systems_design
```powershell
terraform apply
```
## Evaluator
In \PUT-distributed_systems_design\evaluator
```powershell
func azure functionapp publish "${var.name}${var.environment}evaluator" --python
```

## Main app
In \PUT-distributed_systems_design\app
```powershell
func azure functionapp publish "${var.name}${var.environment}app" --python
```

# Usage
Upon deployment one can use following endpoints:
- **POST** `https://${var.name}${var.environment}app.azurewebsites.net/api/new_photo` – Posts a photo to the service.

- **GET** `https://${var.name}${var.environment}app.azurewebsites.net/api/photos_list` – Gets a list of information about stored photos.

- **GET** `https://${var.name}${var.environment}app.azurewebsites.net/api/matched_photo?Searched={Searched}` – Gets a photo which was evaluated as best suiting for keywords provided as a "Searched" parameter.