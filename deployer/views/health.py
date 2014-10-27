from functools import wraps
import flask
from flask.views import MethodView
from pymongo import MongoClient
import sys
from conf.celeryconfig import MONGO_URL
from deployer.elasticsearch import get_search_client
from deployer.tasks.common import ping

HEALTH_OK = 'ok'
HEALTH_FAILED = 'failed'


class HealthApi(MethodView):
    """
    API for getting system health.
    """

    def get(self):
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
    app.add_url_rule('/health', view_func=HealthApi.as_view('health'))


def _check(func):

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
        client.database_names()
        return 'Successfully retrieved database names'
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
