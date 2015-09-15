import flask
from flask.views import MethodView
from flask import url_for, redirect, request

from conf.appconfig import MIME_JSON, MIME_TASK_V1, \
    SCHEMA_TASK_V1, MIME_APP_VERSION_CREATE_V1, SCHEMA_APP_VERSION_CREATE_V1, \
    SCHEMA_APP_VERSION_V1, MIME_APP_VERSION_V1, MIME_APP_DELETE_V1, \
    SCHEMA_APP_LIST_V1, MIME_APP_LIST_V1, SCHEMA_APP_VERSION_LIST_V1, \
    MIME_APP_VERSION_LIST_V1, MIME_APP_VERSION_DELETE_V1, \
    SCHEMA_APP_VERSION_UNIT_LIST_V1, MIME_APP_VERSION_UNIT_LIST_V1, \
    SCHEMA_RECOVERY_V1, MIME_RECOVERY_V1
from deployer.services.storage.factory import get_store

from deployer.tasks.deployment import create, delete, list_units, \
    recover_cluster
from deployer.views import hypermedia, task_client
from deployer.views.util import created_task, created, deleted, \
    build_response, use_paging


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
            return created(deployment, location=location)
        else:
            return created_task(result)

    def get(self, name=None):
        if name:
            return redirect('%s?%s' % (
                url_for('.versions', name=name), request.query_string))
        else:
            return self.list()

    @hypermedia.produces({
        MIME_JSON: SCHEMA_APP_LIST_V1,
        MIME_APP_LIST_V1: SCHEMA_APP_LIST_V1
    }, default=MIME_APP_LIST_V1)
    def list(self, **kwargs):
        """
        Lists all applications.

        :param kwargs:
        :return:
        """
        apps = get_store().find_apps()
        return build_response(apps)

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

    def get(self, name, version=None):
        if version:
            return self.find_one(name, version)
        else:
            return self.list(name)

    @hypermedia.produces({
        MIME_JSON: SCHEMA_APP_VERSION_LIST_V1,
        MIME_APP_VERSION_LIST_V1: SCHEMA_APP_VERSION_LIST_V1
    }, default=MIME_APP_VERSION_LIST_V1)
    @use_paging
    def list(self, name, **kwargs):
        """
        Lists all applications. Require search to be enabled.

        :param kwargs:
        :return: Flask Response wrapping deployment list.
        """

        deployments = get_store().filter_deployments(name)
        return build_response(deployments)

    @hypermedia.produces({
        MIME_JSON: SCHEMA_APP_VERSION_V1,
        MIME_APP_VERSION_V1: SCHEMA_APP_VERSION_V1
    }, default=MIME_APP_VERSION_V1)
    def find_one(self, name, version, **kwargs):
        """
        Finds single deployment. Require search to be enabled.

        :param kwargs:
        :return: Flask Response wrapping deployment.
        """

        deployments = get_store().filter_deployments(name, version=version)
        if not deployments:
            flask.abort(404)
        return build_response(deployments[0])

    @hypermedia.produces({
        MIME_TASK_V1: SCHEMA_TASK_V1,
        MIME_JSON: SCHEMA_TASK_V1,
        MIME_APP_VERSION_DELETE_V1: None
    }, default=MIME_TASK_V1)
    def delete(self, name, version, accept_mimetype=None, **kwargs):
        """
        Deletes applications with given name and version

        :param name:  Name of the application
        :type name: str
        :param version: Version of the application
        :type version: str
        :return: Flask response code for 202.
        """
        result = delete.delay(name, version=version)

        if accept_mimetype == MIME_APP_VERSION_DELETE_V1:
            task_client.ready(result.id, wait=True, raise_error=True)
            return deleted(mimetype=accept_mimetype)

        else:
            return created_task(result)


class StateApi(MethodView):
    """
    API for managing state of a given deployment
    """

    @hypermedia.produces({
        MIME_TASK_V1: SCHEMA_TASK_V1,
        MIME_JSON: SCHEMA_TASK_V1,
        MIME_APP_VERSION_DELETE_V1: None
    }, default=MIME_TASK_V1)
    def update_state(self, name, version, accept_mimetype=None, **kwargs):
        """
        Deletes applications with given name and version

        :param name:  Name of the application
        :type name: str
        :param version: Version of the application
        :type version: str
        :return: Flask response code for 202.
        """
        result = delete.delay(name, version=version)

        if accept_mimetype == MIME_APP_VERSION_DELETE_V1:
            task_client.ready(result.id, wait=True, raise_error=True)
            return deleted(mimetype=accept_mimetype)

        else:
            return created_task(result)


class UnitApi(MethodView):
    """
    API for units of a deployed application version
    """

    @hypermedia.produces({
        MIME_TASK_V1: SCHEMA_TASK_V1,
        MIME_JSON: SCHEMA_TASK_V1,
        MIME_APP_VERSION_UNIT_LIST_V1: SCHEMA_APP_VERSION_UNIT_LIST_V1
    }, default=MIME_TASK_V1)
    def get(self, name, version, accept_mimetype=None, **kwargs):
        """
        Gets all deployed units for a given application version.

        :param name:
        :param version:
        :return: Flask Response wrapping units list
        """

        result = list_units.delay(name, version)
        if accept_mimetype == MIME_APP_VERSION_UNIT_LIST_V1:
            result = task_client.ready(result.id, wait=True, raise_error=True)
            return build_response(result['output'] or [])
        else:
            return created_task(result)


class RecoveryApi(MethodView):
    """
    Provides API for deployment recovery
    :param MethodView:
    :return:
    """

    @hypermedia.consumes({
        MIME_RECOVERY_V1: SCHEMA_RECOVERY_V1,
        MIME_JSON: SCHEMA_RECOVERY_V1
    })
    @hypermedia.produces({
        MIME_TASK_V1: SCHEMA_TASK_V1,
        MIME_JSON: SCHEMA_TASK_V1
    }, default=MIME_TASK_V1)
    def post(self, request_data=None, accept_mimetype=None, **kwargs):
        """
        Allows creation of new application version.
        :return:
        """
        result = recover_cluster.delay(request_data)
        return created_task(result)


def register(app, **kwargs):
    apps_func = ApplicationApi.as_view('apps')
    versions_func = VersionApi.as_view('versions')
    units_func = UnitApi.as_view('units')
    recovery_func = RecoveryApi.as_view('recovery')

    for uri in ('/apps', '/apps/'):
        app.add_url_rule(uri,  view_func=apps_func, methods=['GET', 'POST'])

    app.add_url_rule('/apps/<name>', view_func=apps_func,
                     methods=['DELETE', 'GET'])

    for uri in ('/apps/<name>/versions', '/apps/<name>/versions/'):
        app.add_url_rule(uri, view_func=versions_func, methods=['GET'])

    version_uri = '/apps/<name>/versions/<version>'
    app.add_url_rule(version_uri,
                     view_func=versions_func,
                     methods=['DELETE', 'GET'])

    for uri in ('%s/units' % (version_uri), '%s/units/' % version_uri):
        app.add_url_rule(uri, view_func=units_func, methods=['GET'])

    for uri in ('/recovery', '/recovery/'):
        app.add_url_rule(uri, view_func=recovery_func, methods=['POST'])
