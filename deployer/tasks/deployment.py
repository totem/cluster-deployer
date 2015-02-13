"""
Defines celery tasks for deployment (e.g.: create, undeploy, wire, unwire)
"""
import copy
import datetime
import json
import socket
from fabric.exceptions import NetworkError
from fleet.client.fleet_fabric import FleetExecutionException
from paramiko import SSHException
from deployer.services.distributed_lock import LockService, \
    ResourceLockedException
from deployer.services.security import decrypt_config
from deployer.tasks.exceptions import NodeNotUndeployed, MinNodesNotRunning

from deployer.tasks.search import index_deployment, update_deployment_state, \
    EVENT_NEW_DEPLOYMENT, \
    EVENT_ACQUIRED_LOCK, \
    EVENT_UNDEPLOYED_EXISTING, EVENT_UNITS_DEPLOYED, \
    EVENT_PROMOTED, EVENT_DEPLOYMENT_FAILED, create_search_parameters, \
    add_search_event, EVENT_WIRED, EVENT_UNITS_ADDED, \
    get_promoted_deployments, mark_decommissioned, EVENT_UNITS_STARTED, \
    EVENT_UPSTREAMS_REGISTERED, EVENT_NODES_DISCOVERED, \
    add_search_event_details

__author__ = 'sukrit'
__all__ = ['create', 'delete']

import logging
import time

from celery.canvas import group, chord, chain

from deployer.fleet import get_fleet_provider, jinja_env
from fleet.deploy.deployer import Deployment, undeploy, filter_units

from deployer.celery import app
from conf.appconfig import DEPLOYMENT_DEFAULTS, DEPLOYMENT_TYPE_GIT_QUAY, \
    TEMPLATE_DEFAULTS, TASK_SETTINGS, DEPLOYMENT_MODE_BLUEGREEN, \
    DEPLOYMENT_MODE_REDGREEN, DEPLOYMENT_STATE_STARTED, \
    DEPLOYMENT_STATE_FAILED, DEPLOYMENT_STATE_PROMOTED, UPSTREAM_DEFAULTS

from deployer.tasks.common import async_wait
from deployer.tasks.proxy import wire_proxy, register_upstreams, \
    _check_discover

from deployer.util import dict_merge

logger = logging.getLogger(__name__)

RETRYABLE_FLEET_EXCEPTIONS = (SSHException, EOFError, NetworkError,
                              socket.error, FleetExecutionException)


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

    # Step2: Apply Lock
    # Step3: Un-deploy existing versions
    # Step4: Deploy all services for the deployment
    # Step5: Release lock

    # Note: We will use callback instead of chain as chain of chains do not
    # yield expected results.

    search_params = create_search_parameters(deployment)
    app_name = deployment['deployment']['name']
    app_version = deployment['deployment']['version']
    nodes = deployment['deployment']['nodes']
    min_nodes = deployment['deployment'].get('check', {}).get(
        'min-nodes', nodes)
    check_port = deployment['deployment'].get('check', {}).get('port')
    deployment_mode = deployment['deployment']['mode']
    return (
        index_deployment.si(deployment) |
        add_search_event.si(EVENT_NEW_DEPLOYMENT, details=deployment,
                            search_params=search_params) |
        _using_lock.si(
            search_params,
            app_name,
            do_task=_pre_create_undeploy.si(
                deployment,
                search_params,
                next_task=register_upstreams.si(
                    app_name,
                    app_version,
                    upstreams=deployment['proxy']['upstreams'],
                    deployment_mode=deployment_mode) |
                add_search_event.si(
                    EVENT_UPSTREAMS_REGISTERED, search_params=search_params) |
                _deploy_all.si(deployment, search_params) |
                async_wait.s(
                    default_retry_delay=TASK_SETTINGS[
                        'DEPLOYMENT_WAIT_RETRY_DELAY'],
                    max_retries=TASK_SETTINGS['DEPLOYMENT_WAIT_RETRIES']
                ) |
                add_search_event_details.s(EVENT_UNITS_DEPLOYED,
                                           search_params=search_params) |
                _check_discover.si(app_name, app_version, check_port,
                                   min_nodes, deployment_mode) |
                add_search_event_details.s(EVENT_NODES_DISCOVERED,
                                           search_params=search_params) |
                _promote_deployment.si(deployment, search_params)
            ),
            error_tasks=[
                _deployment_error_event.s(search_params),
                update_deployment_state.si(deployment['id'],
                                           DEPLOYMENT_STATE_FAILED),
                _fleet_undeploy.si(
                    app_name,
                    version=app_version,
                    ignore_error=True
                )
            ]
        )
    ).apply_async()


