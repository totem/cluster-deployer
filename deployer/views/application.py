import json
from flask import request
import flask
from flask.views import MethodView
from deployer.tasks.deployment import create, delete


class ApplicationApi(MethodView):

    def post(self):
        deployment = json.loads(request.data)
        result = create.apply_async([deployment])
        return flask.jsonify({'task_id': str(result)}), 202

    def delete(self, id):
        id_split = id.split('+')
        if len(id_split) != 2:
            flask.abort(400)
        else:
            result = delete.delay(id_split[0], id_split[1])
            return flask.jsonify({'task_id': str(result)}), 202


def register(app):
    view_func = ApplicationApi.as_view('apps')
    app.add_url_rule('/apps', view_func=view_func, methods=['POST'])
    app.add_url_rule('/apps/<id>', view_func=view_func,
                     methods=['DELETE'])
