import json
from flask import Response


def build_response(output, status=200, mimetype='application/json',
                   headers={}):
    return Response(
        json.dumps(output),
        mimetype=mimetype
    ), status, headers
