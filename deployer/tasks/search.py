"""
Module for updating/searching elastic search.
"""
import copy
import datetime

from deployer.celery import app
from deployer.elasticsearch import deployment_search


TYPE_DEPLOYMENTS = 'deployments'
TYPE_EVENTS = 'events'

EVENT_NEW_DEPLOYMENT = 'NEW_DEPLOYMENT'
EVENT_ACQUIRED_LOCK = 'ACQUIRED_LOCK'
EVENT_UNDEPLOYED_EXISTING = 'UNDEPLOYED_EXISTING'
EVENT_UNITS_ADDED = 'UNITS_ADDED'
EVENT_UNITS_DEPLOYED = 'UNITS_DEPLOYED'
EVENT_WIRED = 'WIRED'
EVENT_PROMOTED = 'PROMOTED'
EVENT_DEPLOYMENT_FAILED = 'DEPLOYMENT_FAILED'


@app.task
@deployment_search
def index_deployment(deployment, es=None, idx=None):
    """
    Creates a new deployment
    :param deployment: Dictionary containing deployment parameters
    """
    return es.index(idx, TYPE_DEPLOYMENTS, deployment, id=deployment['id'])


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


def create_search_parameters(deployment):
    """
    Creates search parameters for a given deployment.

    :param deployment: Dictionary containing deployment parameters.
    :type deployment: dict
    :return: Dictionary containing search parameters
    :rtype: dict
    """
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
        'details': details,
        'date': datetime.datetime.utcnow(),
    })
    return es.create(idx, TYPE_EVENTS, event_upd)


# def create_deployment_event(deployment, event_type, details=None):
#     """
#     Creates deployment event from a given deployment object, event type and
#     event details
#
#     :param deployment: dict containing deployment attributes
#     :type deployment: dict
#     :param event_type: Type of event
#     :type event_type: str
#     :param details: Event details
#     :type details: dict or any Json Serializable object.
#     :return: Deployment event
#     :rtype: dict
#     """
#     return {
#         'meta-info': copy.deepcopy(deployment['meta-info']),
#         'deployment': {
#             'name': deployment['deployment']['name'],
#             'version': deployment['deployment']['version'],
#             'id': deployment['id']
#         },
#         'type': event_type,
#         'date': datetime.datetime.utcnow(),
#         'details': details
#     }


# @app.task
# @deployment_search
# def add_search_event(event, es=None, idx=None):
#     """
#     Adds deployment event to search.
#     :param event:
#     :param es:
#     :param idx:
#     :return:
#     """
#     return es.create(idx, TYPE_EVENTS, event)
