import copy
import json
import logging
import time
import datetime
from fleet.deploy.deployer import filter_units
from conf.appconfig import CLUSTER_NAME, DEPLOYMENT_TYPE_GIT_QUAY, \
    DEPLOYMENT_DEFAULTS, TEMPLATE_DEFAULTS, \
    DEPLOYMENT_STATE_STARTED, UPSTREAM_DEFAULTS, DEPLOYMENT_TYPE_DEFAULT, \
    DISCOVER_UPSTREAM_TTL_DEFAULT
from deployer.fleet import get_fleet_provider
from deployer.services.proxy import get_discovered_nodes
from deployer.services.storage.factory import get_store
from deployer.util import dict_merge, to_milliseconds

__author__ = 'sukrit'

"""
Performs service operations related to deploment
"""

logger = logging.getLogger(__name__)


def get_exposed_ports(deployment):
    """
    Gets exposed ports for the given deployment

    :param deployment: Dictionary representing deployment
    :type deployment: dict
    :return: Sorted list of unique exposed ports
    :rtype: list
    """
    return sorted(
        {location.get('port')
         for host in deployment.get('proxy', {}).get('hosts', {}).values()
         for location in host.get('locations', {}).values()} |
        {listener.get('upstream-port')
         for listener in deployment.get('proxy', {}).get('listeners', {})
            .values()
         }
    )


def fetch_runtime_upstreams(deployment):
    """
    Fetches runtime upstream information for a given deployment
    (includes meta-information about the upstream)

    :return:
    """
    app_name = deployment['deployment']['name']
    version = deployment['deployment']['version']
    mode = deployment['deployment'].get('mode')
    ports = get_exposed_ports(deployment)
    return {
        str(port): [dict_merge({'name': name}, upstream) for name, upstream in
                    get_discovered_nodes(
                        app_name, version, port, mode, with_meta=True).items()]
        for port in ports
    }


def fetch_runtime_units(app_name, version=None, exclude_version=None):
    """
    Returns provide specific units runtime info
    :param deployment:
    :return:
    """

    return filter_units(get_fleet_provider(), app_name, version,
                        exclude_version)


def sync_upstreams(deployment_id, ignore_error=True):
    """
    Synchronizes runtime upstream information for given deployment

    :param deployment_id: Id of the deployment
    :type deployment_id: str
    :keyword ignore_error: Ignore error during sync
    :type ignore_error: bool
    :return: None
    """
    store = get_store()
    output = {
        'deployment_id': deployment_id,
    }
    deployment = store.get_deployment(deployment_id)
    if deployment:
        try:
            upstreams = fetch_runtime_upstreams(deployment)
            store.update_runtime_upstreams(deployment_id, upstreams)
            output.update(upstreams=upstreams, state='success')
        except Exception as exception:
            logger.exception('Unknown error took place while trying to sync '
                             'units for deployment: %s', deployment_id)
            if not ignore_error:
                raise
            output.update(error=str(exception), state='failed')

    return output


def sync_units(deployment_id, ignore_error=True):
    """
    Synchronizes runtime units information for given deployment

    :param deployment_id: Id of the deployment
    :type deployment_id: str
    :keyword ignore_error: Ignore error during sync
    :type ignore_error: bool
    :return: None
    """
    store = get_store()
    output = {
        'deployment_id': deployment_id,
    }
    deployment = store.get_deployment(deployment_id)
    if deployment:
        try:
            units = fetch_runtime_units(deployment['deployment']['name'],
                                        deployment['deployment']['version'])
            store.update_runtime_units(deployment_id, units)
            output.update(units=units, state='success')
        except Exception as exception:
            logger.exception('Unknown error took place while trying to sync '
                             'units for deployment: %s', deployment_id)
            if not ignore_error:
                raise
            return {
                'deployment_id': deployment_id,
                'state': 'failed',
                'error': str(exception)
            }
    return output


def generate_deployment_id(app_name, app_version):
    """
    Generated deployment id for given application name and version

    :param app_name: Application name
    :type app_name: str
    :param app_version: Application version
    :type app_version: str
    :return: Deployment id
    :rtype: str
    """
    return '{}-{}-{}'.format(CLUSTER_NAME, app_name, app_version)


def _git_quay_defaults(deployment):
    """
    Applies defaults for git-quay deployment

    :param deployment: Deployment that needs to be updated
    :type deployment: dict
    :return: Updated deployment
    :rtype: dict
    """
    deploy_args = deployment['templates']['app']['args']
    git_meta = deployment['meta-info']['git']
    deploy_args['image'] = deploy_args['image'] \
        .format(GIT_OWNER=git_meta['owner'],
                GIT_REPO=git_meta['repo'],
                GIT_COMMIT=git_meta['commit'])
    deployment['deployment']['name'] = deployment['deployment']['name']\
        .format(GIT_OWNER=git_meta['owner'],
                GIT_REPO=git_meta['repo'],
                GIT_REF=git_meta['ref'])
    return deployment


