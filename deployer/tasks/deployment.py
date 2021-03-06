"""
Defines celery tasks for deployment (e.g.: create, undeploy, wire, unwire)
"""
import copy
from httplib import HTTPException
import socket
import logging
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
from deployer.services.deployment import fetch_runtime_units, \
    sync_upstreams, sync_units, apply_defaults, clone_deployment
from deployer.tasks import notification
from deployer.tasks.exceptions import NodeNotUndeployed, MinNodesNotRunning, \
    NodeCheckFailed, MinNodesNotDiscovered, NodeNotStopped, \
    MaxStartConcurrencyReached
from deployer.tasks import util

from deployer.services.storage.base import EVENT_NEW_DEPLOYMENT, \
    EVENT_ACQUIRED_LOCK, EVENT_UNITS_DEPLOYED, \
    EVENT_PROMOTED, EVENT_DEPLOYMENT_FAILED, EVENT_DEPLOYMENT_CHECK_PASSED, \
    EVENT_UNITS_ADDED, EVENT_UNITS_STARTED, \
    EVENT_WIRED, EVENT_UPSTREAMS_REGISTERED, EVENT_NODES_DISCOVERED, \
    EVENT_DEPLOYMENTS_STOPPED, EVENT_DEPLOYMENTS_UNDEPLOYED

from celery.canvas import group, chord, chain

from deployer.fleet import get_fleet_provider, jinja_env
from fleet.deploy.deployer import Deployment, undeploy, stop

