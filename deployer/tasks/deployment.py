import logging
import time
from celery.canvas import group, chain

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
    # result = chain()
    # result.get(propagate=False, timeout=60)
    return chain_tasks.apply_async()


@app.task(name='deployment.wire')
def wire(proxy):
    print(str(proxy))


@app.task(name='deployment.unwire')
def unwire(proxy):
    print(str(proxy))


@app.task(name='deployment.unwire')
def delete(deployment):
    print(str(deployment))


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


@app.task(name='deployment.fleet_deploy')
def fleet_deploy(name, version, template_name, template):
    logger.info('Deploying %s:%s:%s %r', name, version, template_name,
                template)
    if template['service-type'] == 'app1':
        raise ValueError('Hmmmmm')
    time.sleep(1)
    return template_name


@app.task(name='deployment._processed_deployment')
def _processed_templates(template_names, deployment):
    logger.info('Deployed templates %r', template_names)
    return deployment


@app.task(name='deployment._deploy_all')
def _deploy_all(deployment):
    priorities = sorted({template['priority']
                         for template in deployment['templates'].values()
                         if template['enabled']})
    tasks = []
    for priority in priorities:
        fleet_tasks = [
            fleet_deploy.si(deployment['deployment']['name'],
                            deployment['deployment']['version'],
                            template_name, template)
            for template_name, template in deployment['templates'].iteritems()
            if template['priority'] == priority and template['enabled']]
        tasks.append(group(fleet_tasks) | _processed_templates.s(deployment))
    return chain(tasks)()

# @app.task
# def _add(a, b):
#     print(a, b)
#     return a + b
#
# @app.task
# def _add_all(numbers, callback=None):
#     result = sum(numbers)
#     if callback:
#         return callback(result)()
#     else:
#         return result
#
# @app.task
# def _join_sum(results):
#     return sum(results)
#
# @app.task
# def myadd():
#     group1 = group(_add.s(1,2), _add.s(3,4)) | _join_sum.s()
#     group2 = group(_add.s(2), _add.s(4)) | _join_sum.s()
#     return (group1 | group2)()
