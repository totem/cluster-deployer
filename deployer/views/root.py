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


def register(app):
    """
    Registers RootApi
    :param app:
    :return:
    """
    app.add_url_rule('/', view_func=RootApi.as_view('root'))
