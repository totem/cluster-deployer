from flask import json
from flask.views import MethodView
import deployer


class RootApi(MethodView):

    def get(self):
        return json.dumps({'version': deployer.__version__})


def register(app):
    app.add_url_rule('/', view_func=RootApi.as_view('root'))
