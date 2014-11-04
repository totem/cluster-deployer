import flask
from flask.views import MethodView
import deployer


class RootApi(MethodView):
    """
    Root API
    """

    def get(self):
        """
        Gets the version for the Deployer API.

        :return: Flask Json Response containing version.
        """
        return flask.jsonify({'version': deployer.__version__})


def register(app, **kwargs):
    """
    Registers RootApi ('/')
    Only GET operation is available.

    :param app: Flask application
    :return: None
    """
    app.add_url_rule('/', view_func=RootApi.as_view('root'), methods=['GET'])
