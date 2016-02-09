import datetime
from freezegun import freeze_time
from mock import patch
from nose.tools import eq_, raises
from conf.appconfig import DEPLOYMENT_MODE_BLUEGREEN, DEFAULT_STOP_TIMEOUT, \
    TASK_SETTINGS, DEPLOYMENT_STATE_STARTED, NOTIFICATIONS_DEFAULTS, \
    CLUSTER_NAME, DISCOVER_UPSTREAM_TTL_DEFAULT
from deployer.services.deployment import get_exposed_ports, \
    fetch_runtime_upstreams, apply_defaults, sync_upstreams, sync_units, \
    clone_deployment
from deployer.util import dict_merge
from tests.helper import dict_compare

NOW = datetime.datetime(2014, 01, 01)
DEFAULT_STOP_TIMEOUT_SECONDS = 30


def _create_test_deployment(additional_params=None):
    return dict_merge(additional_params, {
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
            'type': 'git-quay'
        }
    })


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
    deployment = _create_test_deployment({
        'deployment': {
            'name': 'test',
            'version': 'v1'
        },
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
        'endpoint1': {
            'endpoint': 'host1:40001',
            'node-num': '1'
        },
        'endpoint2': {
            'endpoint': 'host2:40001',
            'node-num': '2'
        }
    }]

    # When: I fetch upstreams for given deployment
    upstreams = fetch_runtime_upstreams(deployment)

    # Then: Expected upstreams are returned
    dict_compare(upstreams, {
        '8080': [
            {
                'endpoint': 'host1:40001',
                'name': 'endpoint1',
                'node-num': '1'
            },
            {
                'endpoint': 'host2:40001',
                'name': 'endpoint2',
                'node-num': '2'
            }
        ]
    })


@freeze_time(NOW)
@patch('time.time')
def test_deployment_defaults_for_type_git_quay(mock_time):
    """Should get defaults for deployment of type git-quay"""

    # Given: Deployment dictionary
    deployment = _create_test_deployment()

    # Mock Time call for creating version
    mock_time.return_value = 0.1006

    # When: I apply defaults for deployment
    depl_with_defaults = apply_defaults(deployment)

    # Then: Defaults for deployment are applied
    dict_compare(depl_with_defaults, {
        'meta-info': {
            'job-id': 'test-job',
            'git': {
                'owner': 'testowner',
                'repo': 'testrepo',
                'ref': 'testref',
                'commit': 'testcommit',
                'type': 'github'
            }
        },
        'deployment': {
            'name': 'testowner-testrepo-testref',
            'type': 'git-quay',
            'version': '101',
            'nodes': 1,
            'mode': DEPLOYMENT_MODE_BLUEGREEN,
            'check': {
                'min-nodes': 1,
                'port': None,
                'attempts': 10,
                'timeout': '10s'
            },
            'stop': {
                'timeout': DEFAULT_STOP_TIMEOUT,
                'check-retries':
                    TASK_SETTINGS['DEFAULT_DEPLOYMENT_STOP_CHECK_RETRIES']
            }
        },
        'templates': {
            'app': {
                'args': {
                    'environment': {
                        'DISCOVER_PORTS': '',
                        'DISCOVER_MODE': DEPLOYMENT_MODE_BLUEGREEN,
                        'DISCOVER_HEALTH': '{}',
                        'DISCOVER_UPSTREAM_TTL': DISCOVER_UPSTREAM_TTL_DEFAULT
                    },
                    'docker-args': '',
                    'image': 'quay.io/totem/testowner-testrepo:testcommit',
                    'sidekicks': ['yoda-register'],
                    'service': {
                        'container-stop-sec': DEFAULT_STOP_TIMEOUT_SECONDS
                    }
                },
                'enabled': True,
                'name': 'default-app'
            },
            'yoda-register': {
                'args': {},
                'enabled': True,
                'name': 'yoda-register'
            }
        },
        'id': 'local-testowner-testrepo-testref-101',
        'proxy': {
            'hosts': {},
            'listeners': {},
            'upstreams': {}
        },
        'state': DEPLOYMENT_STATE_STARTED,
        'started-at': NOW,
        'security': {
            'profile': 'default'
        },
        'notifications': NOTIFICATIONS_DEFAULTS,
        'cluster': CLUSTER_NAME,
        'runtime': {},
        'environment': {}
    })


