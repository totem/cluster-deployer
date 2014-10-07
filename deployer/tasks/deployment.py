import logging

__author__ = 'sukrit'

"""
Defines celery tasks for deployment
"""

from deployer.celery import app
from conf.appconfig import DEPLOYMENT_DEFAULTS

from deployer.util import dict_merge

logger = logging.getLogger(__name__)


def _deployment_defaults(deployment):
    """
    Applies the defaults for the deployment
    :param deployment: Dictionary representing deployment
    :type deployment: dict
    :return: Deployment with defaults applied
    :rtype: dict
    """
    deployment_upd = {}
    if 'deployment' in deployment and 'type' in deployment['deployment'] \
            and deployment['deployment']['type'] in DEPLOYMENT_DEFAULTS:
        deployment_upd = dict_merge(
            deployment, DEPLOYMENT_DEFAULTS[deployment['deployment']['type']])
    deployment_upd = dict_merge(deployment_upd, DEPLOYMENT_DEFAULTS['default'])
    if deployment_upd['deployment']['type'] == 'github-quay':
        deploy_args = deployment_upd['templates']['default-app']['args']
        git_meta = deployment_upd['meta-info']['github']
        deploy_args['image'] = deploy_args['image'] \
            .format(GIT_OWNER=git_meta['owner'],
                    GIT_REPO=git_meta['repo'],
                    GIT_COMMIT=git_meta['commit'])
        deployment_upd['deployment']['name'] = \
            deployment_upd['deployment']['name'] \
            .format(GIT_OWNER=git_meta['owner'],
                    GIT_REPO=git_meta['repo'],
                    GIT_BRANCH=git_meta['branch'])
    return deployment_upd


@app.task(name='deployment.create')
def create(deployment):
    deployment_upd = _deployment_defaults(deployment)
    logger.info(str(deployment_upd))
    return deployment_upd


@app.task(name='deployment.wire')
def wire(proxy):
    print(str(proxy))


@app.task(name='deployment.unwire')
def unwire(proxy):
    print(str(proxy))


@app.task(name='deployment.unwire')
def delete(deployment):
    print(str(deployment))
