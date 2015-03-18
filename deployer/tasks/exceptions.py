
class MinNodesNotRunning(Exception):
    """
    Exception corresponding to nodes not in running state.
    """
    def __init__(self, name, version, min_units, units):
        """
        Constructor.

        :param name: Name of the application
        :type name: str
        :param version: Application version
        :type version: str
        :param min_units: Minimum units required for application (in running
            state)
        :type min_units: int
        :param units: Actual deployed units.
        :type units: dict
        """
        self.name = name
        self.version = version
        self.min_units = min_units
        self.units = units
        self.message = 'Minimum of %d units for application:%s version:%s ' \
                       'were not found in running state.' % \
                       (self.min_units, self.name, self.version)
        super(MinNodesNotRunning, self).__init__(
            name, version, min_units, units)

    def to_dict(self):
        return {
            'message': 'Minimum of %d units for application:%s version:%s '
                       'were not found in running state.' %
                       (self.min_units, self.name, self.version),
            'code': 'MIN_NODES_NOT_RUNNING',
            'details': {
                'name': self.name,
                'version': self.version,
                'min-units': self.min_units,
                'units': self.units
                }
        }


class MinNodesNotDiscovered(Exception):
    """
    Exception corresponding to minimum nodes not being discovered.
    """
    def __init__(self, name, version, min_nodes, discovered_nodes):
        """
        Constructor.

        :param name: Name of the application
        :type name: str
        :param version: Application version
        :type version: str
        :param min_nodes: Minimum nodes required for application
        :type min_nodes: int
        :param discovered_nodes: Discovered nodes so far.
        :type discovered_nodes: dict
        """
        self.name = name
        self.version = version
        self.min_nodes = min_nodes
        self.discovered_nodes = discovered_nodes
        self.message = 'Minimum of %d nodes for application:%s version:%s ' \
                       'were not registered to yoda proxy.' % \
                       (self.min_nodes, self.name, self.version)
        super(MinNodesNotDiscovered, self).__init__(
            name, version, min_nodes, discovered_nodes)

    def to_dict(self):
        return {
            'message': self.message,
            'code': 'MIN_NODES_NOT_DISCOVERED',
            'details': {
                'name': self.name,
                'version': self.version,
                'min-nodes': self.min_nodes,
                'discovered-nodes': self.discovered_nodes
            }
        }

    def __str__(self):
        return self.message


class NodeNotUndeployed(Exception):
    """
    Exception corresponding to node still in deployed state.
    """

    def __init__(self, name, version, deployed_units):
        self.name = name
        self.version = version
        self.deployed_units = deployed_units
        self.message = 'Nodes for application:%s version:%s did not get ' \
                       'un-deployed' % (self.name, self.version)
        super(NodeNotUndeployed, self).__init__(
            name, version, deployed_units)

    def to_dict(self):
        return {
            'message': self.message,
            'code': 'NODE_NOT_UNDEPLOYED',
            'details': {
                'name': self.name,
                'version': self.version
            }
        }

    def __str__(self):
        return self.message


class TaskExecutionException(Exception):
    """
    Exception wrapping the final exception returned.
    """

    def __init__(self, cause, traceback=None):
        try:
            dict_repr = cause.to_dict()
        except AttributeError:
            dict_repr = {}

        self.message = dict_repr.get('message', str(cause))
        self.code = dict_repr.get('code', 'INTERNAL')
        self.traceback = traceback
        self.details = dict_repr.get('details', None)
        super(TaskExecutionException, self).__init__(cause, traceback)

    def to_dict(self):
        return {
            'message': self.message,
            'code': self.code,
            'details': self.details,
            'traceback': self.traceback
        }

    def __str__(self):
        return self.message


class NodeCheckFailed(Exception):
    """
    Exception corresponding to failed deployment check for a given node.
    """

    def __init__(self, url, reason, status=None, response=None):
        self.url = url
        self.message = 'Deployment check failed for url: {0} due to: {1}'\
            .format(url, reason)
        self.status = status
        self.response = response
        super(NodeCheckFailed, self).__init__(url, reason, status, response)

    def to_dict(self):
        return {
            'message': self.message,
            'code': 'NODE_CHECK_FAILED',
            'details': {
                'url': self.url,
                'status': self.status,
                'response': self.response
            }
        }

    def __str__(self):
        return self.message

    def __eq__(self, other):
        return self.status == other.status and \
            self.message == other.message and \
            self.response == other.response and \
            self.url == other.url
