import datetime
import httplib
import urllib2

from mock import patch, ANY, MagicMock
import nose
from nose.tools import raises, eq_, assert_raises
from paramiko import SSHException

from conf.appconfig import DEPLOYMENT_MODE_BLUEGREEN, DEPLOYMENT_MODE_REDGREEN
from deployer.celery import app
from deployer.tasks.exceptions import NodeNotUndeployed, MinNodesNotRunning, \
    NodeCheckFailed, MinNodesNotDiscovered
from tests.helper import dict_compare

from deployer.tasks.deployment import _pre_create_undeploy, \
    _wait_for_undeploy, _fleet_check_deploy, _check_node, _check_deployment, \
    _check_discover

__author__ = 'sukrit'


NOW = datetime.datetime(2014, 01, 01)
DEFAULT_STOP_TIMEOUT_SECONDS = 30


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
                'commit': 'testcommit',
                'type': 'github'

            }
        },
        'deployment': {
            'name': 'testowner-testrepo-testref',
            'version': 1000,
            'type': 'git-quay',
            'mode': DEPLOYMENT_MODE_BLUEGREEN,
        }
    }


@app.task
def mock_callback():  # pragma: no cover
    return True


@patch('deployer.tasks.deployment.undeploy')
@patch('deployer.tasks.deployment.fetch_runtime_units')
@patch('deployer.tasks.deployment.stop')
def test_pre_create_undeploy_for_red_green(m_stop, mock_filter_units,
                                           mock_undeploy):
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
    m_stop.assert_called_with(ANY, deployment['deployment']['name'],
                              version=None, exclude_version=None)


@patch('deployer.tasks.deployment.undeploy')
@patch('deployer.tasks.deployment.fetch_runtime_units')
@patch('deployer.tasks.deployment.stop')
def test_pre_create_undeploy_for_blue_green(m_stop, mock_filter_units,
                                            mock_undeploy):
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
    m_stop.assert_called_with(
        ANY, deployment['deployment']['name'],
        version=deployment['deployment']['version'], exclude_version=None)


@patch('deployer.tasks.deployment.undeploy')
@patch('deployer.tasks.deployment.fetch_runtime_units')
@patch('deployer.tasks.deployment.stop')
def test_pre_create_undeploy_for_ab(m_stop, mock_filter_units, mock_undeploy):
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
    m_stop.assert_not_called()


@raises(NodeNotUndeployed)
@patch('deployer.tasks.deployment.fetch_runtime_units')
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


@patch('deployer.tasks.deployment.fetch_runtime_units')
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


@patch('deployer.tasks.deployment.fetch_runtime_units')
def test_fleet_check_deploy_when_units_already_running(mock_filter_units):
    # given: Running units
    mock_filter_units.return_value = [
        {'name': 'unit1-app', 'sub': 'running'},
        {'name': 'unit1-logger', 'sub': 'running'}
    ]

    # When I check for fleet deploy
    result = _fleet_check_deploy.s('mockapp', 'mockversion', 2, 1)\
        .apply_async()
    ret_value = result.get(timeout=1)

    # Then: Check returns successfully
    dict_compare(ret_value, mock_filter_units.return_value)


@patch('deployer.tasks.deployment.fetch_runtime_units')
def test_fleet_check_deploy_when_units_are_not_running(mock_filter_units):
    # given: Running units
    mock_filter_units.return_value = [
        {'name': 'unit1-app', 'sub': 'dead'}
    ]

    # When I check for fleet deploy
    with assert_raises(MinNodesNotRunning) as cm:
        _fleet_check_deploy('mockapp', 'mockversion', 1, 1)

    # Then: Check Retry exception is thrown
    error = cm.exception
    eq_(error.name, 'mockapp')
    eq_(error.version, 'mockversion')
    eq_(error.min_units, 1)
    eq_(error.units, mock_filter_units.return_value)


@raises(SSHException)
@patch('deployer.tasks.deployment.fetch_runtime_units')
def test_fleet_check_deploy_when_ssh_error_is_thrown(mock_filter_units):
    # given: Running units
    mock_filter_units.side_effect = SSHException()

    # When I check for fleet deploy
    _fleet_check_deploy('mockapp', 'mockversion', 1, 1)

    # Then: Check SSHException exception is thrown


@patch('urllib2.urlopen')
def test_check_node(m_urlopen):
    """
    Should perform deployment check for a given node successfully.
    """

    # When: I call check node with a given path
    _check_node('localhost:8080', '/mock', 5, '5s')

    # Then: Http URL Check is performed for given path
    m_urlopen.assert_called_once_with('http://localhost:8080/mock', None, 5)


