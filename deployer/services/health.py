from functools import wraps
import logging
import sys
from etcd import client
from conf.appconfig import HEALTH_OK, HEALTH_FAILED, TOTEM_ETCD_SETTINGS
from deployer.services.storage.factory import get_store
from deployer.tasks.common import ping
from deployer.util import timeout

HEALTH_TIMEOUT_SECONDS = 10

log = logging.getLogger(__name__)


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
            log.exception('Health check failed')
            return {
                'status': HEALTH_FAILED,
                'details': str(sys.exc_info()[1])
            }
    return inner


@timeout(HEALTH_TIMEOUT_SECONDS)
@_check
def _check_etcd():
    etcd_cl = client.Client(
        host=TOTEM_ETCD_SETTINGS['host'],
        port=TOTEM_ETCD_SETTINGS['port'])
    return {
        'machines': etcd_cl.machines
    }


@timeout(HEALTH_TIMEOUT_SECONDS)
@_check
def _check_store():
    """
    Checks health of default store
    """
    return get_store().health()


@timeout(HEALTH_TIMEOUT_SECONDS)
@_check
def _check_celery():
    """
    Checks health for celery integration using ping-pong task output.
    """
    output = ping.delay().get(timeout=HEALTH_TIMEOUT_SECONDS)
    return 'Celery ping:%s' % output


def get_health(check_celery=True):
    """
    Gets the health of the all the external services.

    :return: dictionary with
        key: service name like etcd, celery, elasticsearch
        value: dictionary of health status
    :rtype: dict
    """

    health_status = {
        'etcd': _check_etcd(),
        'store': _check_store()
    }
    if check_celery:
        health_status['celery'] = _check_celery()
    return health_status
