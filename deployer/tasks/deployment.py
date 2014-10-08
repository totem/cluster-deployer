import logging
import time

__author__ = 'sukrit'

"""
Defines celery tasks for deployment
"""

from deployer.celery import app
from conf.appconfig import DEPLOYMENT_DEFAULTS, DEPLOYMENT_TYPE_GITHUB_QUAY, \
    TEMPLATE_DEFAULTS

from deployer.util import dict_merge

logger = logging.getLogger(__name__)


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
