import json
from flask import request
import flask
from flask.views import MethodView
from deployer.tasks.deployment import create


class ApplicationApi(MethodView):

    def post(self):
        deployment = json.loads(request.data)
        result = create.apply_async([deployment])
        return flask.jsonify({'task_id': str(result)})


def register(app):
    app.add_url_rule('/apps',
                     view_func=ApplicationApi.as_view('apps'))
