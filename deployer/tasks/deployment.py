import logging
import time
from celery.canvas import group, chain
from fleet.deploy.deployer import Deployment, status
from deployer.fleet import get_fleet_provider, jinja_env

__author__ = 'sukrit'

"""
Defines celery tasks for deployment
"""

__all__ = ['create', 'wire', 'unwire', 'delete']

from deployer.celery import app
from conf.appconfig import DEPLOYMENT_DEFAULTS, DEPLOYMENT_TYPE_GITHUB_QUAY, \
    TEMPLATE_DEFAULTS

from deployer.util import dict_merge

logger = logging.getLogger(__name__)


@app.task(name='deployment.create')
def create(deployment):
    chain_tasks = _deployment_defaults.s(deployment) | _deploy_all.s()
    return chain_tasks()


@app.task(name='deployment.wire')
def wire(proxy):
    print(str(proxy))


@app.task(name='deployment.unwire')
def unwire(proxy):
    print(str(proxy))


@app.task(name='deployment.unwire')
def delete(deployment):
    print(str(deployment))


@app.task(name='deployment._deploy_all')
def _deploy_all(deployment):
    priorities = sorted({template['priority']
                         for template in deployment['templates'].values()
                         if template['enabled']})
    tasks = []
    name, version, nodes = deployment['deployment']['name'], \
        deployment['deployment']['version'], \
        deployment['deployment']['nodes']
    for priority in priorities:
        fleet_tasks = [
            _fleet_deploy.si(name, version, nodes, template_name, template) |
            _fleet_check_all_running.si(name, version, nodes,
                                        template['service-type'])
            for template_name, template in deployment['templates'].iteritems()
            if template['priority'] == priority and template['enabled']]
        tasks.append(group(fleet_tasks) | _processed_templates.si(deployment))
    return chain(tasks)()


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


@app.task(name='deployment._deployment_defaults')
def _deployment_defaults(deployment):
    """
    Applies the defaults for the deployment
    :param deployment: Dictionary representing deployment
    :type deployment: dict
    :return: Deployment with defaults applied
    :rtype: dict
    """
    # Set the default deployment type
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


@app.task(name='deployment._fleet_deploy', ignore_result=True)
def _fleet_deploy(name, version, nodes, template_name, template):
    logger.info('Deploying %s:%s:%s nodes:%d %r', name, version, template_name,
                nodes, template)
    fleet_deployment = Deployment(
        fleet_provider=get_fleet_provider(), jinja_env=jinja_env, name=name,
        version=version, template=template_name+'.service',
        template_args=template['args'], service_type=template['service-type'])
    fleet_deployment.deploy()

def _fleet_undeploy(name, version):
    pass


@app.task(name='deployment._fleet_status', default_retry_delay=20, bind=True,
          max_retries=15, ignore_result=True)
def _fleet_check_running(self, name, version, node_num,
                         service_type):
    # raise NodeNotRunningException
    # return '%s:%s:%d:%s is running' % (name, version, node_num, service_type)
    try:
        if status(get_fleet_provider(), name, version, node_num, service_type)\
                is not 'running':
            raise NodeNotRunningException()
    except NodeNotRunningException as exc:
        self.retry(exc=exc)

@app.task
def _fleet_check_all_running(name, version, nodes,
                             service_type):
    return group(
        [_fleet_check_running.si(name, version, node_num, service_type)
         for node_num in range(1, nodes+1)])()


@app.task(name='deployment._processed_deployment')
def _processed_templates(deployment):
    logger.info('_processed_templates for deployment %r', deployment)
    return deployment


class NodeNotRunningException(Exception):
    pass
