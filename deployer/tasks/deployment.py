"""
Defines celery tasks for deployment (e.g.: create, undeploy, wire, unwire)
"""
import copy
import datetime
import json
import socket
import logging
import time
import urllib2
from fabric.exceptions import NetworkError
from fleet.client.fleet_fabric import FleetExecutionException
from paramiko import SSHException
import sys

from deployer.services.distributed_lock import LockService, \
    ResourceLockedException
from deployer.services.security import decrypt_config
from deployer.services.storage.factory import get_store
from deployer.services.util import create_notify_ctx
from deployer.services.deployment import fetch_runtime_units, get_exposed_ports, \
    sync_upstreams, sync_units
from deployer.tasks import notification
from deployer.tasks.exceptions import NodeNotUndeployed, MinNodesNotRunning, \
    NodeCheckFailed, MinNodesNotDiscovered
from deployer.tasks import util

from deployer.services.storage.base import EVENT_NEW_DEPLOYMENT, \
    EVENT_ACQUIRED_LOCK, EVENT_UNDEPLOYED_EXISTING, EVENT_UNITS_DEPLOYED, \
    EVENT_PROMOTED, EVENT_DEPLOYMENT_FAILED, EVENT_DEPLOYMENT_CHECK_PASSED, \
    EVENT_UNITS_ADDED, EVENT_UNITS_STARTED, \
    EVENT_WIRED, EVENT_UPSTREAMS_REGISTERED, EVENT_NODES_DISCOVERED

from celery.canvas import group, chord, chain

from deployer.fleet import get_fleet_provider, jinja_env
from fleet.deploy.deployer import Deployment, undeploy

from deployer.celery import app
from conf.appconfig import DEPLOYMENT_DEFAULTS, DEPLOYMENT_TYPE_GIT_QUAY, \
    TEMPLATE_DEFAULTS, TASK_SETTINGS, DEPLOYMENT_MODE_BLUEGREEN, \
    DEPLOYMENT_MODE_REDGREEN, DEPLOYMENT_STATE_STARTED, \
    DEPLOYMENT_STATE_FAILED, DEPLOYMENT_STATE_PROMOTED, UPSTREAM_DEFAULTS, \
    LEVEL_STARTED, LEVEL_FAILED, LEVEL_SUCCESS, CLUSTER_NAME, \
    DEPLOYMENT_STATE_DECOMMISSIONED, LOCK_JOB_BASE

from deployer.tasks.common import async_wait
from deployer.services.proxy import wire_proxy, register_upstreams, \
    get_discovered_nodes

from deployer.util import dict_merge, to_milliseconds

__author__ = 'sukrit'
__all__ = ['create', 'delete']


logger = logging.getLogger(__name__)

RETRYABLE_FLEET_EXCEPTIONS = (SSHException, EOFError, NetworkError,
                              socket.error, FleetExecutionException)


def create_search_parameters(deployment, defaults=None):
    """
    Creates search parameters for a given deployment.

    :param deployment: Dictionary containing deployment parameters.
    :type deployment: dict
    :return: Dictionary containing search parameters
    :rtype: dict
    """

    deployment = dict_merge(deployment or {}, defaults or {}, {
        'meta-info': {}
    })
    return {
        'meta-info': copy.deepcopy(deployment['meta-info']),
        'deployment': {
            'name': deployment['deployment']['name'],
            'version': deployment['deployment']['version'],
            'id': deployment['id']
        }
    }


@app.task
def _register_upstreams(
        app_name, app_version, upstreams,
        deployment_mode=DEPLOYMENT_MODE_BLUEGREEN, search_params=None):
    register_upstreams(app_name, app_version, upstreams,
                       deployment_mode=deployment_mode)
    get_store().add_event(EVENT_UPSTREAMS_REGISTERED,
                          search_params=search_params)


@app.task(bind=True,
          default_retry_delay=TASK_SETTINGS['CHECK_DISCOVERY_RETRY_DELAY'],
          max_retries=TASK_SETTINGS['CHECK_DISCOVERY_RETRIES'])
