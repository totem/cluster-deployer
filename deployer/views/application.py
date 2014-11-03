import json
from celery.result import AsyncResult
from flask import request
import flask
from flask.ext.negotiate import consumes, produces
from flask.views import MethodView
from flask import url_for
from conf.appconfig import TASK_SETTINGS
from deployer.tasks.deployment import create, delete
from deployer.views.hypermedia import ValidateSchema, HyperSchema
from deployer.views.task import TaskApi
from deployer.views.util import build_response


class ApplicationApi(MethodView):
    """
    API for create, deleting, fetching applications
    """

    @consumes('application/vnd.app-version-create-v1+json', 'application/json')
    @produces('application/vnd.app-version-v1+json',
              'application/vnd.task-v1+json', 'application/json', '*/*')
    @HyperSchema('app-version-v1')
    @ValidateSchema('app-version-create-v1')
    def post(self, data=None):
        """
        Allows creation of new application version.
        :return:
        """
        deployment = json.loads(request.data)
        result = create.apply_async([deployment])
        if request.accept_mimetypes[0][0] == \
                'application/vnd.app-version-v1+json':
            while isinstance(result, AsyncResult):
                result = result.get(
                    timeout=TASK_SETTINGS['DEFAULT_GET_TIMEOUT'])
            return build_response(
                result,
                mimetype='application/vnd.app-version-create-v1+json',
                status=201, headers={
                    'Location': url_for(
                        '.versions', name=result['deployment']['name'],
                        version=result['deployment']['version'])
                })
        else:
            return build_response(
                {'task_id': str(result)},
                mimetype='application/vnd.task-v1+json',
                status=202, headers={
                    'Location': url_for('.tasks', id=str(result))
                })

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
