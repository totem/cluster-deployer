"""
Defines celery tasks for deployment (e.g.: create, undeploy, wire, unwire)
"""
from deployer.tasks.exceptions import NodeNotRunningException, \
    NodeNotUndeployed

__author__ = 'sukrit'
__all__ = ['create', 'wire', 'unwire', 'delete']

import logging
import time

from celery.canvas import group, chord, chain
from fleet.deploy.deployer import Deployment, status, undeploy, filter_units

from deployer.fleet import get_fleet_provider, jinja_env
from deployer.tasks.util import TaskNotReadyException, simple_result
from deployer.celery import app
from conf.appconfig import DEPLOYMENT_DEFAULTS, DEPLOYMENT_TYPE_GITHUB_QUAY, \
    TEMPLATE_DEFAULTS, TASK_SETTINGS, DEPLOYMENT_MODE_BLUEGREEN, \
    DEPLOYMENT_MODE_REDGREEN

from deployer.util import dict_merge

logger = logging.getLogger(__name__)


@app.task
def create(deployment):
    """
    Task for creating deployment.

    :param deployment: Deployment dictionary.
    :type deployment: dict
    :return: Newly created deploymentS
    :rtype: dict
    """
    # Step1: Apply defaults
    deployment = _deployment_defaults(deployment)

    # Step2: Un-deploy existing versions
    # Step3: Deploy all services for the deployment
    # Note: We will use callback instead of chain as chain of chains do not
    # yield expected results.
    return _pre_create_undeploy.si(
        deployment, _deploy_all.si(deployment))()


@app.task
def wire(proxy):
    print(str(proxy))


@app.task
def unwire(proxy):
    print(str(proxy))


@app.task
def delete(deployment):
    print(str(deployment))


@app.task(bind=True, default_retry_delay=10, max_retries=5)
def _deploy_all(self, deployment):
    """
    Deploys all services for a given deployment
    :param deployment: Deployment parameters
    :type deployment: dict
    :return:
    """
    try:
        deployment = simple_result(deployment)
    except TaskNotReadyException as exc:
        self.retry(exc=exc)

    priorities = sorted({template['priority']
                         for template in deployment['templates'].values()
                         if template['enabled']})
    service_types = {template['service-type'] for template in
                     deployment['templates'].itervalues()
                     if template['enabled']}
    name, version, nodes = deployment['deployment']['name'], \
        deployment['deployment']['version'], \
        deployment['deployment']['nodes']
    return chord(
        group(
            _fleet_deploy.si(name, version, nodes, template_name, template)
            for priority in priorities
            for template_name, template in deployment['templates'].iteritems()
            if template['priority'] == priority and template['enabled']
        ),
        _fleet_check_deploy.si(name, version, nodes, service_types, deployment)
    )()


def _github_quay_defaults(deployment):
    """
    Applies defaults for github-quay deployment
    :param deployment: Deployment that needs to be updated
    :type deployment: dict
    :return: Updated deployment
    :rtype: dict
    """
    deploy_args = deployment['templates']['default-app']['args']
    git_meta = deployment['meta-info']['github']
    deploy_args['image'] = deploy_args['image'] \
        .format(GIT_OWNER=git_meta['owner'],
                GIT_REPO=git_meta['repo'],
                GIT_COMMIT=git_meta['commit'])
    deployment['deployment']['name'] = \
        deployment['deployment']['name'] \
        .format(GIT_OWNER=git_meta['owner'],
                GIT_REPO=git_meta['repo'],
                GIT_BRANCH=git_meta['branch'])
    return deployment


def _deployment_defaults(deployment):
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
            'type': 'default'
        }
    })
    deployment_type = deployment_upd['deployment']['type']

    # Apply defaults
    if deployment_type in DEPLOYMENT_DEFAULTS:
        deployment_upd = dict_merge(deployment_upd,
                                    DEPLOYMENT_DEFAULTS[deployment_type])
    deployment_upd = dict_merge(deployment_upd,
                                DEPLOYMENT_DEFAULTS['default'])

    if deployment_type == DEPLOYMENT_TYPE_GITHUB_QUAY:
        deployment_upd = _github_quay_defaults(deployment_upd)

    for template_name, template in deployment_upd['templates'].iteritems():
        deployment_upd['templates'][template_name] = \
            dict_merge(template, TEMPLATE_DEFAULTS)

    deployment_upd['deployment']['version'] = \
        deployment_upd['deployment']['version'] or \
        int(round(time.time() * 1000))

    return deployment_upd