def _check_discover(self, app_name, app_version, check_port, min_nodes,
                    deployment_mode, search_params=None):
    """
    Checks if min. no. of nodes for a given application have been discovered
    in yoda proxy

    :param app_name: Application name
    :type app_name: str
    :param app_version: Application version
    :type app_version: str
    :param check_port: Port to be used discover check. If None, discover check
        is skipped.
    :param min_nodes: Minimum no. of nodes to be discovered.
    :param deployment_mode: mode of deploy (blue-green, red-green, a/b etc)
    :return: discovered nodes
    :rtype: dict
    """
    if check_port is None:
        # Skip discover if port is not passed
        return {}

    discovered_nodes = get_discovered_nodes(app_name, app_version, check_port,
                                            deployment_mode)
    if len(discovered_nodes) < min_nodes:
        raise self.retry(exc=MinNodesNotDiscovered(
            app_name, app_version, min_nodes, discovered_nodes))

    get_store().add_event(EVENT_NODES_DISCOVERED,
                          details=discovered_nodes,
                          search_params=search_params)
    return discovered_nodes


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
    deployment_check = deployment['deployment'].get('check', {})
    check_port = deployment_check.get('port')
    deployment_mode = deployment['deployment']['mode']
    notify_ctx = create_notify_ctx(deployment, 'create')
    notification.notify.si(
        {'message': 'Started provisioning'}, ctx=notify_ctx,
        level=LEVEL_STARTED,
        notifications=deployment['notifications'],
        security_profile=deployment['security']['profile']).delay()

    # Tasks to be performed on error
    error_tasks = [
        _deployment_error_event.s(deployment, search_params),
        _fleet_undeploy.si(
            app_name,
            version=app_version,
            ignore_error=True
        )
    ]
    store = get_store()
    store.create_deployment(deployment)
    store.add_event(EVENT_NEW_DEPLOYMENT, details=deployment,
                    search_params=search_params)

    return (
        _using_lock.si(
            search_params,
            app_name,
            do_task=_pre_create_undeploy.si(
                deployment,
                search_params,
                next_task=_register_upstreams.si(
                    app_name,
                    app_version,
                    upstreams=deployment['proxy']['upstreams'],
                    deployment_mode=deployment_mode,
                    search_params=search_params
                ) |
                _deploy_all.si(
                    deployment, search_params,
                    next_task=_check_discover.si(
                        app_name, app_version, check_port,
                        min_nodes, deployment_mode, search_params) |
                    _check_deployment.s(
                        deployment_check.get('path'),
                        deployment_check.get('attempts'),
                        deployment_check.get('timeout'),
                        search_params=search_params,
                        next_task=_promote_deployment.si(deployment,
                                                         search_params)
                    )
                )
            ),
            error_tasks=error_tasks
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
            _wait_for_undeploy.si(name, version, search_params=search_params)
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
    return fetch_runtime_units(name, version)


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

    get_store().add_event(
        EVENT_ACQUIRED_LOCK, search_params=search_params, details={
            'name': name
        })

    return (
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
def _deploy_all(deployment, search_params, next_task=None):
    """
    Deploys all services for a given deployment
    :param deployment: Deployment parameters
    :type deployment: dict
    :return: Result  of execution of next tasj
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
        _fleet_start_and_wait.si(deployment, search_params,
                                 next_task=next_task)
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

    app_template = deployment_upd.get('templates').get('app')
    exposed_ports = get_exposed_ports(deployment_upd)

    # Create default upstreams (using exposed ports)
    for port in exposed_ports:
        deployment_upd['proxy']['upstreams'].setdefault(str(port), {})

    # Apply proxy defaults
    for upstream_name, upstream in deployment_upd['proxy']['upstreams']\
            .iteritems():
        upd_upstream = dict_merge(upstream, UPSTREAM_DEFAULTS)
        if upd_upstream.get('mode') != 'http' and \
                upd_upstream['health'].get('uri'):
            del(upd_upstream['health']['uri'])
        deployment_upd['proxy']['upstreams'][upstream_name] = upd_upstream

    if app_template:
        env = app_template['args']['environment']
        env['DISCOVER_PORTS'] = ','.join(
            [str(port) for port in exposed_ports])
        env['DISCOVER_MODE'] = deployment_upd['deployment']['mode']
        env['DISCOVER_HEALTH'] = json.dumps(
            _create_discover_check(deployment_upd))

    # Override/Set Clustername in meta-info
    deployment_upd['meta-info'] = dict_merge({
        'deployer': {
            'cluster': CLUSTER_NAME
        }
    }, deployment_upd['meta-info'])
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
    get_store().add_event(
        EVENT_UNITS_ADDED, search_params=search_params, details={
            'name': name,
            'version': version,
            'nodes': nodes,
            'service_type': service_type,
            'template': template
        })


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

    get_store().add_event(
        EVENT_UNITS_STARTED, search_params=search_params, details={
            'name': name,
            'version': version,
            'nodes': nodes,
            'service_type': service_type,
            'template': template
        })


@app.task
def _fleet_start_and_wait(deployment, search_params, next_task=None):
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
        _fleet_check_deploy.si(name, version, len(service_types), min_nodes,
                               search_params, next_task=next_task)
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
        return next_task.delay() if next_task else None
    name = deployment['deployment']['name']
    undeploy_chain = [
        _fleet_undeploy.si(name, version, ignore_error=False),
        _wait_for_undeploy.si(name, version, search_params=search_params)
    ]
    if next_task:
        undeploy_chain.append(next_task)
    return chain(undeploy_chain).delay()


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
    except RETRYABLE_FLEET_EXCEPTIONS as exc:
        raise self.retry(exc=exc, max_retries=TASK_SETTINGS['SSH_RETRIES'],
                         countdown=TASK_SETTINGS['SSH_RETRY_DELAY'])
    except:
        if not ignore_error:
            raise
    store = get_store()
    store.update_state_bulk(name, DEPLOYMENT_STATE_DECOMMISSIONED,
                            existing_state=DEPLOYMENT_STATE_PROMOTED,
                            version=version)
    return ret_value


@app.task(bind=True, default_retry_delay=5, max_retries=5)
def _wait_for_undeploy(self, name, version, ret_value=None,
                       search_params=None):
    """
    Wait for undeploy to finish.

    :param name: Name of application
    :param version: Version of application.
    :type version: str
    :keyword ret_value: Value to be returned on successful call.
    :return: ret_value
    """
    try:
        deployed_units = fetch_runtime_units(name, version)
    except RETRYABLE_FLEET_EXCEPTIONS as exc:
        raise self.retry(exc=exc, max_retries=TASK_SETTINGS['SSH_RETRIES'],
                         countdown=TASK_SETTINGS['SSH_RETRY_DELAY'])
    if deployed_units:
        raise self.retry(exc=NodeNotUndeployed(name, version, deployed_units))
    get_store().add_event(
        EVENT_UNDEPLOYED_EXISTING,
        search_params=search_params,
        details={
            'name': name,
            'version': version
        }
    )
    return ret_value


@app.task(bind=True,
          default_retry_delay=TASK_SETTINGS['CHECK_RUNNING_RETRY_DELAY'],
          max_retries=TASK_SETTINGS['CHECK_RUNNING_RETRIES'])
def _fleet_check_deploy(self, name, version, service_cnt, min_nodes,
                        search_params=None, next_task=None):
    expected_cnt = min_nodes * service_cnt
    try:
        units = fetch_runtime_units(name, version=version)
    except RETRYABLE_FLEET_EXCEPTIONS as exc:
        raise self.retry(exc=exc, max_retries=TASK_SETTINGS['SSH_RETRIES'],
                         countdown=TASK_SETTINGS['SSH_RETRY_DELAY'])

    running_units = [unit for unit in units
                     if unit['sub'].lower() == 'running']
    if len(running_units) < expected_cnt:
        raise self.retry(exc=MinNodesNotRunning(
            name, version, expected_cnt, units))
    else:
        get_store().add_event(EVENT_UNITS_DEPLOYED, details=running_units,
                              search_params=search_params)
        if next_task:
            return next_task.delay()
        return running_units


@app.task
def _processed_deployment(deployment):
    deployment['state'] = DEPLOYMENT_STATE_PROMOTED
    deployment['promoted-at'] = datetime.datetime.utcnow()
    return deployment


@app.task
def _deployment_error_event(task_id, deployment, search_params):
    """
    Handles deployment creation error

    :param deployment: Deployment dictionary
    :return: None
    """
    app.set_current()
    output = app.AsyncResult(task_id)
    notify_ctx = create_notify_ctx(deployment, 'create')
    notification.notify.si(
        output.result, ctx=notify_ctx, level=LEVEL_FAILED,
        notifications=deployment['notifications'],
        security_profile=deployment['security']['profile']).delay()
    store = get_store()
    store.update_state(deployment['id'], DEPLOYMENT_STATE_FAILED)
    store.add_event(
        EVENT_DEPLOYMENT_FAILED,
        details={'deployment-error': util.as_dict(output.result)},
        search_params=search_params,
    )


@app.task
def _promote_success(deployment, search_params=None):
    store = get_store()
    deployment_id = deployment['deployment']['id']
    notify_ctx = create_notify_ctx(deployment, 'create')
    store.add_event(EVENT_PROMOTED, search_params=search_params)
    store.update_state(deployment_id, DEPLOYMENT_STATE_PROMOTED)
    notification.notify.si(
        {'message': 'Promoted'}, ctx=notify_ctx,
        level=LEVEL_SUCCESS,
        notifications=deployment['notifications'],
        security_profile=deployment['security']['profile']),
    _processed_deployment.si(deployment)


@app.task
def _promote_deployment(deployment, search_params):
    """
    Promotes the given deployment by wiring the proxy,
    un-deploying existing (if needed) and updating search state.

    :param deployment: Dictionary representing deployment
    :param search_params: Ductionary containing search parameters
    :type deployment: dict
    """
    name = deployment['deployment']['name']
    version = deployment['deployment']['version']

    wire_proxy(name, version, deployment['proxy'])
    get_store().add_event(
        EVENT_WIRED, search_params=search_params, details={
            'name': name,
            'version': version,
            'proxy': deployment['proxy']
        }
    )

    tasks = []

    if deployment['deployment']['mode'] == DEPLOYMENT_MODE_BLUEGREEN:
        tasks.append(
            _fleet_undeploy.subtask((name,), {'exclude_version': version},
                                    countdown=120, immutable=True))

    tasks.append(_promote_success.si(deployment, search_params=search_params))

    return chain(tasks).delay()


@app.task
def _deployment_check_passed(search_params=None, next_task=None):
    get_store().add_event(EVENT_DEPLOYMENT_CHECK_PASSED,
                          search_params=search_params)
    if next_task:
        return next_task.delay()


@app.task
def _check_deployment(nodes, path, attempts, timeout, search_params=None,
                      next_task=None):
    """
    Performs a deployment check on discovered nodes

    :param nodes: List of discovered nodes
    :type nodes: list
    :param attempts: Max no. of attempts for deployment check for a given node.
    :type attempts: int
    :param timeout: Deployment check timeout
    :type timeout: str
    :return: GroupResult
    """

    if path and nodes:
        return chord(
            group(_check_node.si(node, path, attempts, timeout)
                  for _, node in nodes.iteritems()),
            _deployment_check_passed.si(search_params=search_params,
                                        next_task=next_task)
        ).delay()


@app.task(bind=True)
def _check_node(self, node, path, attempts, timeout):
    """
    Performs deployment check on single node.

    :param node: Node on which deployment check needs to be performed.
    :type node: str
    :param attempts: Max no. of attempts for deployment check for a given node.
    :type attempts: int
    :param timeout: Deployment check timeout
    :type timeout: str
    :return: None
    """

    path = '/' + path if not path.startswith('/') else path
    check_url = 'http://{0}{1}'.format(node, path)
    timeout_ms = to_milliseconds(timeout)
    try:
        urllib2.urlopen(check_url, None, timeout_ms/1000)
    except IOError as exc:
        # Clear the current exception so that celery does not raise original
        # exception
        reason = exc.reason if hasattr(exc, 'reason') else str(exc)
        kwargs = {}
        if hasattr(exc, 'read'):
            kwargs.update(response={'raw': exc.read()}, status=exc.code)

        sys.exc_clear()
        raise self.retry(
            exc=NodeCheckFailed(check_url, reason, **kwargs),
            max_retries=attempts-1,
            countdown=TASK_SETTINGS['CHECK_NODE_RETRY_DELAY'])


def _get_job_lock(job_name):
    try:
        return LockService(lock_base=LOCK_JOB_BASE).apply_lock(job_name)
    except ResourceLockedException as lock_error:
        logger.info('Job:{} already running. Skipping...'.format(
            lock_error.name))


@app.task
def sync_upstreams_task(deployment_id):
    """
    Synchronizes upstream for given deployment
    """
    sync_upstreams(deployment_id)


@app.task
def sync_units_task(deployment_id):
    """
    Synchronizes upstream for given deployment
    """
    sync_units(deployment_id)


@app.task(bind=True)
def sync_promoted_upstreams(self):
    """
    Synchronizes upstreams of all promoted deployments
    """
    lock = _get_job_lock(self.name)
    if not lock:
        return

    try:
        deployments = get_store().filter_deployments(
            state=DEPLOYMENT_STATE_PROMOTED)
    except:
        _release_lock.si(lock).delay()
        raise
    return chord(
        group(sync_upstreams_task.si(deployment['id'])
              for deployment in deployments),
        _release_lock.si(lock)
    ).delay()


@app.task(bind=True)
def sync_promoted_units(self):
    """
    Synchronizes upstreams of all promoted deployments
    """
    lock = _get_job_lock(self.name)
    if not lock:
        return

    try:
        deployments = get_store().filter_deployments(
            state=DEPLOYMENT_STATE_PROMOTED)
    except:
        _release_lock.si(lock).delay()
        raise
    return chord(
        group(sync_upstreams_task.si(deployment['id'])
              for deployment in deployments),
        _release_lock.si(lock)
    ).delay()
