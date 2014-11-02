from __future__ import absolute_import
from functools import wraps
from elasticsearch import Elasticsearch
from conf.appconfig import SEARCH_SETTINGS


def deployment_search(fun):
    """
    Function wrapper that automatically passes elastic search instance to
    wrapped function if search is enabled.
    If search is disabled, it skips the call to the search function and returns
    {"skip_search": True}

    :param fun: Function to be wrapped
    :return: Wrapped function.
    """
    @wraps(fun)
    def outer(*args, **kwargs):
        if SEARCH_SETTINGS['enabled']:
            kwargs.setdefault('es', get_search_client())
            kwargs.setdefault('idx', SEARCH_SETTINGS['default-index'])
            return fun(*args, **kwargs)
        else:
            return {
                'skip_search': True
            }
    return outer


def get_search_client():
    """
    Creates the elasticsearch client instance using SEARCH_SETTINGS

    :return: Instance of Elasticsearch
    :rtype: elasticsearch.Elasticsearch
    """
    return Elasticsearch(hosts=SEARCH_SETTINGS['host'],
                         port=SEARCH_SETTINGS['port'])
