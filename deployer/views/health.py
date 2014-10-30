from functools import wraps
import flask
from flask.views import MethodView
from pymongo import MongoClient
import sys
from conf.celeryconfig import MONGO_URL
from deployer.elasticsearch import get_search_client
from deployer.tasks.common import ping
from deployer.views.hypermedia import HyperSchema

HEALTH_OK = 'ok'
HEALTH_FAILED = 'failed'


class HealthApi(MethodView):
    """
    API for monitoring system health.
    """

    @HyperSchema('health-v1')
    def get(self):
        """
        Gets system health.

        :return: Flask JSON response with status of
            200: If overall health is OK
            500: If health check fails for any of the component.
            E.g. output:
            {
                "mongo": {
                    "status": "ok",
                    "details": "Successfully retrieved database names"
                },
                "celery": {
                    "status": "ok",
                    "details": "Celery ping:pong",
                },
                "elasticsearch": {
                    "status": "failed",
                    "details": "Failed to connect to elasticsearch instance"
                }
            }

        """
        health = {
            'mongo': _check_mongo(),
            'celery': _check_celery(),
            'elasticsearch': _check_elasticsearch()
        }
        failed_checks = [
            health_status['status'] for health_status in health.itervalues()
            if health_status['status'] != HEALTH_OK
        ]
        http_status = 200 if not failed_checks else 500
        return flask.jsonify(health), http_status


def register(app):
    """
    Registers the Health API (/health) with flask application.
    Only GET operation is available.

    :param app: Flask application
    :return: None
    """
    app.add_url_rule('/health', view_func=HealthApi.as_view('health'),
                     methods=['GET'])


def _check(func):
    """
    Wrapper that creates a dictionary response  containing 'status' and
    'details'.
    where status can be
        'ok': If wrapped function returns successfully.
        'failed': If wrapped function throws error.
    details is:
        returned value from the wrapped function if no exception is thrown
        else string representation of exception when exception is thrown

    :param func: Function to be wrapped
    :return: dictionary output containing keys 'status' and 'details'
    :rtype: dict
    """

    @wraps(func)
    def inner(*args, **kwargs):
        try:
            return {
                'status': HEALTH_OK,
                'details': func(*args, **kwargs)
            }
        except:
            return {
                'status': HEALTH_FAILED,
                'details': str(sys.exc_info()[1])
            }
    return inner


@_check
def _check_mongo():
    """
    Checks mongo connectivity
    """
    client = MongoClient(MONGO_URL, max_pool_size=1, _connect=False)
    try:
        return client.server_info()
    finally:
        client.close() if client else None


@_check
def _check_celery():
    """
    Checks health for celery integration using ping-pong task output.
    """
    output = ping.delay().get(timeout=10)
    return 'Celery ping:%s' % output


@_check
def _check_elasticsearch():
    """
    Checks elasticsearch health by querying info.
    """
    return get_search_client().info()
