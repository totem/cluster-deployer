import logging
import time
from celery.canvas import group, chain, chord
from fleet.deploy.deployer import Deployment, status, undeploy
from deployer.fleet import get_fleet_provider, jinja_env
from deployer.tasks import util
from deployer.tasks.util import TaskNotReadyException, simple_group_results

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
    chain_tasks = _deployment_defaults.s(deployment) | \
                  _fleet_undeploy.s(all_versions=True) | \
                  _deploy_all.s() | \
                  _processed_deployment.s()
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


@app.task(name='deployment._deploy_priority')
def _deploy_priority(deployment, priority):
    name, version, nodes = deployment['deployment']['name'], \
                           deployment['deployment']['version'], \
                           deployment['deployment']['nodes']
    fleet_tasks = [
        _fleet_deploy.si(name, version, nodes, template_name, template) |
        _fleet_check_all_running.si(name, version, nodes,
                                    template['service-type'])
        for template_name, template in deployment['templates'].iteritems()
        if template['priority'] == priority and template['enabled']]
    return chord(group(fleet_tasks), _processed_priority.s(deployment,
                                                            priority))()



@app.task(name='deployment._deploy_all')
def _deploy_all(deployment):
    priorities = sorted({template['priority']
                         for template in deployment['templates'].values()
                         if template['enabled']})
    return chain([_deploy_priority.si(deployment, priority)
                  for priority in priorities])()


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


@app.task(name='deployment._fleet_deploy')
def _fleet_deploy(name, version, nodes, template_name, template):
    logger.info('Deploying %s:%s:%s nodes:%d %r', name, version, template_name,
                nodes, template)
    fleet_deployment = Deployment(
        fleet_provider=get_fleet_provider(), jinja_env=jinja_env, name=name,
        version=version, template=template_name+'.service', nodes=nodes,
        template_args=template['args'], service_type=template['service-type'])
    fleet_deployment.deploy()


@app.task(name='deployment._fleet_undeploy')
def _fleet_undeploy(deployment, all_versions=False):
    version = deployment['deployment']['version'] if not all_versions else None
    undeploy(get_fleet_provider(), deployment['deployment']['name'], version)
    time.sleep(10)
    return deployment


@app.task(name='deployment._fleet_status', default_retry_delay=30, bind=True,
          max_retries=2)
def _fleet_check_running(self, name, version, node_num,
                         service_type):
    # raise NodeNotRunningException
    # return '%s:%s:%d:%s is running' % (name, version, node_num, service_type)
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
def _fleet_check_all_running(name, version, nodes,
                             service_type):
    return group(
        [_fleet_check_running.si(name, version, node_num, service_type)
         for node_num in range(1, nodes+1)])()

@app.task(name='deployment._processed_priority', default_retry_delay=30,
          bind=True, max_retries=2)
def _processed_priority(self, results, deployment, priority):
    try:
        results = simple_group_results(results)
    except TaskNotReadyException as exc:
        self.retry(exc=exc)
    logger.info('Processed priority: %d for deployment %r  %r', priority,
                deployment, results)
    return deployment

@app.task
def _processed_deployment(deployment):
    logger.info('Processed deployment %r', deployment)
    return deployment


class NodeNotRunningException(Exception):
    def __init__(self, name, version, node_num, service_type, status,
                 retryable=True, expected_status='running'):
        self.name = name
        self.version = version
        self.node_num = node_num
        self.service_type = service_type
        self.status = status
        self.retryable = retryable
        self.expected_status = expected_status
        super(NodeNotRunningException,self).__init__(
            name, version, node_num, service_type, status, retryable)

    def to_dict(self):
        return {
            'message': 'Status for application:%s version:%s node_num:%d '
                       'service_type:%s is %s instead of %s' %
                       (self.name, self.version, self.node_num,
                        self.service_type, self.unit_status,
                        self.expected_status),
            'code': 'NODE_NOT_RUNNING',
            'details': {
                'name': self.name,
                'version': self.version,
                'node_num': self.node_num,
                'service_type': self.service_type,
                'status': self.status,
                'expected_status': self.expected_status
            },
            'retryable': self.retryable
        }