def _create_discover_check(deployment):
    """
    Creates the dictionary to be used by discover for health check

    :param deployment:
    :return:
    """
    return {
        port: upstream.get('health', {}) for port, upstream in
        deployment.get('proxy', {}).get('upstreams', {}).iteritems()
    }


def _get_app_environment(deployment, exposed_ports):
    app_template = deployment.get('templates').get('app')
    discover = {
        'DISCOVER_PORTS': ','.join([str(port) for port in exposed_ports]),
        'DISCOVER_MODE': deployment['deployment']['mode'],
        'DISCOVER_HEALTH': json.dumps(
                _create_discover_check(deployment)),
        'DISCOVER_UPSTREAM_TTL': DISCOVER_UPSTREAM_TTL_DEFAULT
    }
    return dict_merge(app_template['args']['environment'],
                      deployment.get('environment'), discover)


def apply_defaults(deployment):
    """
    Applies the defaults for the deployment

    :param deployment: Dictionary representing deployment
    :type deployment: dict
    :return: Deployment with defaults applied
    :rtype: dict
    """

    # Set the default deployment type.
    deployment_upd = dict_merge(deployment, {
        'deployment': {
            'type': DEPLOYMENT_TYPE_GIT_QUAY
        }
    })
    deployment_type = deployment_upd['deployment']['type']

    # Apply defaults
    if deployment_type in DEPLOYMENT_DEFAULTS:
        deployment_upd = dict_merge(deployment_upd,
                                    DEPLOYMENT_DEFAULTS[deployment_type])
    deployment_upd = dict_merge(deployment_upd,
                                DEPLOYMENT_DEFAULTS['default'])

    if deployment_type == DEPLOYMENT_TYPE_GIT_QUAY:
        deployment_upd = _git_quay_defaults(deployment_upd)

    for template_name, template in deployment_upd['templates'].iteritems():
        deployment_upd['templates'][template_name] = \
            dict_merge(template, TEMPLATE_DEFAULTS)

    deployment_upd['deployment']['version'] = \
        deployment_upd['deployment']['version'] or \
        int(round(time.time() * 1000))

    deployment_upd['deployment']['version'] = \
        str(deployment_upd['deployment']['version'])

    # Set the deployment identifier.  We will use deployment name and version
    # as unique identifier as there can only be one deployment with same name
    # and version
    app_name = deployment_upd['deployment']['name']
    app_version = deployment_upd['deployment']['version']
    deployment_upd['id'] = generate_deployment_id(app_name, app_version)
    deployment_upd['state'] = DEPLOYMENT_STATE_STARTED
    deployment_upd['started-at'] = datetime.datetime.utcnow()

    app_template = deployment_upd.get('templates').get('app')
    exposed_ports = get_exposed_ports(deployment_upd)

    # Create default upstreams (using exposed ports)
    for port in exposed_ports:
        deployment_upd['proxy']['upstreams'].setdefault(str(port), {})

    # Apply proxy defaults
    for upstream_name, upstream in deployment_upd['proxy']['upstreams'] \
            .iteritems():
        upd_upstream = dict_merge(upstream, UPSTREAM_DEFAULTS)
        if upd_upstream.get('mode') != 'http' and \
                upd_upstream['health'].get('uri'):
            del(upd_upstream['health']['uri'])
        deployment_upd['proxy']['upstreams'][upstream_name] = upd_upstream

    if app_template:
        app_template['args']['environment'] = _get_app_environment(
            deployment_upd, exposed_ports)
        sidekicks = [service_type for service_type, template in
                     deployment_upd['templates'].iteritems()
                     if template['enabled'] and service_type != 'app']
        app_template['args']['sidekicks'] = sidekicks
        timeout_stop = deployment_upd['deployment']['stop']['timeout'] or \
            DEPLOYMENT_DEFAULTS[DEPLOYMENT_TYPE_DEFAULT]['deployment']['stop']
        ['timeout']
        timeout_stop_sec = to_milliseconds(timeout_stop) / 1000
        app_template['args']['service'] = dict_merge(
            app_template['args'].get('service') or {},
            {
                'container-stop-sec': timeout_stop_sec
            }
        )

    # Override/Set Clustername
    deployment_upd['cluster'] = CLUSTER_NAME

    # Reset runtime if it exists
    deployment_upd['runtime'] = {}
    return deployment_upd


def clone_deployment(deployment):
    """
    Clones existing deployment and udpates settings for creating new deploy

    :param deployment: Deployment parameters
    :type deployment: dict
    :return:
    """
    deployment_upd = copy.deepcopy(deployment)
    if (deployment_upd and deployment_upd.get('deployment') and
            deployment_upd.get('deployment').get('version')):
        # We want to create new deployment version
        del(deployment_upd['deployment']['version'])
    return deployment_upd
