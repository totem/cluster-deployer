import re
import yoda
from conf.appconfig import DEPLOYMENT_MODE_BLUEGREEN, TOTEM_ETCD_SETTINGS, \
    UPSTREAM_DEFAULTS
from yoda.model import Location, Host, TcpListener
from yoda.client import as_upstream
from deployer.util import to_milliseconds

__author__ = 'sukrit'

"""
Module that provides service methods for doing different operations releated
to proxy
"""


def get_proxy_client():
    """
    Creates yoda client instance.
    :return: Yoda Client
    :rtype: yoda.client.Client
    """
    return yoda.client.Client(
        etcd_host=TOTEM_ETCD_SETTINGS['host'],
        etcd_port=TOTEM_ETCD_SETTINGS['port'],
        etcd_base=TOTEM_ETCD_SETTINGS['yoda_base'])


def wire_host(host, app_name, use_version):
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

    yoda_cl = get_proxy_client()
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


def wire_listener(listener, app_name, use_version):
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
    yoda_cl = get_proxy_client()
    yoda_listener = TcpListener(
        listener['name'], listener['bind'],
        upstream=as_upstream(app_name, listener['upstream-port'],
                             app_version=use_version),
        allowed_acls=listener.get('allowed-acls', []),
        denied_acls=listener.get('denied-acls', [])
    )
    yoda_cl.update_tcp_listener(yoda_listener)


def wire_proxy(app_name, app_version, proxy,
               deployment_mode=DEPLOYMENT_MODE_BLUEGREEN):
    """
    Wires proxy with yoda.

    :param deployment: Dictionary containing proxy settings.
    :type deployment: dict
    :return: None
    """

    use_version = app_version \
        if deployment_mode == DEPLOYMENT_MODE_BLUEGREEN else None

    for host in proxy.get('hosts', {}).values():
        if host.get('enabled', True):
            wire_host(host, app_name, use_version)

    for listener in proxy.get('listeners', {}).values():
        if listener.get('enabled', True):
            wire_listener(listener, app_name, use_version)


def register_upstreams(
        app_name, app_version, upstreams,
        deployment_mode=DEPLOYMENT_MODE_BLUEGREEN):
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
    yoda_cl = get_proxy_client()
    use_version = app_version \
        if deployment_mode == DEPLOYMENT_MODE_BLUEGREEN else None
    for port, upstream in upstreams.iteritems():
        upstream_name = as_upstream(app_name, port, app_version=use_version)
        health = upstream.get('health', {})
        yoda_cl.register_upstream(
            upstream_name, mode=upstream.get('mode', 'http'),
            health_uri=health.get('uri'), health_timeout=health.get('timeout'),
            health_interval=health.get('interval'),
            ttl=to_milliseconds(
                upstream.get('ttl', UPSTREAM_DEFAULTS['ttl'])) / 1000
        )


def get_discovered_nodes(app_name, app_version, check_port, deployment_mode):
    """
    Gets the discovered nodes for given application
    :param app_name: Application name
    :type app_name: str
    :param app_version: Application version
    :type app_version: str
    :param check_port: Port to be used discover check. If None, empty dict is
        returned
    :param deployment_mode: mode of deploy (blue-green, red-green, a/b etc)
    :return: discovered nodes
    :rtype: dict
    """

    if check_port is None:
        return {}

    yoda_cl = get_proxy_client()
    use_version = app_version \
        if deployment_mode == DEPLOYMENT_MODE_BLUEGREEN else None
    upstream = as_upstream(app_name, check_port, app_version=use_version)
    return yoda_cl.get_nodes(upstream)
