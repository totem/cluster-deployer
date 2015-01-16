"""
Tests for tasks defined in deployer.tasks.yoda
"""
from mock import patch, call
from nose.tools import eq_
from yoda import Host, Location
from deployer.tasks.proxy import wire_proxy

MOCK_APP = 'mock-app'
MOCK_VERSION = 'mock-version'


def _get_mock_proxy_with_hosts():
    return {
        'hosts': {
            'host1': {
                'hostname': 'mockhostname1',
                'locations': {
                    'loc1': {
                        'port': 8080,
                        'path': '/path1'
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
    result = wire_proxy.delay(MOCK_APP, MOCK_VERSION, proxy)
    result.get(timeout=1)

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
            location_name='loc1'
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
                'hostname': 'mockhostname1',
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
    result = wire_proxy.delay(MOCK_APP, MOCK_VERSION, proxy,
                              deployment_mode='a/b')
    result.get(timeout=1)

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
            ]
        ))
    ])
