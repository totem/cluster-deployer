import flask
from flask.views import MethodView
from flask import jsonify, request
from deployer.views.hypermedia import load_schema


class SchemaApi(MethodView):
    """
    Root API
    """

    def get(self, schema_id):
        """
        Gets the version for the Deployer API.

        :return: Flask Json Response containing version.
        """
        schema = load_schema(request.url_root[:-1], schema_id)
        if not schema:
            return flask.abort(404)
        return jsonify(schema)


def register(app):
    """
    Register the schema endpoint
    :param app: Flask application
    :return:
    """
    app.add_url_rule('/schemas/<string:schema_id>',
                     view_func=SchemaApi.as_view('schemas'),
                     methods=['GET'])
