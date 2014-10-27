"""
Module for updating/searching elastic search.
"""
from functools import wraps
from elasticsearch import Elasticsearch
from conf.appconfig import SEARCH_SETTINGS
from deployer.celery import app

TYPE_DEPLOYMENTS = 'deployments'


def _get_search_client():
    """
    Creates the elasticsearch client instance use SEARCH_SETTINGS

    :return: Instance of Elasticsearch
    :rtype: elasticsearch.Elasticsearch
    """
    return Elasticsearch(hosts=SEARCH_SETTINGS['host'],
                         port=SEARCH_SETTINGS['port'])


def _deployment_search(fun):
    @wraps(fun)
    def outer(*args, **kwargs):
        kwargs.setdefault('es', _get_search_client())
        kwargs.setdefault('idx', SEARCH_SETTINGS['default-index'])
        return fun(*args, **kwargs)
    return outer


@app.task
@_deployment_search
def index_deployment(deployment, es=None, idx=None):
    """
    Creates a new deployment
    :param deployment: Dictionary containing deployment parameters
    """
    return es.index(idx, TYPE_DEPLOYMENTS, deployment, id=deployment['id'])


@app.task
@_deployment_search
def update_deployment_state(id, state, ret_value=None, es=None, idx=None):
    """
    Updates the deployment state

    :param id: Id for the deployment
    :param state: State for the deployment
    :keyword ret_value: Value to be returned. If None, the updated search
     document is returned.
    """
    es = _get_search_client()
    updated_doc = es.update(idx, TYPE_DEPLOYMENTS, id, body={
        'doc': {
            'state': state
        }
    })
    return ret_value or updated_doc