@app.task
def _fleet_deploy(name, version, nodes, template_name, template):
    logger.info('Deploying %s:%s:%s nodes:%d %r', name, version, template_name,
                nodes, template)
    fleet_deployment = Deployment(
        fleet_provider=get_fleet_provider(), jinja_env=jinja_env, name=name,
        version=version, template=template_name + '.service', nodes=nodes,
        template_args=template['args'], service_type=template['service-type'])
    fleet_deployment.deploy()


@app.task
def _pre_create_undeploy(deployment, callback=None):
    """
    Un-deploys during pre-create phase. The versions un-deployed depends upon
    mode of deployment.
    :param deployment: Deployment parameters
    :type deployment: dict
    :return: deployment to continue deploy chain
    :rtype: dict
    """
    deploy_mode = deployment['deployment']['mode']
    if deploy_mode == DEPLOYMENT_MODE_BLUEGREEN:
        # Undeploy only current version in pre-create phase.
        version = deployment['deployment']['version']
    elif deploy_mode == DEPLOYMENT_MODE_REDGREEN:
        # Undeploy all versions in pre-create phase.
        version = None
    else:
        # Do not undeploy anything when mode is custom or A/B
        return callback()
    name = deployment['deployment']['name']

    undeploy_chain = [
        _fleet_undeploy.si(name, version),
        _wait_for_undeploy.si(name, version)
    ]
    if callback:
        undeploy_chain.append(callback)
    return chain(undeploy_chain)()


@app.task
def _fleet_undeploy(name, version):
    """
    Un-deploys fleet units with matching name and version
    :param name: Name of application
    :param version: Version of application
    :return: None
    """
    undeploy(get_fleet_provider(), name, version)


@app.task(bind=True, default_retry_delay=5, max_retries=5)
def _wait_for_undeploy(self, name, version, ret_value=None):
    """
    Wait for undeploy to finish.
    :param name: Name of application
    :param version : Version of application.
    :param ret_value : Value to be returned on successful call.
    :return: ret_value
    """
    deployed_units = filter_units(get_fleet_provider(), name, version)
    if deployed_units:
        self.retry(exc=NodeNotUndeployed(name, version, deployed_units))
    return ret_value


@app.task(bind=True,
          default_retry_delay=TASK_SETTINGS['DEFAULT_RETRY_DELAY'],
          max_retries=TASK_SETTINGS['DEFAULT_RETRIES'])
def _fleet_check_running(self, name, version, node_num,
                         service_type):
    unit_status = status(get_fleet_provider(), name, version, node_num,
                         service_type)
    logger.info('Status for %s:%s:%d:%s is <%s>', name, version, node_num,
                service_type, unit_status)
    if unit_status == 'running':
        return
    else:
        self.retry(exc=NodeNotRunningException(name, version, node_num,
                                               service_type, unit_status))


@app.task
def _fleet_unit_deployed(name, version, node_num, service_type):
    logger.info('Unit deployed successfully %s:%s:%d:%s ', name,
                version, node_num, service_type)
    return 'Unit deployed successfully %s:%s:%d:%s ' % (name, version,
                                                        node_num, service_type)


@app.task
def _fleet_check_unit(name, version, node_num, service_type):
    return (
        _fleet_check_running.si(name, version, node_num, service_type) |
        _fleet_unit_deployed.si(name, version, node_num, service_type)
    )()


@app.task
def _fleet_check_deploy(name, version, nodes, service_types, deployment):
    return chord(
        group(
            _fleet_check_unit.si(name, version, node_num, service_type)
            for service_type in service_types
            for node_num in range(1, nodes + 1)
        ),
        _processed_deploy.s(name, version, nodes, deployment)
    )()


@app.task(bind=True, default_retry_delay=TASK_SETTINGS['DEFAULT_RETRY_DELAY'],
          max_retries=TASK_SETTINGS['DEFAULT_RETRIES'])
def _processed_deploy(self, results, name, version, nodes, deployment):
    try:
        extracted_results = simple_result(results)
    except TaskNotReadyException as exc:
        self.retry(exc=exc)

    logger.info('Processed: %s:%s for %d nodes. result:%s', name, version,
                nodes,
                extracted_results)
    return deployment
