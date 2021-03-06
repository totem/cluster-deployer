"""
Tests proxy service methods
"""
from mock import patch, call
from nose.tools import eq_
from yoda import Host, Location
from conf.appconfig import DEPLOYMENT_MODE_BLUEGREEN, DEPLOYMENT_MODE_AB
from deployer.services.proxy import wire_proxy, register_upstreams, \
    get_discovered_nodes


MOCK_APP = 'mock-app'
MOCK_VERSION = 'mock-version'
DEFAULT_TTL_MS = 604800


def _get_mock_proxy_with_hosts():
    return {
        'hosts': {
            'host1': {
                'hostname': 'mockhostname1',
                'locations': {
                    'loc1': {
                        'port': 8080,
                        'path': '/path1',
                        'force-ssl': True
                    },
                    'loc2': {
                        'port': 8081,
                        'path': '/path2'
                    }
                }
            },
            'host2': {
                'hostname': 'mockhostname2',
                'locations': {
                    'loc3': {
                        'port': 80,
                        'path': '/path3',
                        'allowed-acls': ['allowed-acl1', 'allowed-acl2'],
                        'denied-acls': ['denied-acl1']
                    }
                }
            }
        }
    }


@patch('yoda.client.Client')
def test_wire_for_bluegreen(mock_yoda_cl):

    # Given: Mock Proxy, application that needs to be wired
    proxy = _get_mock_proxy_with_hosts()

    # When: I wire the proxy
    wire_proxy(MOCK_APP, MOCK_VERSION, proxy)

    # Then: Yoda proxy hosts are created using given version
    eq_(mock_yoda_cl().wire_proxy.call_count, 2)

    hosts = sorted(
        (mcall[0][0] for mcall in mock_yoda_cl().wire_proxy.call_args_list),
        key=lambda obj: obj.hostname)

    eq_(hosts[0].hostname, 'mockhostname1')
    eq_(hosts[1].hostname, 'mockhostname2')

    eq_(sorted(hosts[0].locations, key=lambda obj: obj.location_name), [
        Location(
            upstream='mock-app-mock-version-8080',
            path='/path1',
            location_name='loc1',
            force_ssl=True,
        ),
        Location(
            upstream='mock-app-mock-version-8081',
            path='/path2',
            location_name='loc2'
        )
        ])

    eq_(hosts[1].locations, [
        Location(
            location_name='loc3',
            upstream='mock-app-mock-version-80',
            path='/path3',
            allowed_acls=['allowed-acl1', 'allowed-acl2'],
            denied_acls=['denied-acl1']
        )
        ])


@patch('yoda.client.Client')
def test_wire_for_ab(mock_yoda_cl):

    # Given: Mock Proxy, application that needs to be wired
    proxy = {
        'hosts': {
            'host1': {
                'hostname': 'mockhostname1, mockhostname2,',
                'locations': {
                    'home': {
                        'port': 8080,
                        'path': '/path1'
                    }
                }
            }
        }
    }

    # When: I wire the proxy in a/b mode
    wire_proxy(MOCK_APP, MOCK_VERSION, proxy,
               deployment_mode=DEPLOYMENT_MODE_AB)

    # Then: Yoda proxy hosts are created as expected
    eq_(mock_yoda_cl().wire_proxy.call_count, 1)
    eq_(mock_yoda_cl().wire_proxy.call_args_list, [
        call(Host(
            hostname='mockhostname1',
            locations=[
                Location(
                    location_name='home',
                    upstream='mock-app-8080',
                    path='/path1'
                )
            ],
            aliases=['mockhostname2']
        ))
    ])


@patch('yoda.client.Client')
def test_register_upstreams_for_blue_green(mock_yoda_cl):

    # Given: Upstreams that needs to be registered
    upstreams = {
        '8080': {
            'mode': 'http',
            'health': {
                'uri': '/health',
                'timeout': '5s',
                'interval': '5m'
            }
        },
        '22': {
            'mode': 'tcp'
        }
    }

    # When: I wire the proxy in a/b mode
    register_upstreams(
        MOCK_APP, MOCK_VERSION, upstreams, deployment_mode='blue-green')

    # Then: Upstreams get registered
    eq_(mock_yoda_cl().register_upstream.call_count, 2)
    eq_(mock_yoda_cl().register_upstream.call_args_list, [
        call('mock-app-mock-version-8080', health_uri='/health',
             health_timeout='5s', mode='http', health_interval='5m',
             ttl=DEFAULT_TTL_MS),
        call('mock-app-mock-version-22', health_uri=None,
             health_timeout=None, mode='tcp', health_interval=None,
             ttl=DEFAULT_TTL_MS),
        ])


@patch('yoda.client.Client')
def test_register_upstreams_for_ab_deploy(mock_yoda_cl):

    # Given: Upstreams that needs to be registered
    upstreams = {
        '8080': {
            'mode': 'http',
            'health': {
                'uri': '/health',
                'timeout': '5s'
            }
        },
        '22': {
            'mode': 'tcp'
        }
    }

    # When: I wire the proxy in a/b mode
    register_upstreams(
        MOCK_APP, MOCK_VERSION, upstreams, deployment_mode='a/b')

    # Then: Upstreams get registered
    eq_(mock_yoda_cl().register_upstream.call_count, 2)
    eq_(mock_yoda_cl().register_upstream.call_args_list, [
        call('mock-app-8080', health_uri='/health',
             health_timeout='5s', mode='http', health_interval=None,
             ttl=DEFAULT_TTL_MS),
        call('mock-app-22', health_uri=None,
             health_timeout=None, mode='tcp', health_interval=None,
             ttl=DEFAULT_TTL_MS)
        ])


@patch('yoda.client.Client')
def test_check_discover_when_port_is_not_defined(mock_yoda_cl):

    # When: I check discover for app with no check-port defined
    nodes = get_discovered_nodes('mockapp', 'mockversion', None,
                                 DEPLOYMENT_MODE_BLUEGREEN)

    # Then: Discover check is skipped
    eq_(nodes, {})
    eq_(mock_yoda_cl.call_count, 0)


@patch('yoda.client.Client')
def test_check_discover_for_existing_nodes(mock_yoda_cl):
    # Given: Existing nodes
    mock_yoda_cl().get_nodes.return_value = {
        'node1': 'mockhost1:48080',
        'node2': 'mockhost2:47080'
    }

    # When: I check discover for app with no check-port defined
    nodes = get_discovered_nodes(
        'mockapp', 'mockversion', 8080, DEPLOYMENT_MODE_BLUEGREEN)

    # Then: Discover check passes
    eq_(nodes, mock_yoda_cl().get_nodes.return_value)
    mock_yoda_cl().get_nodes.assert_called_once_with(
        'mockapp-mockversion-8080')


@patch('yoda.client.Client')
def test_check_discover_for_existing_nodes_with_ab_deploy(mock_yoda_cl):
    # Given: Existing nodes
    mock_yoda_cl().get_nodes.return_value = {
        'node1': 'mockhost1:48080',
        'node2': 'mockhost2:47080'
    }

    # When: I check discover for app with no check-port defined
    nodes = get_discovered_nodes(
        'mockapp', 'mockversion', 8080, DEPLOYMENT_MODE_AB)

    # Then: Discover check passes
    eq_(nodes, mock_yoda_cl().get_nodes.return_value)
    mock_yoda_cl().get_nodes.assert_called_once_with(
        'mockapp-8080')
