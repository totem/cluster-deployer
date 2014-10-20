from mock import patch, ANY
from conf.appconfig import DEPLOYMENT_MODE_BLUEGREEN, DEPLOYMENT_MODE_REDGREEN

from tests.helper import dict_compare


__author__ = 'sukrit'

from deployer.tasks.deployment import _deployment_defaults, \
    _pre_create_undeploy


def test_create():
    """Should create a new deployment."""
    # response = create.delay('Hello').get(propogate=True)
    # eq_(response, 'Hello')
    pass


def _create_test_deployment():
    return {
        'meta-info': {
            'job-id': 'test-job',
            'github': {
                'owner': 'testowner',
                'repo': 'testrepo',
                'branch': 'testbranch',
                'commit': 'testcommit'

            }
        },
        'deployment': {
            'type': 'github-quay'
        }
    }


def _create_test_deployment_with_defaults_applied():
    return {
        'meta-info': {
            'job-id': 'test-job',
            'github': {
                'owner': 'testowner',
                'repo': 'testrepo',
                'branch': 'testbranch',
                'commit': 'testcommit'

            }
        },
        'deployment': {
            'name': 'testowner-testrepo-testbranch',
            'version': 1000,
            'type': 'github-quay',
            'mode': DEPLOYMENT_MODE_BLUEGREEN
        }
    }


@patch('time.time')
def test_deployment_defaults_for_type_github_quay(mock_time):
    """Should get defaults for deployment of type github-quay"""

    # Given: Deployment dictionary
    deployment = _create_test_deployment()

    # Mock Time call for creating version
    mock_time.return_value = 0.1006

    # When: I apply defaults for deployment
    depl_with_defaults = _deployment_defaults(deployment)

    # Then: Defaults for deployment are applied
    dict_compare(depl_with_defaults, {
        'meta-info': {
            'job-id': 'test-job',
            'github': {
                'owner': 'testowner',
                'repo': 'testrepo',
                'branch': 'testbranch',
                'commit': 'testcommit'

            }
        },
        'deployment': {
            'name': 'testowner-testrepo-testbranch',
            'type': 'github-quay',
            'version': 101,
            'nodes': 2,
            'mode': DEPLOYMENT_MODE_BLUEGREEN
        },
        'templates': {
            'default-app': {
                'priority': 1,
                'args': {
                    'environment': {},
                    'docker-args': '',
                    'image': 'quay.io/totem/totem-testrepo:testcommit'
                },
                'enabled': True,
                'service-type': 'app'
            },
            'yoda-ec2-register': {
                'args': {},
                'priority': 2,
                'enabled': True,
                'service-type': 'yoda-register'
            },
            'default-logger': {
                'args': {},
                'priority': 2,
                'enabled': True,
                'service-type': 'logger'
            }
        }
    })


@patch('time.time')
def test_deployment_defaults_for_type_github_quay_with_overrides(mock_time):
    """Should get defaults for deployment of type github-quay"""

    # Given: Deployment dictionary
    deployment = _create_test_deployment()
    deployment['templates'] = {
        'default-logger': {
            'priority': 3,
            'enabled': False,
        }
    }

    # Mock Time call for creating version
    mock_time.return_value = 1

    # When: I apply defaults for deployment
    depl_with_defaults = _deployment_defaults(deployment)

    # Then: Defaults for deployment are applied
    dict_compare(depl_with_defaults, {
        'meta-info': {
            'job-id': 'test-job',
            'github': {
                'owner': 'testowner',
                'repo': 'testrepo',
                'branch': 'testbranch',
                'commit': 'testcommit'

            }
        },
        'deployment': {
            'name': 'testowner-testrepo-testbranch',
            'type': 'github-quay',
            'version': 1000,
            'nodes': 2,
            'mode': DEPLOYMENT_MODE_BLUEGREEN
        },
        'templates': {
            'default-app': {
                'priority': 1,
                'args': {
                    'environment': {},
                    'docker-args': '',
                    'image': 'quay.io/totem/totem-testrepo:testcommit'
                },
                'enabled': True,
                'service-type': 'app'
            },
            'yoda-ec2-register': {
                'args': {},
                'priority': 2,
                'enabled': True,
                'service-type': 'yoda-register'
            },
            'default-logger': {
                'args': {},
                'priority': 3,
                'enabled': False,
                'service-type': 'logger'
            }
        }
    })


