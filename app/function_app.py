import azure.functions as func
import datetime
import json
import logging
import os
import uuid

from azure.data.tables import TableServiceClient
from azure.storage.blob import BlobServiceClient, BlobSasPermissions, generate_blob_sas
from azure.storage.queue import (
    QueueServiceClient,
    BinaryBase64DecodePolicy,
    BinaryBase64EncodePolicy,
)
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import VisualFeatureTypes
from msrest.authentication import CognitiveServicesCredentials

import requests

app = func.FunctionApp()

# Configure the Azure Table Storage and Azure Blob Storage
try:
    PHOTOS_QUEUE_URL = os.environ["ENV_PHOTOS_QUEUE_URL"]
    PHOTOS_TABLE_URL = os.environ["ENV_PHOTOS_TABLE_URL"]
    PHOTOS_CONTAINER_URL = os.environ["ENV_PHOTOS_CONTAINER_URL"]
    PHOTOS_TABLE_NAME = os.environ["ENV_PHOTOS_TABLE_NAME"]
    PHOTOS_QUEUE_NAME = os.environ["ENV_PHOTOS_QUEUE_NAME"]
    PHOTOS_CONTAINER_NAME = os.environ["ENV_PHOTOS_CONTAINER_NAME"]
    PHOTOS_PRIMARY_KEY = os.environ["ENV_PHOTOS_PRIMARY_KEY"]
    CREDENTIALS = {
        "account_name": os.environ["ENV_PHOTOS_ACCOUNT_NAME"],
        "account_key": PHOTOS_PRIMARY_KEY,
    }
    PHOTOS_CONNSTRING = os.environ["ENV_PHOTOS_CONNSTR"]
    CV_ENDPOINT = os.environ["ENV_COGNITIVE_URL"]
    CV_KEY = os.environ["ENV_COGNITIVE_KEY"]
    EVALUATOR_URL = os.environ["ENV_EVALUATOR_URL"]
except KeyError as e:
    logging.error(f"Error: {e}")
    raise e


def get_evaluation(searched: str, evaluated: str):
    request_data = json.dumps({"Evaluated": evaluated,'Keywords': searched})
    connection_string = EVALUATOR_URL+"/evaluation"
    json_result = requests.get(connection_string, data=request_data, headers={'Content-Type': 'application/json'}).json()
    result = float(json_result['Evaluation'])
    return result


def generate_sas_token(image_name):
    blob_service_client = BlobServiceClient.from_connection_string(PHOTOS_CONNSTRING)
    blob_client = blob_service_client.get_blob_client(
        container=PHOTOS_CONTAINER_NAME, blob=image_name
    )
    token = generate_blob_sas(
        account_name=blob_client.account_name,
        container_name=blob_client.container_name,
        blob_name=blob_client.blob_name,
        account_key=PHOTOS_PRIMARY_KEY,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.datetime.now() + datetime.timedelta(hours=1),
    )
    return f"{blob_client.url}?{token}"


