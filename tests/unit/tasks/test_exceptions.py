from nose.tools import eq_
from deployer.tasks.exceptions import MinNodesNotRunning, MinNodesNotDiscovered, \
    NodeCheckFailed
from tests.helper import dict_compare


def test_dict_repr_for_min_nodes_not_running_exception():

    # When: I call to_dict for MinNodesNotRunning exception
    result = MinNodesNotRunning('mockapp', 'mockversion', min_units=1, units=[
        {'unit': 'mockunit'}]).to_dict()

    # Then: Expected result is returned
    dict_compare(result, {
        'message': 'Minimum of 1 units for application:mockapp version:'
                   'mockversion were not found in running state.',
        'code': 'MIN_NODES_NOT_RUNNING',
        'details': {
            'name': 'mockapp',
            'version': 'mockversion',
            'min-units': 1,
            'units': [{'unit': 'mockunit'}]
        }
    })


def test_dict_repr_for_min_nodes_not_discovered_exception():

    # When: I call to_dict for MinNodesNotRunning exception
    result = MinNodesNotDiscovered(
        'mockapp', 'mockversion', 1, {'node1': 'host1:8080'}).to_dict()

    # Then: Expected result is returned
    dict_compare(result, {
        'message': 'Minimum of 1 nodes for application:mockapp '
                   'version:mockversion were not registered to yoda proxy.',
        'code': 'MIN_NODES_NOT_DISCOVERED',
        'details': {
            'name': 'mockapp',
            'version': 'mockversion',
            'min-nodes': 1,
            'discovered-nodes': {'node1': 'host1:8080'}
        }
    })


def test_dict_repr_for_node_check_failed():

    # When: I call to_dict for NodeCheckFailed exception
    result = NodeCheckFailed('http://localhost:8080', 'MockReason',
                             status=500, response={'raw': 'Mock'}).to_dict()

    # Then: Expected result is returned
    dict_compare(result, {
        'message': 'Deployment check failed for url: http://localhost:8080 '
                   'due to: MockReason',
        'code': 'NODE_CHECK_FAILED',
        'details': {
            'url': 'http://localhost:8080',
            'status': 500,
            'response': {'raw': 'Mock'}
        }
    })


def test_str_repr_for_node_check_failed():

    # When: I call str representation for NodeCheckFailed exception
    result = str(NodeCheckFailed('http://localhost:8080', 'MockReason'))

    # Then: Expected result is returned
    eq_(result, 'Deployment check failed for url: http://localhost:8080 due '
                'to: MockReason')