@app.task
def delete(name, version=None):
    """
    Deletes the application with given name and version.

    :param name: Name of the application. Optionally it might also contain
    :param version: Version of application to be undeployed. If none, all
        versions are undeployed.
    :return:
    """
    search_params = {
        'deployment': {
            'name': name,
            'version': version or 'all',
            'id': '%s-%s' % (name, version) if version else 'all'
        }
    }
    return _using_lock.si(
        search_params, name,
        do_task=(
            _fleet_undeploy.si(name, version) |
            get_promoted_deployments.si(name, version) |
            mark_decommissioned.s() |
            _wait_for_undeploy.si(name, version, ret_value='done')
        )
    )()


@app.task
def list_units(name, version):
    """
    Lists fleet units for a given application and version

    :param name:
    :param version:
    :return: list of units where each unit is represented as dict
            comprising of
                - unit : Name of fleet unit,
                - machine : Machine for the unit
                - active : Activation status ('activating', 'active')
                - sub : Current state of the unit
    """
    return filter_units(get_fleet_provider(), name, version)


@app.task(bind=True, default_retry_delay=TASK_SETTINGS['LOCK_RETRY_DELAY'],
          max_retries=TASK_SETTINGS['LOCK_RETRIES'])
def _using_lock(self, search_params, name, do_task, cleanup_tasks=None,
                error_tasks=None):
    """
    Applies lock for the deployment

    :return: Lock object (dictionary)
    :rtype: dict
    """
    try:
        lock = LockService().apply_lock(name)
    except ResourceLockedException as lock_error:
        self.retry(exc=lock_error)

    _release_lock_s = _release_lock.si(lock)
    cleanup_tasks = cleanup_tasks or []
    if not isinstance(cleanup_tasks, list):
        cleanup_tasks = [cleanup_tasks]

    error_tasks = error_tasks or []
    if not isinstance(error_tasks, list):
        error_tasks = [error_tasks]

    error_tasks.append(_release_lock_s)
    cleanup_tasks.append(_release_lock_s)

    return (
        add_search_event.si(
            EVENT_ACQUIRED_LOCK, search_params=search_params,
            details={
                'name': name
            }) |
        do_task |
        async_wait.s(
            default_retry_delay=TASK_SETTINGS['DEPLOYMENT_WAIT_RETRY_DELAY'],
            max_retries=TASK_SETTINGS['DEPLOYMENT_WAIT_RETRIES']
        )
    ).apply_async(
        link=chain(cleanup_tasks),
        link_error=chain(error_tasks)
    )


@app.task
def _release_lock(lock):
    """
    Releases lock acquired during deletion or creation.

    :param lock: Lock dictionary
    :type lock: dict
    :return: True: If lock was released.
            False: Otherwise
    """
    return LockService().release(lock)


@app.task
def _deploy_all(deployment, search_params):
    """
    Deploys all services for a given deployment
    :param deployment: Deployment parameters
    :type deployment: dict
    :return:
    """

    security_profile = deployment.get('security', {})\
        .get('profile', 'default')
    templates = copy.deepcopy(deployment['templates'])
    app_template = templates['app']
    if not app_template['enabled']:
        return []

    sidekicks = [service_type for service_type, template in
                 deployment['templates'].iteritems()
                 if template['enabled'] and service_type != 'app']

    app_template['args']['sidekicks'] = sidekicks
    name, version, nodes = deployment['deployment']['name'], \
        deployment['deployment']['version'], \
        deployment['deployment']['nodes']
    return chord(
        group(
            _fleet_deploy.si(search_params, name, version, nodes, service_type,
                             template, security_profile)
            for service_type, template in templates.iteritems()
            if template['enabled']
        ),
        _fleet_start_and_wait.si(deployment, search_params)
    )()


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
    deployment['deployment']['name'] = \
        deployment['deployment']['name'] \
        .format(GIT_OWNER=git_meta['owner'],
                GIT_REPO=git_meta['repo'],
                GIT_REF=git_meta['ref'])
    return deployment


