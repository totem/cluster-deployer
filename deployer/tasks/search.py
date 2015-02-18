"""
Module for updating/searching elastic search.
"""
import copy
import datetime
from conf.appconfig import DEPLOYMENT_STATE_PROMOTED, \
    DEPLOYMENT_STATE_DECOMMISSIONED, DEPLOYMENT_STATE_STARTED

from deployer.celery import app
from deployer.elasticsearch import deployment_search
from deployer.util import dict_merge


TYPE_DEPLOYMENTS = 'deployments'
TYPE_EVENTS = 'events'

EVENT_NEW_DEPLOYMENT = 'NEW_DEPLOYMENT'
EVENT_ACQUIRED_LOCK = 'ACQUIRED_LOCK'
EVENT_UNDEPLOYED_EXISTING = 'UNDEPLOYED_EXISTING'
EVENT_UNITS_ADDED = 'UNITS_ADDED'
EVENT_UNITS_STARTED = 'UNITS_STARTED'
EVENT_UNITS_DEPLOYED = 'UNITS_DEPLOYED'
EVENT_NODES_DISCOVERED = 'NODES_DISCOVERED'
EVENT_WIRED = 'WIRED'
EVENT_UPSTREAMS_REGISTERED = 'UPSTREAMS_REGISTERED'
EVENT_PROMOTED = 'PROMOTED'
EVENT_DEPLOYMENT_FAILED = 'DEPLOYMENT_FAILED'


def massage_config(config):
    """
    massages config for indexing.
    1. Removes encrypted parameters from indexing.
    2. Extracts raw parameter for value types.

    :param config: dictionary that needs to be massaged
    :type config: dict
    :return: massaged config
    :rtype: dict
    """

    if hasattr(config, 'items'):
        if 'value' in config:

            if config.get('encrypted', False):
                return ''
            else:
                return str(config.get('value'))
        else:
            return {
                k: massage_config(v) for k, v in config.items()
            }
    elif isinstance(config, (list, set, tuple)):
        return [massage_config(v) for v in config]
    else:
        return config


@app.task
@deployment_search
def index_deployment(deployment, es=None, idx=None):
    """
    Creates a new deployment
    :param deployment: Dictionary containing deployment parameters
    """
    return es.index(idx, TYPE_DEPLOYMENTS, massage_config(deployment),
                    id=deployment['id'])


@app.task
@deployment_search
def update_deployment_state(id, state, ret_value=None, es=None, idx=None):
    """
    Updates the deployment state

    :param id: Id for the deployment
    :param state: State for the deployment
    :keyword ret_value: Value to be returned. If None, the updated search
     document is returned.
    """
    updated_doc = es.update(idx, TYPE_DEPLOYMENTS, id, body={
        'doc': {
            'state': state
        }
    })
    return ret_value or updated_doc


def create_search_parameters(deployment, defaults=None):
    """
    Creates search parameters for a given deployment.

    :param deployment: Dictionary containing deployment parameters.
    :type deployment: dict
    :return: Dictionary containing search parameters
    :rtype: dict
    """

    deployment = dict_merge(deployment or {}, defaults or {}, {
        'meta-info': {}
    })
    return {
        'meta-info': copy.deepcopy(deployment['meta-info']),
        'deployment': {
            'name': deployment['deployment']['name'],
            'version': deployment['deployment']['version'],
            'id': deployment['id']
        }
    }


@app.task
@deployment_search
def add_search_event(event_type, details=None, search_params={}, es=None,
                     idx=None):
    event_upd = copy.deepcopy(search_params)
    event_upd.update({
        'type': event_type,
        'details': massage_config(details),
        'date': datetime.datetime.utcnow(),
    })
    return es.create(idx, TYPE_EVENTS, event_upd)


@app.task
def add_search_event_details(details, event_type, search_params):
    """
    Adds search event with return value.

    :param details:
    :param event_type:
    :param search_params:
    :return:
    """
    return add_search_event.si(
        event_type, search_params=search_params, details=details)()


@deployment_search
def find_apps(es=None, idx=None):
    results = es.search(idx, doc_type=TYPE_DEPLOYMENTS, body={
        'size': 0,
        'aggs': {
            'apps': {
                'terms': {
                    'field': 'deployment.name'
                }
            }
        }
    })
    return [bucket['key'] for bucket in
            results['aggregations']['apps']['buckets']]


@app.task
@deployment_search
def get_promoted_deployments(name, version=None, es=None, idx=None):
    query = {
        # Not expecting more than 1000 promoted deployments for a given app
        'size': 1000,
        "fields": [],
        "filter": {
            "and": [
                {"term": {"deployment.name": name}},
                {"term": {"deployment.version": version}} if version else {},
                {"term": {"state": DEPLOYMENT_STATE_PROMOTED}}

            ]
        }
    }
    results = es.search(idx, TYPE_DEPLOYMENTS, body=query)

    return [hit['_id'] for hit in results['hits']['hits']]


@app.task
@deployment_search
def mark_decommissioned(ids, es=None, idx=None):
    if ids:
        body = list()
        for _id in ids:
            body += [
                {'update': {'_id': _id}},
                {'doc': {'state': DEPLOYMENT_STATE_DECOMMISSIONED}}
            ]
        return es.bulk(body, index=idx, doc_type=TYPE_DEPLOYMENTS)


@deployment_search
def find_deployments(name, version=None, page=0, size=10, es=None, idx=None):
    query = {
        "size": size,
        "from": page,
        "filter": {
            "and": [
                {"term": {"deployment.name": name}},
                {"term": {"deployment.version": version}} if version else {}
            ]
        }
    }
    results = es.search(idx, TYPE_DEPLOYMENTS, body=query)
    return [hit['_source'] for hit in results['hits']['hits']]


@deployment_search
def find_running_deployments(name, version=None, page=0, size=10, es=None,
                             idx=None):
    query = {
        "size": size,
        "from": page,
        "filter": {
            "and": [
                {"term": {"deployment.name": name}},
                {"term": {"deployment.version": version}} if version else {},
                {"terms": {"state": [DEPLOYMENT_STATE_PROMOTED,
                                     DEPLOYMENT_STATE_STARTED]}}
            ]
        }
    }
    results = es.search(idx, TYPE_DEPLOYMENTS, body=query)
    return [hit['_source'] for hit in results['hits']['hits']]
