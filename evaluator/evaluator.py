import azure.functions as func
import json
import logging

import numpy as np
import string
from gensim import downloader

app = func.FunctionApp()

wage_exponent = 5

model = downloader.load("glove-wiki-gigaword-100")

def remove_punctuation(s):
    table = s.maketrans({key: None for key in string.punctuation})
    return s.translate(table)


def sum_cosine_similarities(keywords, evaluated):
    result = 0.0
    for keyword in keywords:
        for word in evaluated:
            try:
                result += np.power(model.similarity(keyword, word), wage_exponent)
            except KeyError:
                pass
    return result


def evaluate_basing_on_every_words_cosine_similarity(data):
    result = sum_cosine_similarities(data['Keywords'], data['Evaluated'])
    return result / len(data['Evaluated']) 


def evaluate(data):
    data['Keywords'] = remove_punctuation(data['Keywords']).split()
    data['Evaluated'] = remove_punctuation(data['Evaluated']).split()
    return evaluate_basing_on_every_words_cosine_similarity(data)



@app.function_name(name="evaluation")
@app.route(route="evaluation", auth_level=func.AuthLevel.ANONYMOUS, methods=["GET"])
def evaluation(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError as e:
        logging.error(f"Error reading request body: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Unable to read the request body"}),
            status_code=400,
            headers={"Content-Type": "application/json"}
        )

    if 'Keywords' not in body or 'Evaluated' not in body:
        logging.error("Invalid input: 'Keywords' or 'Evaluated' not found")
        return func.HttpResponse(
            json.dumps({"error": "Invalid input: 'Keywords' or 'Evaluated' not found"}),
            status_code=400,
            headers={"Content-Type": "application/json"}
        )

    try:
        result = evaluate(body)
    except Exception as e:
        logging.error(f"Error during evaluation: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Error during evaluation"}),
            status_code=500,
            headers={"Content-Type": "application/json"}
        )

    return func.HttpResponse(
        json.dumps({"result": result}),
        status_code=200,
        headers={"Content-Type": "application/json"}
    )
