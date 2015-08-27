import logging
from fleet.deploy.deployer import filter_units
from conf.appconfig import CLUSTER_NAME
from deployer.fleet import get_fleet_provider
from deployer.services.proxy import get_discovered_nodes
from deployer.services.storage.factory import get_store
from deployer.util import dict_merge

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
    :return: Sorteed list of unique exposed ports
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
        str(port): get_discovered_nodes(app_name, version, port, mode,
                                        with_meta=True)
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


def sync_upstreams(deployment_id):
    """
    Synchronizes runtime upstream information for given deployment

    :param deployment_id: Id of the deployment
    :type deployment_id: str
    :return: None
    """
    store = get_store()
    deployment = store.get_deployment(deployment_id)
    if deployment:
        upstreams = [dict_merge({'name': name}, upstream) for name, upstream in
                     fetch_runtime_upstreams(deployment).items()]
        store.update_runtime_upstreams(deployment_id, upstreams)


def sync_units(deployment_id):
    """
    Synchronizes runtime units information for given deployment

    :param deployment_id: Id of the deployment
    :type deployment_id: str
    :return: None
    """
    store = get_store()
    deployment = store.get_deployment(deployment_id)
    if deployment:
        units = fetch_runtime_units(deployment['deployment']['name'],
                                    deployment['deployment']['version'])
        store.update_runtime_units(deployment_id, units)


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
