import json
from flask import request
import flask
from flask.views import MethodView
from deployer.tasks.deployment import create, delete


class ApplicationApi(MethodView):
    """
    API for create, deleting, fetching applications
    """

    def post(self):
        """
        Allows creation of new application version.
        :return:
        """
        deployment = json.loads(request.data)
        result = create.apply_async([deployment])
        return flask.jsonify({'task_id': str(result)}), 202

    def delete(self, name):
        """
        Deletes all applications with given name

        :param name: Name of the application
        :type name: str
        :return: Flask response code for 202.
        """
        result = delete.delay(name)
        return flask.jsonify({'task_id': str(result)}), 202


class VersionApi(MethodView):
    """
    API for deleting and fetching versions for application.
    """

    def delete(self, name, version):
        """
        Deletes applications with given name and version
        :param name:  Name of the application
        :type name: str
        :param version: Version of the application
        :type version: str
        :return: Flask response code for 202.
        """
        result = delete.delay(name, version=version)
        return flask.jsonify({'task_id': str(result)}), 202


def register(app):
    apps_func = ApplicationApi.as_view('apps')
    versions_func = VersionApi.as_view('versions')
    app.add_url_rule('/apps', view_func=apps_func, methods=['POST'])
    app.add_url_rule('/apps/<name>', view_func=apps_func,
                     methods=['DELETE'])
    app.add_url_rule('/apps/<name>/versions/<version>',
                     view_func=versions_func,
                     methods=['DELETE'])
