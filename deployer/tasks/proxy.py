"""
Tasks for yoda proxy. Uses yoda-py library for making calls to yoda.
"""
from __future__ import absolute_import
import logging
import re
import yoda.client

from celery.canvas import chord, group
from deployer.celery import app
from conf.appconfig import TOTEM_ETCD_SETTINGS, DEPLOYMENT_MODE_BLUEGREEN, \
    TASK_SETTINGS
from yoda.model import Location, Host, TcpListener
from yoda.client import as_upstream
from deployer.tasks.exceptions import MinNodesNotDiscovered

logger = logging.getLogger(__name__)


@app.task
def wire_proxy(app_name, app_version, proxy,
               deployment_mode=DEPLOYMENT_MODE_BLUEGREEN,
               ret_value=None, next_task=None):
    """
    Wires proxy with yoda.

    :param deployment: Dictionary containing proxy settings.
    :return: None
    """

    use_version = app_version \
        if deployment_mode == DEPLOYMENT_MODE_BLUEGREEN else None

    proxy_host_tasks = [
        _wire_host.si(host, app_name, use_version)
        for host in proxy.get('hosts', {}).values()
        if proxy.get('enabled', True)
    ]

    proxy_listener_tasks = [
        _wire_listener.si(listener, app_name, use_version)
        for listener in proxy.get('listeners', {}).values()
        if listener.get('enabled', True)
    ]

    return chord(
        group(proxy_host_tasks + proxy_listener_tasks),
        _wire_done.si(app_name, app_version, proxy, deployment_mode,
                      ret_value=ret_value, next_task=next_task)
    )()


@app.task
def register_upstreams(app_name, app_version, upstreams,
                       deployment_mode=DEPLOYMENT_MODE_BLUEGREEN,
                       next_task=None):
    """
    Register upstream with yoda

    :param app_name: Application name
    :param app_version: Application version. (Can be None for non blue-green
        deploys.
    :param upstreams: Dictionary comprising of all upstreams that needs to
        registered.
    :param deployment_mode: Mode of deploy( 'red-green', 'bluee-green', 'a/b')
    :param next_task: Next task to be executed if Not None
    :return: Result of next task if passed else None.
    """
    yoda_cl = _get_yoda_cl()
    use_version = app_version \
        if deployment_mode == DEPLOYMENT_MODE_BLUEGREEN else None
    for port, upstream in upstreams.iteritems():
        upstream_name = as_upstream(app_name, port, app_version=use_version)
        health = upstream.get('health', {})
        yoda_cl.register_upstream(
            upstream_name, mode=upstream.get('mode', 'http'),
            health_uri=health.get('uri'), health_timeout=health.get('timeout'),
            health_interval=health.get('interval')
        )
    return next_task() if next_task else None


@app.task
def _wire_host(host, app_name, use_version):
    """
    Task for wiring up yoda proxy for a single host

    :param host: Dictionary containing host parameters. e.g.:
        {
            'hostname': 'myapp.example.com,mapp2.example.com',
            'locations': {
                'home': {
                    'port': 8080,
                    'path': '/',
                    'allowed-acls': ['public'],
                    'denied-acls': ['global-black-list'],
                    'force-ssl': False
                }
            }
        }
    :type host: dict
    :param app_name: Application Name. e.g.: totem-spec-python-develop
    :type app_name: str
    :param use_version: Application Version. Required only for Blue Green
        deploys.  (e.g.: 12312)
    :type use_version: str
    :return: None
    """

    yoda_cl = _get_yoda_cl()
    yoda_locations = [
        Location(
            as_upstream(app_name, location['port'], use_version),
            path=location['path'],
            allowed_acls=location.get('allowed-acls', []),
            denied_acls=location.get('denied-acls', []),
            location_name=location_key,
            force_ssl=location.get('force-ssl', False)
        ) for location_key, location in host['locations'].iteritems()]
    hostnames = [hostname.strip() for hostname in
                 re.split('[\\s,]*', host['hostname']) if hostname]
    yoda_host = Host(hostnames[0], yoda_locations, aliases=hostnames[1:])
    yoda_cl.wire_proxy(yoda_host)


@app.task
def _wire_listener(listener, app_name, use_version):
    """
    Wires TCP listener for application.

    :param listener: Dictionary containing listener configuration. e.g.:
        {
            'bind': '0.0.0.0:5437',
            'upstream-port': 5457,
            'allowed-acls': ['public'],
            'denied-acls': ['global-black-list']
        }
    :type listener: dict
    :param app_name: Application name
    :type app_name: str
    :param use_version: Use application version for creating upstream.
    :type use_version: str
    :return: None
    """
    yoda_cl = _get_yoda_cl()
    yoda_listener = TcpListener(
        listener['name'], listener['bind'],
        upstream=as_upstream(app_name, listener['upstream-port'],
                             app_version=use_version),
        allowed_acls=listener.get('allowed-acls', []),
        denied_acls=listener.get('denied-acls', [])
    )
    yoda_cl.update_tcp_listener(yoda_listener)


@app.task
def _wire_done(app_name, app_version, proxy, deployment_mode, ret_value=None,
               next_task=None):
    """
    Carries out post wiring actions (los, auditing, event streaming, ...)
    :param app_name:
    :param app_version:
    :param proxy:
    :param deployment_mode:
    :return:
    """
    logger.info('Proxy wired successfully for app_name:%s app_version:%s '
                'proxy:%r deployment_mode:%s', app_name, app_version, proxy,
                deployment_mode)
    if next_task:
        return next_task()
    else:
        return ret_value


@app.task(bind=True,
          default_retry_delay=TASK_SETTINGS['CHECK_DISCOVERY_RETRY_DELAY'],
          max_retries=TASK_SETTINGS['CHECK_DISCOVERY_RETRIES'])
def _check_discover(self, app_name, app_version, check_port, min_nodes,
                    deployment_mode):
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
        logger.debug('Skip discover check as no port was defined for %s:%s',
                     app_name, app_version)
        return {}
    yoda_cl = _get_yoda_cl()
    use_version = app_version \
        if deployment_mode == DEPLOYMENT_MODE_BLUEGREEN else None
    upstream = as_upstream(app_name, check_port, app_version=use_version)
    discovered_nodes = yoda_cl.get_nodes(upstream)
    if len(discovered_nodes) < min_nodes:
        raise self.retry(exc=MinNodesNotDiscovered(
            app_name, app_version, min_nodes, discovered_nodes))
    else:
        return discovered_nodes


def _get_yoda_cl():
    """
    Creates yoda client instance.
    :return: Yoda Client
    :rtype: yoda.client.Client
    """
    return yoda.client.Client(
        etcd_host=TOTEM_ETCD_SETTINGS['host'],
        etcd_port=TOTEM_ETCD_SETTINGS['port'],
        etcd_base=TOTEM_ETCD_SETTINGS['yoda_base'])
