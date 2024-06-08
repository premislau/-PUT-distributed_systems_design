import azure.functions as func
import datetime
import json
import logging
import os
import uuid

import json
import numpy as np
import string
from gensim import downloader
import multiprocessing

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
    data['Evaluated'] = remove_punctuation(data['Evaluated']).split()
    return evaluate_basing_on_every_words_cosine_similarity(data)


def evaluation(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_body()
    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(
            "Error: Unable to read the request body", status_code=400
        )

    result = evaluate(body)

    return func.HttpResponse(
        json.dumps(result),
        status_code=200,
        headers={"Content-Type": "application/json"},
    )