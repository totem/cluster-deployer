from deployer.tasks.exceptions import MinNodesNotRunning
from tests.helper import dict_compare


def test_dict_repr_for_min_nodes_not_running_exception():
    """Should get defaults for deployment of type git-quay"""

    # When: I call to_dict for MinNodesNotRunning exception
    result = MinNodesNotRunning('mockapp', 'mockversion', min_units=1, units=[
        {'unit': 'mockunit'}]).to_dict()

    # Then: Expected result is returned
    dict_compare(result, {
        'message': 'Minimum of 1 nodes for application:mockapp version: '
                   'mockversion were not found in running state.',
        'code': 'MIN_NODES_NOT_RUNNING',
        'details': {
            'name': 'mockapp',
            'version': 'mockversion',
            'min_units': 1,
            'units': [{'unit': 'mockunit'}]
        }
    })
