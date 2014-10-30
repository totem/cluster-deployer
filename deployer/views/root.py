import flask
from flask.views import MethodView
import deployer
from deployer.views.hypermedia import HyperSchema


class RootApi(MethodView):
    """
    Root API
    """

    @HyperSchema('root-v1')
    def get(self):
        """
        Gets the version for the Deployer API.

        :return: Flask Json Response containing version.
        """
        return flask.jsonify({'version': deployer.__version__})


def register(app):
    """
    Registers RootApi ('/')
    Only GET operation is available.

    :param app: Flask application
    :return: None
    """
    app.add_url_rule('/', view_func=RootApi.as_view('root'), methods=['GET'])
