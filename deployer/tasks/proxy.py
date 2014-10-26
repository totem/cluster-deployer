"""
Tasks for yoda proxy. Uses yoda-py library for making calls to yoda.
"""
from __future__ import absolute_import
import logging
import yoda.client

from celery.canvas import chord, group
from deployer.celery import app
from conf.appconfig import TOTEM_ETCD_SETTINGS, DEPLOYMENT_MODE_BLUEGREEN
from yoda.model import Location, Host, TcpListener
from yoda.client import as_upstream

logger = logging.getLogger(__name__)


@app.task
def wire_proxy(app_name, app_version, proxy,
               deployment_mode=DEPLOYMENT_MODE_BLUEGREEN):
    """
    Wires proxy with yoda.

    :param deployment: Dictionary containing proxy settings.
    :return: None
    """

    use_version = app_version \
        if deployment_mode == DEPLOYMENT_MODE_BLUEGREEN else None

    proxy_host_tasks = [
        _wire_host.si(host, app_name, use_version)
        for host in proxy.get('hosts', [])
    ]

    proxy_listener_tasks = [
        _wire_listener.si(listener, app_name, use_version)
        for listener in proxy.get('listeners', [])
    ]

    return chord(
        group(proxy_host_tasks + proxy_listener_tasks),
        _wire_done.si(app_name, app_version, proxy, deployment_mode)
    )()


@app.task
def _wire_host(host, app_name, use_version):
    """
    Task for wiring up yoda proxy for a single host

    :param host: Dictionary containing host parameters. e.g.:
        {
            'hostname': 'myapp.example.com',
            'locations': [
                {
                    'port': 8080,
                    'path': '/',
                    'allowed-acls': ['public'],
                    'denied-acls': ['global-black-list']
                }
            ]
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
        ) for location in host['locations']]
    yoda_host = Host(host['hostname'], yoda_locations)
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
def _wire_done(app_name, app_version, proxy, deployment_mode):
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
    pass


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
    pass