def _get_exposed_ports(deployment):
    """
    Gets the exposed ports for the given deployment

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

    deployment_upd['id'] = '%s-%s' % (deployment_upd['deployment']['name'],
                                      deployment_upd['deployment']['version'])
    deployment_upd['state'] = DEPLOYMENT_STATE_STARTED
    deployment_upd['started-at'] = datetime.datetime.utcnow()

    # Apply proxy defaults
    for upstream_name, upstream in deployment_upd['proxy']['upstreams']\
            .iteritems():
        upd_upstream = dict_merge(upstream, UPSTREAM_DEFAULTS)
        if upd_upstream.get('mode') != 'http' and \
                upd_upstream['health'].get('uri'):
            del(upd_upstream['health']['uri'])
        deployment_upd['proxy']['upstreams'][upstream_name] = upd_upstream

    app_template = deployment_upd.get('templates').get('app')
    if app_template:
        env = app_template['args']['environment']
        env['DISCOVER_PORTS'] = ','.join(
            [str(port) for port in _get_exposed_ports(deployment_upd)])
        env['DISCOVER_MODE'] = deployment_upd['deployment']['mode']
        env['DISCOVER_HEALTH'] = json.dumps(
            _create_discover_check(deployment_upd))
    return deployment_upd


@app.task(bind=True)
def _fleet_deploy(self, search_params, name, version, nodes, service_type,
                  template, security_profile):
    """
    Deploys the unit with given service type to multiple nodes using fleet.
    The unit won't be launched after install.

    :param name: Name of the application
    :param version: Version of the application
    :param nodes: No. of nodes/units to be created
    :param service_type: Type of unit ('app', 'logger' etc)
    :param template: Fleet Template settings.
    :return:
    """
    logger.info('Deploying %s:%s:%s nodes:%d %r', name, version, service_type,
                nodes, template)
    template_args = decrypt_config(template.get('args', {}),
                                   profile=security_profile)
    fleet_deployment = Deployment(
        fleet_provider=get_fleet_provider(), jinja_env=jinja_env, name=name,
        version=version, template=template['name'] + '.service', nodes=nodes,
        template_args=template_args, service_type=service_type)
    try:
        fleet_deployment.deploy(start=False)
    except RETRYABLE_FLEET_EXCEPTIONS as exc:
        raise self.retry(exc=exc, max_retries=TASK_SETTINGS['SSH_RETRIES'],
                         countdown=TASK_SETTINGS['SSH_RETRY_DELAY'])
    return add_search_event.si(
        EVENT_UNITS_ADDED,
        search_params=search_params,
        details={
            'name': name,
            'version': version,
            'nodes': nodes,
            'service_type': service_type,
            'template': template
        })()


@app.task(bind=True)
def _fleet_start(self, search_params, name, version, nodes, service_type,
                 template):
    """
    Starts the fleet units

    :param name: Name of the application
    :param version: Version of the application
    :param nodes: No. of nodes/units to be created
    :param service_type: Type of unit ('app', 'logger' etc)
    :param template: Fleet Template settings.
    :return:
    """
    logger.info('Starting %s:%s:%s nodes:%d %r', name, version, service_type,
                nodes, template)
    fleet_deployment = Deployment(
        fleet_provider=get_fleet_provider(), jinja_env=jinja_env, name=name,
        version=version, template=template['name'] + '.service', nodes=nodes,
        template_args=template['args'], service_type=service_type)
    try:
        fleet_deployment.start_units()
    except RETRYABLE_FLEET_EXCEPTIONS as exc:
        raise self.retry(exc=exc, max_retries=TASK_SETTINGS['SSH_RETRIES'],
                         countdown=TASK_SETTINGS['SSH_RETRY_DELAY'])

    return add_search_event.si(
        EVENT_UNITS_STARTED,
        search_params=search_params,
        details={
            'name': name,
            'version': version,
            'nodes': nodes,
            'service_type': service_type,
            'template': template
        })()


@app.task
def _fleet_start_and_wait(deployment, search_params):
    """
    Starts the units for the deployment and performs an asynchronous wait for
    all unit states to reach running state.

    :param deployment: Deployment parameters.
    :type deployment: dict
    :param search_params: Search parameters
    :type search_params: dict
    :return:
    """
    name, version, nodes = deployment['deployment']['name'], \
        deployment['deployment']['version'], \
        deployment['deployment']['nodes']
    service_types = {service_type for service_type, template in
                     deployment['templates'].iteritems()
                     if template['enabled']}
    min_nodes = deployment['deployment'].get('check', {}).get(
        'min-nodes', nodes)
    return chord(
        group(
            _fleet_start.si(search_params, name, version, nodes, service_type,
                            template)
            for service_type, template in deployment['templates'].iteritems()
            if template['enabled']
        ),
        _fleet_check_deploy.si(name, version, len(service_types), min_nodes)
    )()


@app.task
def _pre_create_undeploy(deployment, search_params, next_task=None):
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
        return next_task() if next_task else None
    name = deployment['deployment']['name']
    undeploy_chain = [
        _fleet_undeploy.si(name, version, ignore_error=False),
        _wait_for_undeploy.si(name, version),
        add_search_event.si(
            EVENT_UNDEPLOYED_EXISTING,
            search_params=search_params,
            details={
                'name': name,
                'version': version
            }
        )
    ]
    if next_task:
        undeploy_chain.append(next_task)
    return chain(undeploy_chain)()


@app.task(bind=True)
def _fleet_undeploy(self, name, version=None, exclude_version=None,
                    ret_value=None, ignore_error=False):
    """
    Un-deploys fleet units with matching name and version

    :param name: Name of application
    :keyword version: Version of application
    :keyword exclude_version: Version of deployment to be excluded
    :keyword ret_value: Value to be returned after successful deployment
    :return: ret_value
    """
    try:
        undeploy(get_fleet_provider(), name, version,
                 exclude_version=exclude_version)
        return ret_value
    except RETRYABLE_FLEET_EXCEPTIONS as exc:
        raise self.retry(exc=exc, max_retries=TASK_SETTINGS['SSH_RETRIES'],
                         countdown=TASK_SETTINGS['SSH_RETRY_DELAY'])
    except:
        if ignore_error:
            return ret_value
        else:
            raise


@app.task(bind=True, default_retry_delay=5, max_retries=5)
def _wait_for_undeploy(self, name, version, ret_value=None):
    """
    Wait for undeploy to finish.

    :param name: Name of application
    :param version: Version of application.
    :type version: str
    :keyword ret_value: Value to be returned on successful call.
    :return: ret_value
    """
    try:
        deployed_units = filter_units(get_fleet_provider(), name, version)
    except RETRYABLE_FLEET_EXCEPTIONS as exc:
        raise self.retry(exc=exc, max_retries=TASK_SETTINGS['SSH_RETRIES'],
                         countdown=TASK_SETTINGS['SSH_RETRY_DELAY'])
    if deployed_units:
        raise self.retry(exc=NodeNotUndeployed(name, version, deployed_units))
    return ret_value


@app.task(bind=True,
          default_retry_delay=TASK_SETTINGS['CHECK_RUNNING_RETRY_DELAY'],
          max_retries=TASK_SETTINGS['CHECK_RUNNING_RETRIES'])
def _fleet_check_deploy(self, name, version, service_cnt, min_nodes):
    expected_cnt = min_nodes * service_cnt
    try:
        units = filter_units(get_fleet_provider(), name, version=version)
    except RETRYABLE_FLEET_EXCEPTIONS as exc:
        raise self.retry(exc=exc, max_retries=TASK_SETTINGS['SSH_RETRIES'],
                         countdown=TASK_SETTINGS['SSH_RETRY_DELAY'])

    running_units = [unit for unit in units
                     if unit['sub'].lower() == 'running']
    if len(running_units) < expected_cnt:
        raise self.retry(exc=MinNodesNotRunning(
            name, version, expected_cnt, units))
    else:
        return running_units


@app.task
def _processed_deployment(deployment):
    deployment['state'] = DEPLOYMENT_STATE_PROMOTED
    deployment['promoted-at'] = datetime.datetime.utcnow()
    return deployment


@app.task
def _deployment_error_event(task_id, search_params):
    """
    Handles deployment creation error

    :param deployment: Deployment dictionary
    :return: None
    """
    app.set_current()
    output = app.AsyncResult(task_id)
    return add_search_event.si(
        EVENT_DEPLOYMENT_FAILED,
        search_params=search_params,
        details={
            'error': str(output.result),
            'traceback': output.traceback
        })


@app.task
def _promote_deployment(deployment, search_params):
    """
    Promotes the given deployment by wiring the proxy,
    un-deploying existing (if needed) and updating search state.

    :param deployment: Dictionary representing deployment
    :param search_params: Ductionary containing search parameters
    :type deployment: dict
    """
    tasks = []
    name = deployment['deployment']['name']
    version = deployment['deployment']['version']
    # Add Proxy Wired to the chain
    tasks.append(
        add_search_event.si(
            EVENT_WIRED, search_params=search_params,
            details={
                'name': name,
                'version': version,
                'proxy': deployment['proxy']
            }
        )
    )

    if deployment['deployment']['mode'] == DEPLOYMENT_MODE_BLUEGREEN:
        tasks += [
            _fleet_undeploy.subtask((name,), {'exclude_version': version},
                                    countdown=120, immutable=True),
            get_promoted_deployments.si(name),
            mark_decommissioned.s()
        ]

    tasks += [
        update_deployment_state.si(deployment['id'],
                                   DEPLOYMENT_STATE_PROMOTED),
        add_search_event.si(EVENT_PROMOTED, search_params=search_params),
        _processed_deployment.si(deployment)
    ]

    return wire_proxy.si(
        deployment['deployment']['name'],
        deployment['deployment']['version'],
        deployment['proxy'],
        next_task=(chain(tasks))
    )()