@patch('time.time')
def test_deployment_defaults_for_custom_deployment(mock_time):
    """Should get defaults for deployment of type github-quay"""

    # Given: Deployment dictionary
    deployment = _create_test_deployment()
    deployment['deployment'] = {
        'name': 'testdeployment',
        'type': 'custom',
        'nodes': 3
    }

    deployment['templates'] = {
        'custom-app': {
            'args': {
                'arg1': 'value1'
            },
            'service-type': 'app'
        },
        'custom-logger': {
            'args': {
                'arg1': 'value1'
            },
            'service-type': 'logger',
            'priority': 2,
            'enabled': False
        }
    }

    # Mock Time call for creating version
    mock_time.return_value = 1

    # When: I apply defaults for deployment
    depl_with_defaults = _deployment_defaults(deployment)

    # Then: Defaults for deployment are applied
    dict_compare(depl_with_defaults, {
        'meta-info': {
            'job-id': 'test-job',
            'github': {
                'owner': 'testowner',
                'repo': 'testrepo',
                'branch': 'testbranch',
                'commit': 'testcommit'

            }
        },
        'deployment': {
            'name': 'testdeployment',
            'type': 'custom',
            'version': 1000,
            'nodes': 3,
            'mode': DEPLOYMENT_MODE_BLUEGREEN
        },
        'templates': {
            'custom-app': {
                'args': {
                    'arg1': 'value1'
                },
                'priority': 1,
                'enabled': True,
                'service-type': 'app'
            },
            'custom-logger': {
                'args': {
                    'arg1': 'value1'
                },
                'priority': 2,
                'enabled': False,
                'service-type': 'logger'
            }
        }
    })


@patch('deployer.tasks.deployment.undeploy')
@patch('time.sleep')
def test_pre_create_undeploy_for_red_green(mock_sleep, mock_undeploy):
    """
    Should undeploy all versions for mode: red-green
    """

    # Given: Deployment parameters
    deployment = _create_test_deployment_with_defaults_applied()
    deployment['deployment']['mode'] = DEPLOYMENT_MODE_REDGREEN

    # When: I undeploy in pre-create phase
    result = _pre_create_undeploy.s(deployment).apply()
    ret_deployment = result.get(timeout=1)

    # Then: All versions of application are un-deployed.
    mock_undeploy.assert_called_with(ANY, deployment['deployment']['name'],
                                     None)
    ret_deployment == deployment


@patch('deployer.tasks.deployment.undeploy')
@patch('time.sleep')
def test_pre_create_undeploy_for_blue_green(mock_sleep, mock_undeploy):
    """
    Should undeploy all versions for mode: red-green
    """

    # Given: Deployment parameters
    deployment = _create_test_deployment_with_defaults_applied()
    deployment['deployment']['mode'] = DEPLOYMENT_MODE_BLUEGREEN

    # When: I undeploy in pre-create phase
    result = _pre_create_undeploy.s(deployment).apply()
    ret_deployment = result.get(timeout=1)

    # Then: All versions of application are un-deployed.
    mock_undeploy.assert_called_with(ANY, deployment['deployment']['name'],
                                     deployment['deployment']['version'])
    ret_deployment == deployment


@patch('deployer.tasks.deployment.undeploy')
@patch('time.sleep')
def test_pre_create_undeploy_for_ab(mock_sleep, mock_undeploy):
    """
    Should undeploy all versions for mode: red-green
    """

    # Given: Deployment parameters
    deployment = _create_test_deployment_with_defaults_applied()
    deployment['deployment']['mode'] = DEPLOYMENT_MODE_BLUEGREEN

    # When: I undeploy in pre-create phase
    result = _pre_create_undeploy.s(deployment).apply()
    ret_deployment = result.get(timeout=1)

    # Then: All versions of application are un-deployed.
    mock_undeploy.assert_not_called()
    ret_deployment == deployment