@patch('urllib2.urlopen')
def test_check_node_for_path_not_beginning_with_forward_slash(m_urlopen):
    """
    Should perform deployment check for a given node successfully.
    """

    # When: I call check node with a given path
    _check_node('localhost:8080', 'mock', 5, '5s')

    # Then: Http URL Check is performed for given path
    m_urlopen.assert_called_once_with('http://localhost:8080/mock', None, 5)


@patch('urllib2.urlopen')
def test_check_node_for_unhealthy_node(m_urlopen):
    """
    Should fail node check for unhealthy node.
    """

    # Given: Unhealthy node
    fp = MagicMock()
    fp.read.return_value = 'MockResponse'
    m_urlopen.side_effect = urllib2.HTTPError(
        'http://mockurl', 500, 'MockError', None, fp)

    # And: Mock Implementation for retry
    _check_node.retry = MagicMock()

    def retry(*args, **kwargs):
        raise kwargs.get('exc')

    _check_node.retry.side_effect = retry

    # When: I call check node with a given path
    with nose.tools.assert_raises(NodeCheckFailed) as cm:
        _check_node('localhost:8080', 'mock', 5, '5s')

    # Then: NodeCheckFailed exception is raised
    eq_(cm.exception, NodeCheckFailed(
        'http://localhost:8080/mock', 'MockError', status=500,
        response={'raw': 'MockResponse'}, attempts=5))


@patch('urllib2.urlopen')
def test_check_node_for_unhealthy_node_returning_bad_status_line(m_urlopen):
    """
    Should fail node check for unhealthy node.
    """

    # Given: Unhealthy node
    m_urlopen.side_effect = httplib.BadStatusLine('')

    # And: Mock Implementation for retry
    _check_node.retry = MagicMock()

    def retry(*args, **kwargs):
        raise kwargs.get('exc')

    _check_node.retry.side_effect = retry

    # When: I call check node with a given path
    with nose.tools.assert_raises(NodeCheckFailed) as cm:
        _check_node('localhost:8080', 'mock', 5, '5s')

    # Then: NodeCheckFailed exception is raised
    eq_(cm.exception, NodeCheckFailed(
        'http://localhost:8080/mock', 'BadStatusLine("\'\'",)', status=None,
        response=None, attempts=5))


@patch('deployer.tasks.deployment._check_node')
@patch('deployer.tasks.deployment.chord')
def test_check_deployment(m_chord, m_check_node):
    """
    Should perform node check for all discovered nodes
    """

    # Given: DIscovered Nodes
    nodes = {
        'node1': 'localhost:8080',
        'node2': 'localhost:8081'
    }

    # And: Path for deployment check
    path = '/mockpath'

    # When: I perform deployment check for discovered nodes
    result = _check_deployment(nodes, path, 3, '5s')

    # Then: Node check is performed for all discovered nodes
    eq_(result, m_chord.return_value.delay.return_value)
    eq_(list(m_chord.call_args[0][0]),
        [m_check_node.si.return_value] * 2)
    m_check_node.si.assert_any_call('localhost:8080', '/mockpath', 3, '5s')
    m_check_node.si.assert_any_call('localhost:8081', '/mockpath', 3, '5s')


@patch('deployer.tasks.deployment._check_node')
@patch('deployer.tasks.deployment.group')
def test_check_deployment_with_no_path_specified(m_group, m_check_node):
    """
    Should not perform node check when path is not given
    """

    # Given: Discovered Nodes
    nodes = {
        'node1': 'localhost:8080',
        'node2': 'localhost:8081'
    }

    # When: I perform deployment check for discovered nodes
    result = _check_deployment(nodes, None, 3, '5s')

    # Then: Node check is skipped for all discovered nodes
    eq_(result, None)
    eq_(m_group.call_count, 0)


@patch('deployer.tasks.deployment._check_node')
@patch('deployer.tasks.deployment.group')
def test_check_deployment_with_no_discovered_nodes(m_group, m_check_node):
    """
    Should not perform node check when path is not given
    """

    # Given: No nodes were discovered
    nodes = {}

    # When: I perform deployment check
    result = _check_deployment(nodes, '/mockpath', 3, '5s')

    # Then: Node check is skipped
    eq_(result, None)
    eq_(m_group.call_count, 0)


@patch('yoda.client.Client')
def test_check_discover_for_min_node_criteria_not_met(mock_yoda_cl):
    # Given: Existing nodes
    mock_yoda_cl().get_nodes.return_value = {
        'node1': 'mockhost1:48080',
        }

    # When: I check discover for app with no check-port defined
    with assert_raises(MinNodesNotDiscovered) as cm:
        _check_discover('mockapp', 'mockversion', 8080, 2,
                        DEPLOYMENT_MODE_BLUEGREEN)

    # Then: Discover check fails
    error = cm.exception
    eq_(error.name, 'mockapp')
    eq_(error.version, 'mockversion')
    eq_(error.min_nodes, 2)
    dict_compare(error.discovered_nodes, {'node1': 'mockhost1:48080'})