@freeze_time(NOW)
@patch('time.time')
def test_deployment_defaults_with_proxy(mock_time):
    """Should get defaults for deployment with proxy"""

    # Given: Deployment dictionary
    deployment = _create_test_deployment()
    deployment = dict_merge(deployment, {
        'proxy': {
            'hosts': {
                'host1': {
                    'locations': {
                        'loc1': {
                            'port': 8080,
                            'path': '/loc1'
                        },
                        'loc2': {
                            'port': 8081,
                            'path': '/loc2'
                        },
                        'loc3': {
                            'port': 8082,
                            'path': '/loc3'
                        }
                    }
                }
            },
            'upstreams': {
                '8080': {},
                '8081': {
                    'mode': 'tcp'
                }
            }
        }
    })

    # Mock Time call for creating version
    mock_time.return_value = 0.1006

    # When: I apply defaults for deployment
    depl_with_defaults = apply_defaults(deployment)

    # Then: Defaults for deployment are applied
    dict_compare(depl_with_defaults, {
        'meta-info': {
            'job-id': 'test-job',
            'git': {
                'owner': 'testowner',
                'repo': 'testrepo',
                'ref': 'testref',
                'commit': 'testcommit',
                'type': 'github'
            }
        },
        'deployment': {
            'name': 'testowner-testrepo-testref',
            'type': 'git-quay',
            'version': '101',
            'nodes': 1,
            'mode': DEPLOYMENT_MODE_BLUEGREEN,
            'check': {
                'min-nodes': 1,
                'port': None,
                'attempts': 10,
                'timeout': '10s'
            },
            'stop': {
                'timeout': DEFAULT_STOP_TIMEOUT,
                'check-retries':
                    TASK_SETTINGS['DEFAULT_DEPLOYMENT_STOP_CHECK_RETRIES']
            }
        },
        'templates': {
            'app': {
                'args': {
                    'environment': {
                        'DISCOVER_PORTS': '8080,8081,8082',
                        'DISCOVER_MODE': DEPLOYMENT_MODE_BLUEGREEN,
                        'DISCOVER_HEALTH': '{"8080": {"timeout": "5s"},'
                                           ' "8081": {"timeout": "5s"},'
                                           ' "8082": {"timeout": "5s"}}',
                        'DISCOVER_UPSTREAM_TTL': DISCOVER_UPSTREAM_TTL_DEFAULT
                    },
                    'docker-args': '',
                    'image': 'quay.io/totem/testowner-testrepo:testcommit',
                    'sidekicks': ['yoda-register'],
                    'service': {
                        'container-stop-sec': DEFAULT_STOP_TIMEOUT_SECONDS
                    }
                },
                'enabled': True,
                'name': 'default-app'
            },
            'yoda-register': {
                'args': {},
                'enabled': True,
                'name': 'yoda-register'
            }
        },
        'id': 'local-testowner-testrepo-testref-101',
        'proxy': {
            'hosts': {
                'host1': {
                    'locations': {
                        'loc1': {
                            'port': 8080,
                            'path': '/loc1'
                        },
                        'loc2': {
                            'port': 8081,
                            'path': '/loc2'
                        },
                        'loc3': {
                            'port': 8082,
                            'path': '/loc3'
                        }
                    }
                }
            },
            'upstreams': {
                '8080': {
                    'mode': 'http',
                    'health': {
                        'timeout': '5s'
                    },
                    'ttl': '1w'
                },
                '8081': {
                    'mode': 'tcp',
                    'health': {
                        'timeout': '5s'
                    },
                    'ttl': '1w'
                },
                '8082': {
                    'mode': 'http',
                    'health': {
                        'timeout': '5s'
                    },
                    'ttl': '1w'
                }
            },
            'listeners': {}
        },
        'state': DEPLOYMENT_STATE_STARTED,
        'started-at': NOW,
        'security': {
            'profile': 'default'
        },
        'notifications': NOTIFICATIONS_DEFAULTS,
        'cluster': CLUSTER_NAME,
        'runtime': {},
        'environment': {}
    })


