import json
from flask import Response, jsonify


def build_response(output, status=200, mimetype='application/json',
                   headers={}):
    resp = jsonify(output)
    resp.mimetype = mimetype
    return resp, status, headers
