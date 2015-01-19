import datetime
from freezegun import freeze_time
from mock import patch, ANY
from nose.tools import raises, eq_

from conf.appconfig import DEPLOYMENT_MODE_BLUEGREEN, DEPLOYMENT_MODE_REDGREEN, \
    DEPLOYMENT_STATE_STARTED
from deployer.celery import app

from deployer.tasks.exceptions import NodeNotUndeployed
from tests.helper import dict_compare


__author__ = 'sukrit'

from deployer.tasks.deployment import _deployment_defaults, \
    _pre_create_undeploy, _wait_for_undeploy

NOW = datetime.datetime(2014, 01, 01)


def test_create():
    """Should create a new deployment."""
    # response = create.delay('Hello').get(propogate=True)
    # eq_(response, 'Hello')
    pass


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
            'type': 'git-quay'
        }
    }


def _create_test_deployment_with_defaults_applied():
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
            'name': 'testowner-testrepo-testref',
            'version': 1000,
            'type': 'git-quay',
            'mode': DEPLOYMENT_MODE_BLUEGREEN
        }
    }


@freeze_time(NOW)
@patch('time.time')
def test_deployment_defaults_for_type_git_quay(mock_time):
    """Should get defaults for deployment of type git-quay"""

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
            'git': {
                'owner': 'testowner',
                'repo': 'testrepo',
                'ref': 'testref',
                'commit': 'testcommit'

            }
        },
        'deployment': {
            'name': 'testowner-testrepo-testref',
            'type': 'git-quay',
            'version': '101',
            'nodes': 2,
            'mode': DEPLOYMENT_MODE_BLUEGREEN,
            'check': {
                'min-nodes': 1
            }
        },
        'templates': {
            'app': {
                'args': {
                    'environment': {},
                    'docker-args': '',
                    'image': 'quay.io/totem/testowner-testrepo:testcommit'
                },
                'enabled': True,
                'name': 'default-app'
            },
            'yoda-register': {
                'args': {},
                'enabled': True,
                'name': 'yoda-ec2-register'
            },
            'logger': {
                'args': {},
                'enabled': True,
                'name': 'default-logger'
            }
        },
        'id': 'testowner-testrepo-testref-101',
        'proxy': {
            'hosts': {},
            'listeners': {}
        },
        'state': DEPLOYMENT_STATE_STARTED,
        'started-at': NOW
    })