from deployer.celery import app
from conf.appconfig import DEPLOYMENT_DEFAULTS, \
    TASK_SETTINGS, DEPLOYMENT_MODE_BLUEGREEN, \
    DEPLOYMENT_MODE_REDGREEN, \
    DEPLOYMENT_STATE_FAILED, DEPLOYMENT_STATE_PROMOTED, \
    LEVEL_STARTED, LEVEL_FAILED, LEVEL_SUCCESS, CLUSTER_NAME, \
    DEPLOYMENT_STATE_DECOMMISSIONED, LOCK_JOB_BASE, DEPLOYMENT_TYPE_DEFAULT, \
    DEFAULT_CHORD_OPTIONS, DEPLOYMENT_STATE_STARTED, FLEET_STARTED_STATES

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
        'meta-info': {},
        'deployment': {
            'name': '',
            'version': ''
        },
        'id': ''
    })
    return {
        'meta-info': dict_merge(
            {
                'deployer': {
                    'cluster': CLUSTER_NAME
                }
            },
            copy.deepcopy(deployment['meta-info'])),
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
    if not check_port:
        # Skip discover if port is empty, 0 , None
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
    deployment = apply_defaults(deployment)

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
            do_task=_start_deployment.si(deployment['id'], TASK_SETTINGS) |
            _pre_create_undeploy.si(
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
    search_params = create_search_parameters({
        'deployment': {
            'name': name,
            'version': version or 'all'
        }
    })
    return _using_lock.si(
        search_params, name,
        do_task=(
            _fleet_stop.si(name, version=version) |
            _wait_for_stop.si(name, version=version,
                              search_params=search_params) |
            _fleet_undeploy.si(name, version) |
            _wait_for_undeploy.si(name, version, search_params=search_params)
        )
    ).apply_async()


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
        raise self.retry(exc=lock_error)

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
    app_template = deployment['templates']['app']
    if not app_template['enabled']:
        return []

    name, version, nodes = deployment['deployment']['name'], \
        deployment['deployment']['version'], \
        deployment['deployment']['nodes']
    return chord(
        group(
            _fleet_deploy.si(search_params, name, version, nodes, service_type,
                             template, security_profile)
            for service_type, template in deployment['templates'].items()
            if template['enabled']
        ),
        _fleet_start_and_wait.si(deployment, search_params,
                                 next_task=next_task),
        options=DEFAULT_CHORD_OPTIONS
    )()


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
    is_timer = (service_type == 'timer')
    fleet_deployment = Deployment(
        fleet_provider=get_fleet_provider(), jinja_env=jinja_env, name=name,
        version=version, template=template['name'], nodes=nodes,
        template_args=template_args, service_type=service_type,
        timer=is_timer)
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
    is_timer = (service_type == 'timer')
    fleet_deployment = Deployment(
        fleet_provider=get_fleet_provider(), jinja_env=jinja_env, name=name,
        version=version, template=template['name'], nodes=nodes,
        template_args=template['args'], service_type=service_type,
        timer=is_timer)
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
    if not deployment['schedule']:
        service_types = {service_type for service_type, template in
                         deployment['templates'].items()
                         if template['enabled']}
    else:
        service_types = {'timer'}
    min_nodes = deployment['deployment'].get('check', {}).get(
        'min-nodes', nodes)
    templates = deployment['templates']
    return chord(
        group(
            _fleet_start.si(search_params, name, version, nodes, service_type,
                            templates[service_type])
            for service_type in service_types
        ),
        _fleet_check_deploy.si(name, version, len(service_types), min_nodes,
                               search_params, next_task=next_task),
        options=DEFAULT_CHORD_OPTIONS
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
        _fleet_stop.si(name, version=version) |
        _wait_for_stop.si(name, version=version, search_params=search_params) |
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


@app.task(bind=True)
def _fleet_stop(self, name, version=None, exclude_version=None,
                ignore_error=False):
    """
   Stops fleet units with matching name and version

    :param name: Name of application
    :keyword version: Version of application
    :keyword exclude_version: Version of deployment to be excluded
    :keyword ret_value: Value to be returned after successful deployment
    :return: ret_value
    """
    try:
        stop(get_fleet_provider(), name, version=version,
             exclude_version=exclude_version)
    except RETRYABLE_FLEET_EXCEPTIONS as exc:
        raise self.retry(exc=exc, max_retries=TASK_SETTINGS['SSH_RETRIES'],
                         countdown=TASK_SETTINGS['SSH_RETRY_DELAY'])
    except:
        if not ignore_error:
            raise


@app.task(bind=True, default_retry_delay=5, max_retries=5)
def _wait_for_undeploy(self, name, version=None, ret_value=None,
                       search_params=None, exclude_version=None):
    """
    Wait for undeploy to finish.

    :param name: Name of application
    :param version: Version of application.
    :type version: str
    :keyword ret_value: Value to be returned on successful call.
    :return: ret_value
    """
    try:
        deployed_units = fetch_runtime_units(
            name, version=version, exclude_version=exclude_version)
    except RETRYABLE_FLEET_EXCEPTIONS as exc:
        raise self.retry(exc=exc, max_retries=TASK_SETTINGS['SSH_RETRIES'],
                         countdown=TASK_SETTINGS['SSH_RETRY_DELAY'])
    if deployed_units:
        raise self.retry(exc=NodeNotUndeployed(name, version, deployed_units))
    get_store().add_event(
        EVENT_DEPLOYMENTS_UNDEPLOYED,
        search_params=search_params,
        details={
            'deployment': {
                'name': name,
                'version': version,
                'exclude-version': exclude_version
            }
        }
    )
    return ret_value


@app.task(bind=True, default_retry_delay=5, max_retries=5)
def _wait_for_stop(self, name, version=None, exclude_version=None,
                   timeout=None, check_retries=None, search_params=None):
    """
    Wait for deployment to be stopped

    :param name: Name of application
    :type name: str
    :param version: Version of application.
    :type version: str
    :keyword ret_value: Value to be returned on successful call.
    :return: ret_value
    """
    timeout = timeout or DEPLOYMENT_DEFAULTS[DEPLOYMENT_TYPE_DEFAULT][
        'deployment']['stop']['timeout']
    timout_seconds = to_milliseconds(timeout) / 1000
    check_retries = check_retries or \
        TASK_SETTINGS['DEFAULT_DEPLOYMENT_STOP_CHECK_RETRIES']
    check_interval = max(
        (timout_seconds / check_retries)+1,
        TASK_SETTINGS['DEPLOYMENT_STOP_MIN_CHECK_RETRY_DELAY']
    )
    try:
        deployed_units = fetch_runtime_units(
            name, version=version, exclude_version=exclude_version)
    except RETRYABLE_FLEET_EXCEPTIONS as exc:
        raise self.retry(exc=exc, max_retries=TASK_SETTINGS['SSH_RETRIES'],
                         countdown=TASK_SETTINGS['SSH_RETRY_DELAY'])
    active_units = [unit for unit in deployed_units if unit['active']
                    not in ('inactive', 'loaded', 'failed')]
    if active_units:
        raise self.retry(exc=NodeNotStopped(name, version, active_units),
                         max_retries=check_retries+1,
                         countdown=check_interval)
    get_store().add_event(
        EVENT_DEPLOYMENTS_STOPPED,
        search_params=search_params,
        details={
            'deployment': {
                'name': name,
                'version': version,
                'exclude-version': exclude_version,
                'matching-units': deployed_units,
                'active-units': active_units
            }
        }
    )


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
                     if unit['sub'].lower() in FLEET_STARTED_STATES]
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
    deployment_id = deployment['id']
    notify_ctx = create_notify_ctx(deployment, 'create')

    store.add_event(EVENT_PROMOTED, search_params=search_params)
    store.update_state(deployment_id, DEPLOYMENT_STATE_PROMOTED)
    notification.notify.si(
        {'message': 'Promoted'}, ctx=notify_ctx,
        level=LEVEL_SUCCESS,
        notifications=deployment['notifications'],
        security_profile=deployment['security']['profile']).delay()
    return store.get_deployment(deployment_id)


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
        timeout = deployment['deployment']['stop']['timeout']
        check_retries = deployment['deployment']['stop']['check-retries']
        # Wait for a while before starting decommissioning the process
        # To given enough time for traffic to be moved to new deployment.
        # In future we can make this configurable
        tasks.append(_fleet_stop.subtask(
            (name,), {'exclude_version': version}, countdown=60,
            immutable=True))
        tasks.append(_wait_for_stop.si(
            name, exclude_version=version, timeout=timeout,
            check_retries=check_retries, search_params=search_params))
        tasks.append(
            _fleet_undeploy.si(name, exclude_version=version))
        tasks.append(_wait_for_undeploy.si(
            name, exclude_version=version, search_params=search_params
        ))

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
                                        next_task=next_task),
            options=DEFAULT_CHORD_OPTIONS
        ).delay()
    elif next_task:
        return next_task.delay()


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
    except (IOError, HTTPException) as exc:
        # Clear the current exception so that celery does not raise original
        # exception
        reason = exc.reason if hasattr(exc, 'reason') else repr(exc)
        kwargs = {'attempts': attempts}
        if hasattr(exc, 'read'):
            kwargs.update(response={'raw': exc.read()}, status=exc.code)

        sys.exc_clear()
        raise self.retry(
            exc=NodeCheckFailed(check_url, reason, **kwargs),
            max_retries=attempts-1,
            countdown=TASK_SETTINGS['CHECK_NODE_RETRY_DELAY'])


