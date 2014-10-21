

class NodeNotRunningException(Exception):
    """
    Exception corresponding to node not in running state.
    """
    def __init__(self, name, version, node_num, service_type, status,
                 retryable=True, expected_status='running'):
        self.name = name
        self.version = version
        self.node_num = node_num
        self.service_type = service_type
        self.status = status
        self.retryable = retryable
        self.expected_status = expected_status
        super(NodeNotRunningException, self).__init__(
            name, version, node_num, service_type, status, retryable)

    def to_dict(self):
        return {
            'message': 'Status for application:%s version:%s node_num:%d '
                       'service_type:%s is %s instead of %s' %
                       (self.name, self.version, self.node_num,
                        self.service_type, self.unit_status,
                        self.expected_status),
            'code': 'NODE_NOT_RUNNING',
            'details': {
                'name': self.name,
                'version': self.version,
                'node_num': self.node_num,
                'service_type': self.service_type,
                'status': self.status,
                'expected_status': self.expected_status
                },
            'retryable': self.retryable
        }


class NodeNotUndeployed(Exception):
    """
    Exception corresponding to node still in deployed state.
    """

    def __init__(self, name, version, deployed_units):
        self.name = name
        self.version = version
        self.deployed_units = deployed_units
        super(NodeNotUndeployed, self).__init__(
            name, version, deployed_units)

    def to_dict(self):
        return {
            'message': 'Nodes for application:%s version:%s did not get '
                       'un-deployed' % (self.name, self.version),
            'code': 'NODE_NOT_UNDEPLOYED',
            'details': {
                'name': self.name,
                'version': self.version
                }
        }
