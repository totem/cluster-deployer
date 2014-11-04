import flask
from flask.views import MethodView
from flask import url_for

from conf.appconfig import MIME_JSON, MIME_TASK_V1, \
    SCHEMA_TASK_V1
from deployer.tasks.deployment import create, delete
from deployer.views import hypermedia, task_client
from deployer.views.util import created_task, created, deleted


MIME_APP_VERSION_V1 = 'application/vnd.app-version-v1+json'
MIME_APP_VERSION_CREATE_V1 = 'application/vnd.app-version-create-v1+json'
MIME_APP_VERSION_DELETE_V1 = 'application/vnd.app-version-delete-v1+json'
MIME_APP_DELETE_V1 = 'application/vnd.app-delete-v1+json'

SCHEMA_APP_VERSION_CREATE_V1 = 'app-version-create-v1'
SCHEMA_APP_VERSION_V1 = 'app-version-v1'


class ApplicationApi(MethodView):
    """
    API for create, deleting, fetching applications
    """

    @hypermedia.consumes({
        MIME_APP_VERSION_CREATE_V1: SCHEMA_APP_VERSION_CREATE_V1,
        MIME_JSON: SCHEMA_APP_VERSION_CREATE_V1
    })
    @hypermedia.produces({
        MIME_TASK_V1: SCHEMA_TASK_V1,
        MIME_JSON: SCHEMA_TASK_V1,
        MIME_APP_VERSION_V1: SCHEMA_APP_VERSION_V1
    }, default=MIME_TASK_V1)
    def post(self, request_data=None, accept_mimetype=None, **kwargs):
        """
        Allows creation of new application version.
        :return:
        """
        deployment = request_data
        result = create.delay(deployment)
        if accept_mimetype == MIME_APP_VERSION_V1:
            result = task_client.ready(
                result.id, wait=True, raise_error=True)
            deployment = result['output']
            location = url_for(
                '.versions', name=deployment['deployment']['name'],
                version=deployment['deployment']['version'])
            return created(deployment, location=location,
                           mimetype=accept_mimetype)
        else:
            return created_task(result)


    @hypermedia.produces({
        MIME_TASK_V1: SCHEMA_TASK_V1,
        MIME_JSON: SCHEMA_TASK_V1,
        MIME_APP_DELETE_V1: None
    }, default=MIME_TASK_V1)
    def delete(self, name, accept_mimetype=None, **kwargs):
        """
        Deletes all applications with given name

        :param name: Name of the application
        :type name: str
        :return: Flask response code for 202.
        """
        result = delete.delay(name)

        if accept_mimetype == MIME_APP_DELETE_V1:
            task_client.ready(result.id, wait=True, raise_error=True)
            return deleted(mimetype=accept_mimetype)

        else:
            return created_task(result)


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


def register(app, **kwargs):
    apps_func = ApplicationApi.as_view('apps')
    versions_func = VersionApi.as_view('versions')
    app.add_url_rule('/apps', view_func=apps_func, methods=['POST'])
    app.add_url_rule('/apps/<name>', view_func=apps_func,
                     methods=['DELETE'])
    app.add_url_rule('/apps/<name>/versions/<version>',
                     view_func=versions_func,
                     methods=['DELETE'])