@freeze_time(NOW)
@patch('time.time')
def test_deployment_defaults_for_type_git_quay_with_overrides(mock_time):
    """Should get defaults for deployment of type git-quay"""

    # Given: Deployment dictionary
    deployment = _create_test_deployment({
        'templates': {
            'logger': {
                'name': 'default-logger',
                'enabled': False,
            },
            'app': {
                'args': {
                    'environment': {
                        'MOCK_ENV1': 'MOCK_VAL1_OVERRIDE'
                    }
                }

            }
        },
        'environment': {
            'MOCK_ENV1': 'MOCK_VAL1',
            'MOCK_ENV2': 'MOCK_VAL2'
        }
    })

    # Mock Time call for creating version
    mock_time.return_value = 1

    # When: I apply defaults for deployment
    depl_with_defaults = apply_defaults(deployment)

    # Then: Defaults for deployment are applied
    dict_compare(depl_with_defaults, {
        'meta-info': {
            'job-id': 'test-job',
            'git': {
                'owner': 'testowner',
                'repo': 'testrepo',
                'ref': 'testref',
                'commit': 'testcommit',
                'type': 'github'
            }
        },
        'deployment': {
            'name': 'testowner-testrepo-testref',
            'type': 'git-quay',
            'version': '1000',
            'nodes': 1,
            'mode': DEPLOYMENT_MODE_BLUEGREEN,
            'check': {
                'min-nodes': 1,
                'port': None,
                'attempts': 10,
                'timeout': '10s'
            },
            'stop': {
                'timeout': DEFAULT_STOP_TIMEOUT,
                'check-retries':
                    TASK_SETTINGS['DEFAULT_DEPLOYMENT_STOP_CHECK_RETRIES']
            }
        },
        'templates': {
            'app': {
                'args': {
                    'environment': {
                        'DISCOVER_PORTS': '',
                        'DISCOVER_MODE': DEPLOYMENT_MODE_BLUEGREEN,
                        'DISCOVER_HEALTH': '{}',
                        'DISCOVER_UPSTREAM_TTL': DISCOVER_UPSTREAM_TTL_DEFAULT,
                        'MOCK_ENV1': 'MOCK_VAL1_OVERRIDE',
                        'MOCK_ENV2': 'MOCK_VAL2'
                    },
                    'docker-args': '',
                    'image': 'quay.io/totem/testowner-testrepo:testcommit',
                    'sidekicks': ['yoda-register'],
                    'service': {
                        'container-stop-sec': DEFAULT_STOP_TIMEOUT_SECONDS
                    }
                },
                'enabled': True,
                'name': 'default-app'
            },
            'yoda-register': {
                'args': {},
                'enabled': True,
                'name': 'yoda-register'
            },
            'logger': {
                'args': {},
                'enabled': False,
                'name': 'default-logger'
            }
        },
        'id': 'local-testowner-testrepo-testref-1000',
        'proxy': {
            'hosts': {},
            'listeners': {},
            'upstreams': {}
        },
        'state': DEPLOYMENT_STATE_STARTED,
        'started-at': NOW,
        'security': {
            'profile': 'default'
        },
        'notifications': NOTIFICATIONS_DEFAULTS,
        'cluster': CLUSTER_NAME,
        'runtime': {},
        'environment': deployment['environment']
    })


