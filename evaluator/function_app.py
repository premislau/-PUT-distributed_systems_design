import azure.functions as func
import json
import logging

import numpy as np
import string
from gensim import downloader

app = func.FunctionApp()

wage_exponent = 5

model = None

def get_model():
    global model
    if model is None:
        model = downloader.load("glove-wiki-gigaword-100")
    return model

def remove_punctuation(s):
    table = s.maketrans({key: None for key in string.punctuation})
    return s.translate(table)


def sum_cosine_similarities(keywords, evaluated):
    result = 0.0
    for keyword in keywords:
        for word in evaluated:
            try:
                result += np.power(get_model().similarity(keyword, word), wage_exponent)
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
    keywords = req.params.get('Keywords')
    evaluated = req.params.get('Evaluated')

    if not keywords:
        logging.error("Error: Missing a 'Keywords' parameter in a request")
        return func.HttpResponse(
            f"Error: Missing a 'Keywords' parameter in a request", status_code=400
        )

    if not evaluated:
        logging.error("Error: Missing an 'Evaluated' parameter in a request")
        return func.HttpResponse(
            f"Error: Missing an 'Evaluated' parameter in a request", status_code=400
        )
    
    query = {
        "Keywords": keywords,
        "Evaluated": evaluated
    }

    try:
        result = evaluate(query)
    except Exception as e:
        logging.error(f"Error during evaluation: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Error during evaluation"}),
            status_code=500,
            headers={"Content-Type": "application/json"}
        )

    return func.HttpResponse(
        json.dumps({"Evaluation": result}),
        status_code=200,
        headers={"Content-Type": "application/json"}
    )