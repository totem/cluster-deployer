import flask
from flask.views import MethodView
from pymongo import MongoClient
import sys
from conf.celeryconfig import MONGO_URL
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
            'celery': _check_celery()
        }
        failed_checks = [
            health_status['status'] for health_status in health.itervalues()
            if health_status['status'] != HEALTH_OK
        ]
        http_status = 200 if not failed_checks else 500
        return flask.jsonify(health), http_status


def register(app):
    app.add_url_rule('/health', view_func=HealthApi.as_view('health'))


def _check_mongo():
    """
    Checks mongo connectivity

    :return: dictionary containing health status and details
    :rtype: dict
    """
    client = MongoClient(MONGO_URL, max_pool_size=1, _connect=False)
    try:
        client.database_names()
        status, details = (HEALTH_OK, 'Successfully retrieved database names')
    except:
        status, details = (HEALTH_FAILED,
                           'Mongo connectivity failed due to: %s' %
                           sys.exc_info()[1])
    finally:
        client.close() if client else None

    return {
        'status': status,
        'details': details
    }


def _check_celery():
    try:
        output = ping.delay().get(timeout=10)
        status, details = (HEALTH_OK, 'Celery ping:%s' % output)
    except:
        status, details = (HEALTH_FAILED,
                           'Celery ping failed due to: %s' % sys.exc_info()[1])
    return {
        'status': status,
        'details': details
    }
