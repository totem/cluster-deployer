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
        'hosts': [
            {
                'hostname': 'mockhostname1',
                'locations': [
                    {
                        'port': 8080,
                        'path': '/path1'
                    },
                    {
                        'port': 8081,
                        'path': '/path2'
                    }
                ]
            },
            {
                'hostname': 'mockhostname2',
                'locations': [
                    {
                        'port': 80,
                        'path': '/path3',
                        'allowed-acls': ['allowed-acl1', 'allowed-acl2'],
                        'denied-acls': ['denied-acl1']
                    }
                ]
            }
        ]
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
    eq_(mock_yoda_cl().wire_proxy.call_args_list, [
        call(Host(
            hostname='mockhostname1',
            locations=[
                Location(
                    upstream='mock-app-mock-version-8080',
                    path='/path1'
                ),
                Location(
                    upstream='mock-app-mock-version-8081',
                    path='/path2'
                )
            ]
        )),

        call(Host(
            hostname='mockhostname2',
            locations=[
                Location(
                    upstream='mock-app-mock-version-80',
                    path='/path3',
                    allowed_acls=['allowed-acl1', 'allowed-acl2'],
                    denied_acls=['denied-acl1']
                )
            ]
        ))

    ])


@patch('yoda.client.Client')
def test_wire_for_ab(mock_yoda_cl):

    # Given: Mock Proxy, application that needs to be wired
    proxy = {
        'hosts': [
            {
                'hostname': 'mockhostname1',
                'locations': [
                    {
                        'port': 8080,
                        'path': '/path1'
                    }
                ]
            }
        ]
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
                    upstream='mock-app-8080',
                    path='/path1'
                )
            ]
        ))
    ])