def _get_job_lock(job_name, raise_error=False):
    try:
        return LockService(lock_base=LOCK_JOB_BASE).apply_lock(job_name)
    except ResourceLockedException as lock_error:
        if raise_error:
            raise
        else:
            logger.info('Job:{} already running. Skipping...'.format(
                lock_error.name))


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

        return list(sync_upstreams(deployment['id'])
                    for deployment in deployments)
    finally:
        _release_lock.si(lock).delay()


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
            state=DEPLOYMENT_STATE_PROMOTED, only_ids=True)

        return list(sync_units(deployment['id'])
                    for deployment in deployments)
    finally:
        _release_lock.si(lock).delay()


@app.task(bind=True)
def recover_cluster(self, recovery_params):
    """
    Recovers the cluster by re-scheduling deployments

    :param recovery_params: Parameters for recovering cluster
    :type recovery_params: dict
    :return: GroupResult
    """
    logger.info('Begin Cluster recovery for: {}'.format(recovery_params))
    state = recovery_params.get('state', DEPLOYMENT_STATE_PROMOTED)

    deployments = get_store().filter_deployments(
        state=state,
        name=recovery_params.get('name'),
        version=recovery_params.get('version'),
        exclude_names=recovery_params.get('exclude-names')
    )

    return chord(
        group(create.si(clone_deployment(deployment))
              for deployment in deployments),
        async_wait.s(
            default_retry_delay=TASK_SETTINGS['DEPLOYMENT_WAIT_RETRY_DELAY'],
            max_retries=TASK_SETTINGS['DEPLOYMENT_WAIT_RETRIES']),
        options=DEFAULT_CHORD_OPTIONS
    ).delay()


@app.task(bind=True)
def _start_deployment(self, deployment_id, task_settings):
    store = get_store()
    concurrency = task_settings.get('START_CONCURRENCY')
    if concurrency and concurrency > 0:
        used_concurrency = len(store.filter_deployments(
                only_ids=True, state=DEPLOYMENT_STATE_STARTED))
        if used_concurrency >= concurrency:
            raise self.retry(
                exc=MaxStartConcurrencyReached(concurrency, used_concurrency),
                max_retries=task_settings['START_CONCURRENCY_RETRIES'],
                countdown=task_settings['START_CONCURRENCY_RETRY_DELAY'])
    store.update_state(deployment_id, DEPLOYMENT_STATE_STARTED)