@app.function_name(name="post")
@app.route(route="post", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def post(req: func.HttpRequest) -> func.HttpResponse:
    """Post image from body to Azure Blob Storage and create an entry in Azure Table Storage"""
    try:
        table_service_client = TableServiceClient.from_connection_string(
            PHOTOS_CONNSTRING
        )
        table_client = table_service_client.get_table_client(PHOTOS_TABLE_NAME)
        blob_service_client = BlobServiceClient.from_connection_string(
            PHOTOS_CONNSTRING
        )
        queue_service_client = QueueServiceClient.from_connection_string(
            PHOTOS_CONNSTRING
        )
        queue_client = queue_service_client.get_queue_client(
            PHOTOS_QUEUE_NAME,
            message_encode_policy=BinaryBase64EncodePolicy(),
            message_decode_policy=BinaryBase64DecodePolicy(),
        )
    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(
            "Error: Unable to connect to Azure Storage", status_code=500
        )

    logging.info(
        "Uploading a photo to Azure Blob Storage and creating an entry in Azure Table Storage"
    )
    if not req.get_body():
        return func.HttpResponse(
            "Please pass an image in the request body", status_code=400
        )

    try:
        body = req.get_body()
    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(
            "Error: Unable to read the image from the request body", status_code=400
        )

    idx = str(uuid.uuid4())
    image_name = idx + ".png"

    try:
        blob_client = blob_service_client.get_blob_client(
            container=PHOTOS_CONTAINER_NAME, blob=image_name
        )
        blob_client.upload_blob(body, overwrite=True)
    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(
            "Error: Unable to upload image to Azure Blob Storage", status_code=500
        )

    entity = {
        "PartitionKey": idx,
        "RowKey": idx,
        "Timestamp": datetime.datetime.now().isoformat(),
        "Url": blob_client.url,
        "State": "uploaded",
        "Tags": "",
    }
    try:
        logging.info("upserting entity")
        table_client.upsert_entity(entity=entity)
    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(
            "Error: Unable to create an entry in Azure Table Storage", status_code=500
        )

    # add message to the queue
    try:
        queue_client.send_message(idx.encode("utf-8"))
    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(
            "Error: Unable to add a message to the Azure Queue", status_code=500
        )

    return func.HttpResponse(
        json.dumps(entity),
        status_code=200,
        headers={"Content-Type": "application/json"},
    )


@app.function_name(name="list")
@app.route(route="list", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def list(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Python HTTP trigger function processed a request.")

    try:
        table_service_client = TableServiceClient.from_connection_string(
            PHOTOS_CONNSTRING
        )
        table_client = table_service_client.get_table_client(PHOTOS_TABLE_NAME)
    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(
            "Error: Unable to connect to Azure Storage", status_code=500
        )

    logging.info(f"Connected to Azure Table Storage: {PHOTOS_TABLE_NAME}")

    # read all entities from the table
    entities = []
    try:
        for entity in table_client.list_entities():
            entities.append(entity)
        logging.warn(f"Entities: {entities}")
    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(
            "Error: Unable to read entities from Azure Table Storage", status_code=500
        )
    return func.HttpResponse(
        json.dumps({"list": entities}),
        status_code=200,
        headers={"Content-Type": "application/json"},
    )

@app.function_name(name="matched_photo")
@app.route(route="matched_photo", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def matched_photo(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Python HTTP trigger function processed a request.")

    try:
        table_service_client = TableServiceClient.from_connection_string(
            PHOTOS_CONNSTRING
        )
        table_client = table_service_client.get_table_client(PHOTOS_TABLE_NAME)
    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(
            "Error: Unable to connect to Azure Storage", status_code=500
        )

    logging.info(f"Connected to Azure Table Storage: {PHOTOS_TABLE_NAME}")
    
    highest_value = -1.0
    searched = None
    try:
        searched = req.get_body().decode("utf-8")
    except Exception as e:
        return func.HttpResponse(
            f"Error: Missing body in a request", status_code=400
        )      
    chosen_photo_idx = None
    entities = None
    try:
        entities = table_client.list_entities()
    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(
            f"Error: Unable to read entities from Azure Table Storage", status_code=500
        ) 
    try:
        for entity in entities:
            value = get_evaluation(searched, entity["Tags"])
            if value>highest_value:
                highest_value=value
                chosen_photo_idx = entity["RowKey"]
    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(
            f"Error: Unable to get an evaluation; {str(e)}", status_code=500
        )   
    if chosen_photo_idx is None:
        return func.HttpResponse(
            "Error: No photo was matched", status_code=404
        )
    blob_service_client = BlobServiceClient.from_connection_string(
            PHOTOS_CONNSTRING
        )
    try:
        blob_client = blob_service_client.get_blob_client(
            container=PHOTOS_CONTAINER_NAME, blob=f"{chosen_photo_idx}.png"
        )
        downloader = blob_client.download_blob()
        photo = downloader.readall()
    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(
            f"Error: Unable to download image from Azure Blob Storage", status_code=500
        )
    return func.HttpResponse(
        photo,
        status_code=200,
        headers={"Content-Type": "application/json"},
    )


# Process an id from queue with Azure Cognitive Services image recognition
@app.function_name(name="process")
@app.queue_trigger(
    queue_name=PHOTOS_QUEUE_NAME, connection="ENV_PHOTOS_CONNSTR", arg_name="msg"
)
def process(msg: func.QueueMessage) -> None:
    idx = msg.get_body().decode("utf-8")
    logging.info("Python HTTP trigger function processed a request.")

    try:
        table_service_client = TableServiceClient.from_connection_string(
            PHOTOS_CONNSTRING
        )
        table_client = table_service_client.get_table_client(PHOTOS_TABLE_NAME)
        credentials = CognitiveServicesCredentials(CV_KEY)
        cv_service_client = ComputerVisionClient(CV_ENDPOINT, credentials)
    except Exception as e:
        logging.error(f"Error: {e}")
        raise e

    logging.info(f"Connected to Azure Table Storage: {PHOTOS_TABLE_NAME}")

    # read the entity from the table
    entity = None
    try:
        entity = table_client.get_entity(partition_key=idx, row_key=idx)
    except Exception as e:
        logging.error(f"Error: {e}")
        raise e

    if entity is None:
        return

    # get sas token
    try:
        sas_token = generate_sas_token(idx + ".png")
    except Exception as e:
        logging.error(f"Error: {e}")
        raise e

    # Label image with Azure Congitive Services
    try:
        tags = ""
        analysis = cv_service_client.analyze_image(sas_token, [VisualFeatureTypes.tags])
        for tag in analysis.tags:
            if tag.confidence > 0.8:
                tags += tag.name + " "
    except Exception as e:
        logging.error(f"Error: {e}")
        raise e

    entity["Tags"] = tags
    entity["State"] = "processed"

    try:
        table_client.upsert_entity(entity=entity)
    except Exception as e:
        logging.error(f"Error: {e}")
        raise e

    return None

# @app.function_name(name="hello")
# @app.route(route="hello", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
# def matched_photo(req: func.HttpRequest) -> func.HttpResponse:
#     hello = ""
#     try:
#         connection_string = EVALUATOR_URL+"/hello"
#         json_result = requests.get(connection_string)
#         hello = json.loads(json_result)['Result']
#     except Exception as e:
#         return func.HttpResponse(
#             f"Exception while getting hello: "+e, status_code=500
#         )
#     result = "Got this from evaluator: "+hello
#     return func.HttpResponse(
#         result,
#         status_code=200,
#         headers={"Content-Type": "application/json"},
#     )