@freeze_time(NOW)
@patch('time.time')
def test_deployment_defaults_for_custom_deployment(mock_time):
    """Should get defaults for deployment of type git-quay"""

    # Given: Deployment dictionary
    deployment = _create_test_deployment()
    deployment['deployment'] = {
        'name': 'testdeployment',
        'type': 'custom',
        'nodes': 3
    }

    deployment['templates'] = {
        'app': {
            'args': {
                'arg1': 'value1'
            },
            'name': 'custom-app'
        },
        'logger': {
            'args': {
                'arg1': 'value1'
            },
            'name': 'custom-logger',
            'enabled': False
        }
    }

    # Mock Time call for creating version
    mock_time.return_value = 1

    # When: I apply defaults for deployment
    depl_with_defaults = apply_defaults(deployment)

    # Then: Defaults for deployment are applied
    dict_compare(depl_with_defaults, {
        'meta-info': {
            'job-id': 'test-job',
            'git': {
                'owner': 'testowner',
                'repo': 'testrepo',
                'ref': 'testref',
                'commit': 'testcommit',
                'type': 'github'
            }
        },
        'deployment': {
            'name': 'testdeployment',
            'type': 'custom',
            'version': '1000',
            'nodes': 3,
            'mode': DEPLOYMENT_MODE_BLUEGREEN,
            'check': {
                'min-nodes': 1,
                'port': None,
                'attempts': 10,
                'timeout': '10s'
            },
            'stop': {
                'timeout': DEFAULT_STOP_TIMEOUT,
                'check-retries':
                    TASK_SETTINGS['DEFAULT_DEPLOYMENT_STOP_CHECK_RETRIES']
            }
        },
        'templates': {
            'app': {
                'args': {
                    'arg1': 'value1',
                    'environment': {
                        'DISCOVER_PORTS': '',
                        'DISCOVER_MODE': DEPLOYMENT_MODE_BLUEGREEN,
                        'DISCOVER_HEALTH': '{}',
                        'DISCOVER_UPSTREAM_TTL': DISCOVER_UPSTREAM_TTL_DEFAULT
                    },
                    'service': {
                        'container-stop-sec': DEFAULT_STOP_TIMEOUT_SECONDS
                    },
                    'sidekicks': []
                },
                'enabled': True,
                'name': 'custom-app'
            },
            'logger': {
                'args': {
                    'arg1': 'value1'
                },
                'enabled': False,
                'name': 'custom-logger'
            }
        },
        'id': 'local-testdeployment-1000',
        'proxy': {
            'hosts': {},
            'listeners': {},
            'upstreams': {}
        },
        'state': DEPLOYMENT_STATE_STARTED,
        'started-at': NOW,
        'security': {
            'profile': 'default'
        },
        'notifications': NOTIFICATIONS_DEFAULTS,
        'cluster': CLUSTER_NAME,
        'runtime': {},
        'environment': {}
    })


@patch('deployer.services.deployment.get_store')
@patch('deployer.services.deployment.get_discovered_nodes')
def test_sync_upstreams(m_get_discovered_nodes, m_get_store):

    # Given: Existing deployment
    m_get_store.return_value.get_deployment.return_value = {
        'deployment': {
            'name': 'test',
            'version': 'v1',
            'mode': DEPLOYMENT_MODE_BLUEGREEN
        },
        'proxy': {
            'hosts': {
                'mock-host': {
                    'locations': {
                        'home': {
                            'port': 8090
                        }
                    }
                }
            }
        }
    }

    # And: Discovered Nodes
    m_get_discovered_nodes.return_value = {
        'upstream1': {
            'endpoints': {
                'endpoint1': {
                    'endpoint': 'host1:8091',
                }
            }
        }
    }

    # When: I synchronize upstreams for existing deployment
    ret_value = sync_upstreams('mock')

    # Then: Upstreams are synchronized as expected:
    dict_compare(ret_value, {
        'deployment_id': 'mock',
        'state': 'success',
        'upstreams': {
            '8090': [{
                'endpoints': {
                    'endpoint1': {
                        'endpoint': 'host1:8091',
                    }
                },
                'name': 'upstream1'
            }]
        }
    })


@patch('deployer.services.deployment.get_store')
@patch('deployer.services.deployment.get_discovered_nodes')
def test_sync_upstreams_with_error_fetching_nodes(
        m_get_discovered_nodes, m_get_store):

    # Given: Existing deployment
    m_get_store.return_value.get_deployment.return_value = {
        'deployment': {
            'name': 'test',
            'version': 'v1',
            'mode': DEPLOYMENT_MODE_BLUEGREEN
        },
        'proxy': {
            'hosts': {
                'mock-host': {
                    'locations': {
                        'home': {
                            'port': 8090
                        }
                    }
                }
            }
        }
    }

    # And: Discovered Nodes
    m_get_discovered_nodes.side_effect = Exception('Mock')

    # When: I synchronize upstreams for existing deployment
    ret_value = sync_upstreams('mock')

    # Then: Upstreams are synchronized as expected:
    dict_compare(ret_value, {
        'deployment_id': 'mock',
        'state': 'failed',
        'error': 'Mock'
    })


