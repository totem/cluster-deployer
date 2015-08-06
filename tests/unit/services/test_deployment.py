from mock import patch
from nose.tools import eq_
from deployer.services.deployment import get_exposed_ports, \
    fetch_runtime_upstreams
from deployer.util import dict_merge
from tests.helper import dict_compare


def _create_test_deployment():
    return {
        'meta-info': {
            'job-id': 'test-job',
            'git': {
                'owner': 'testowner',
                'repo': 'testrepo',
                'ref': 'testref',
                'commit': 'testcommit'

            }
        },
        'deployment': {
            'type': 'git-quay',
            'name': 'testowner-testrepo-v1',
            'version': 'v1'
        }
    }


def test_get_exposed_ports_with_no_proxy():

    # Given: Deployment parameters (w/o proxy)
    deployment = _create_test_deployment()

    # When: I get exposed ports for deployment
    ports = get_exposed_ports(deployment)

    # Then: Empty set is returned
    eq_(ports, [])


def test_get_exposed_ports_with_hosts_and_listeners():

    # Given: Deployment parameters
    deployment = _create_test_deployment()
    deployment = dict_merge(deployment, {
        'proxy': {
            'hosts': {
                'host1': {
                    'locations': {
                        'loc1': {
                            'port': 8080,
                            },
                        'loc2': {
                            'port': 8081
                        }
                    }
                },
                'host2': {
                    'locations': {
                        'loc3': {
                            'port': 8080
                        },
                        'loc4': {
                            'port': 8082
                        }
                    }
                }
            },
            'listeners': {
                'ssh': {
                    'upstream-port': 22
                }
            }
        }

    })

    # When: I get exposed ports for deployment
    ports = get_exposed_ports(deployment)

    # Then: Empty set is returned
    eq_(ports, [22, 8080, 8081, 8082])


@patch('deployer.services.deployment.get_discovered_nodes')
def test_fetch_runtime_upstreams(m_get_discovered_nodes):
    # Given: Deployment parameters (w/o proxy)
    deployment = dict_merge(_create_test_deployment(), {
        'proxy': {
            'hosts': {
                'host1': {
                    'locations': {
                        'loc1': {
                            'port': 8080
                        }
                    }
                }
            }
        }
    })

    # And: Registered nodes for given deployment
    m_get_discovered_nodes.side_effect = [{
        'endpoint1': 'host1:40001',
        'endpoint2': 'host2:40001'
    }]

    # When: I fetch upstreams for given deployment
    upstreams = fetch_runtime_upstreams(deployment)

    # Then: Expected upstreams are returned
    dict_compare(upstreams, {
        '8080': {
            'endpoint1': 'host1:40001',
            'endpoint2': 'host2:40001'
        }
    })