@freeze_time(NOW)
@patch('time.time')
def test_deployment_defaults_for_type_git_quay_with_overrides(mock_time):
    """Should get defaults for deployment of type git-quay"""

    # Given: Deployment dictionary
    deployment = _create_test_deployment()
    deployment['templates'] = {
        'logger': {
            'name': 'default-logger',
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
            'git': {
                'owner': 'testowner',
                'repo': 'testrepo',
                'ref': 'testref',
                'commit': 'testcommit'

            }
        },
        'deployment': {
            'name': 'testowner-testrepo-testref',
            'type': 'git-quay',
            'version': '1000',
            'nodes': 2,
            'mode': DEPLOYMENT_MODE_BLUEGREEN,
            'check': {
                'min-nodes': 1
            }
        },
        'templates': {
            'app': {
                'args': {
                    'environment': {},
                    'docker-args': '',
                    'image': 'quay.io/totem/testowner-testrepo:testcommit'
                },
                'enabled': True,
                'name': 'default-app'
            },
            'yoda-register': {
                'args': {},
                'enabled': True,
                'name': 'yoda-ec2-register'
            },
            'logger': {
                'args': {},
                'enabled': False,
                'name': 'default-logger'
            }
        },
        'id': 'testowner-testrepo-testref-1000',
        'proxy': {
            'hosts': {},
            'listeners': {}
        },
        'state': DEPLOYMENT_STATE_STARTED,
        'started-at': NOW
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
    depl_with_defaults = _deployment_defaults(deployment)

    # Then: Defaults for deployment are applied
    dict_compare(depl_with_defaults, {
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
            'name': 'testdeployment',
            'type': 'custom',
            'version': '1000',
            'nodes': 3,
            'mode': DEPLOYMENT_MODE_BLUEGREEN,
            'check': {
                'min-nodes': 1
            }
        },
        'templates': {
            'app': {
                'args': {
                    'arg1': 'value1'
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
        'id': 'testdeployment-1000',
        'proxy': {
            'hosts': {},
            'listeners': {}
        },
        'state': DEPLOYMENT_STATE_STARTED,
        'started-at': NOW
    })


@app.task
def mock_callback():
    return True


@patch('deployer.tasks.deployment.add_search_event')
@patch('deployer.tasks.deployment.undeploy')
@patch('deployer.tasks.deployment.filter_units')
def test_pre_create_undeploy_for_red_green(mock_filter_units, mock_undeploy,
                                           mock_add_search_event):
    """
    Should un-deploy all versions for mode: red-green
    """

    # Given: Deployment parameters
    deployment = _create_test_deployment_with_defaults_applied()
    deployment['deployment']['mode'] = DEPLOYMENT_MODE_REDGREEN

    # Mock implementation for filter_units
    mock_filter_units.return_value = []

    # When: I un-deploy in pre-create phase
    result = _pre_create_undeploy.s(deployment, mock_callback.si())\
        .apply_async()
    result.get(timeout=1).result

    # Then: All versions of application are un-deployed.
    mock_undeploy.assert_called_with(ANY, deployment['deployment']['name'],
                                     None, exclude_version=None)


@patch('deployer.tasks.deployment.add_search_event')
@patch('deployer.tasks.deployment.undeploy')
@patch('deployer.tasks.deployment.filter_units')
def test_pre_create_undeploy_for_blue_green(mock_filter_units, mock_undeploy,
                                            mock_add_search_event):
    """
    Should undeploy all versions for mode: red-green
    """

    # Given: Deployment parameters
    deployment = _create_test_deployment_with_defaults_applied()
    deployment['deployment']['mode'] = DEPLOYMENT_MODE_BLUEGREEN

    # Mock implementation for filter_units
    mock_filter_units.return_value = []

    # When: I undeploy in pre-create phase
    result = _pre_create_undeploy.s(deployment, mock_callback.si())\
        .apply_async()
    result.get(timeout=1).result

    # Then: All versions of application are un-deployed.
    mock_undeploy.assert_called_with(ANY, deployment['deployment']['name'],
                                     deployment['deployment']['version'],
                                     exclude_version=None)


@patch('deployer.tasks.deployment.add_search_event')
@patch('deployer.tasks.deployment.undeploy')
@patch('deployer.tasks.deployment.filter_units')
def test_pre_create_undeploy_for_ab(mock_filter_units, mock_undeploy,
                                    mock_add_search_event):
    """
    Should undeploy all versions for mode: red-green
    """

    # Given: Deployment parameters
    deployment = _create_test_deployment_with_defaults_applied()
    deployment['deployment']['mode'] = DEPLOYMENT_MODE_BLUEGREEN

    # Mock implementation for filter_units
    mock_filter_units.return_value = []

    # When: I un-deploy in pre-create phase
    result = _pre_create_undeploy.s(deployment, mock_callback.si())\
        .apply_async()
    result.get(timeout=1).result

    # Then: All versions of application are un-deployed.
    mock_undeploy.assert_not_called()


@raises(NodeNotUndeployed)
@patch('deployer.tasks.deployment.filter_units')
def test_wait_for_undeploy_for_failure(mock_filter_units):
    """
    Should raise NodeNotUndeployed exception if units do not get undeployed
    """

    # Given: Active units
    mock_filter_units.return_value = [
        {
            'unit': 'mock-v1'
        }
    ]

    # When I wait for un-deploy to finish
    _wait_for_undeploy.s('mock', None).apply_async()

    # NodeNotUndeployed is raised


@patch('deployer.tasks.deployment.filter_units')
def test_wait_for_undeploy_for_success(mock_filter_units):
    """
    Should wait for undeploy to finish.
    """

    # Given: Active units
    mock_filter_units.return_value = []

    # When I wait for un-deploy to finish
    result = _wait_for_undeploy.s('mock', None, True).apply_async()
    ret_value = result.get(timeout=1)

    eq_(ret_value, True)