@patch('deployer.services.deployment.get_store')
@patch('deployer.services.deployment.get_discovered_nodes')
@raises(Exception)
def test_sync_upstreams_without_ignoring_errors(
        m_get_discovered_nodes, m_get_store):

    # Given: Existing deployment
    m_get_store.return_value.get_deployment.return_value = {
        'deployment': {
            'name': 'test',
            'version': 'v1',
            'mode': DEPLOYMENT_MODE_BLUEGREEN
        },
        'proxy': {
            'hosts': {
                'mock-host': {
                    'locations': {
                        'home': {
                            'port': 8090
                        }
                    }
                }
            }
        }
    }

    # And: Discovered Nodes
    m_get_discovered_nodes.side_effect = Exception('Mock')

    # When: I synchronize upstreams for existing deployment
    sync_upstreams('mock', ignore_error=False)


@patch('deployer.services.deployment.get_store')
@patch('deployer.services.deployment.filter_units')
def test_sync_units(m_filter_units, m_get_store):

    # Given: Existing deployment
    m_get_store.return_value.get_deployment.return_value = {
        'deployment': {
            'name': 'test',
            'version': 'v1',
            'mode': DEPLOYMENT_MODE_BLUEGREEN
        }
    }

    # And: Discovered Nodes
    m_filter_units.return_value = [{
        'name': 'app-unit'
    }]

    # When: I synchronize units for existing deployment
    ret_value = sync_units('mock')

    # Then: Upstreams are synchronized as expected:
    dict_compare(ret_value, {
        'deployment_id': 'mock',
        'state': 'success',
        'units': m_filter_units.return_value
    })


@patch('deployer.services.deployment.get_store')
@patch('deployer.services.deployment.filter_units')
def test_sync_units_with_error(m_filter_units, m_get_store):

    # Given: Existing deployment
    m_get_store.return_value.get_deployment.return_value = {
        'deployment': {
            'name': 'test',
            'version': 'v1',
            'mode': DEPLOYMENT_MODE_BLUEGREEN
        }
    }

    # And: Discovered Nodes
    m_filter_units.side_effect = Exception('MockException')

    # When: I synchronize units for existing deployment
    ret_value = sync_units('mock')

    # Then: Upstreams are synchronized as expected:
    dict_compare(ret_value, {
        'deployment_id': 'mock',
        'state': 'failed',
        'error': 'MockException'
    })


@patch('deployer.services.deployment.get_store')
@patch('deployer.services.deployment.filter_units')
@raises(Exception)
def test_sync_units_without_ignoring_error(m_filter_units, m_get_store):

    # Given: Existing deployment
    m_get_store.return_value.get_deployment.return_value = {
        'deployment': {
            'name': 'test',
            'version': 'v1',
            'mode': DEPLOYMENT_MODE_BLUEGREEN
        }
    }

    # And: Discovered Nodes
    m_filter_units.side_effect = Exception('MockException')

    # When: I synchronize units for existing deployment
    sync_units('mock', ignore_error=False)

    # Then: Exception is raised


@patch('uuid.uuid4')
def test_clone_deployment(m_uuid):
    """
    Should clone exiting deployment and reset version
    """

    # Given: New job id
    m_uuid.return_value = 'new-job-id'

    # When: I clone existing deployment
    cloned = clone_deployment({
        'deployment': {
            'name': 'mock',
            'version': 'v1'
        },
        'meta-info': {
            'job-id': 'old-job-id'
        }
    })

    # Then: Expected cloned deployment is created
    dict_compare(cloned, {
        'deployment': {
            'name': 'mock'
        },
        'meta-info': {
            'job-id': 'new-job-id'
        }
    })
