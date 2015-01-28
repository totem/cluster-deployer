
class MinNodesNotRunning(Exception):
    """
    Exception corresponding to node not in running state.
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
        super(MinNodesNotRunning, self).__init__(
            name, version, min_units, units)

    def to_dict(self):
        return {
            'message': 'Minimum of %d nodes for application:%s version: %s '
                       'were not found in running state.' %
                       (self.min_units, self.name, self.version),
            'code': 'MIN_NODES_NOT_RUNNING',
            'details': {
                'name': self.name,
                'version': self.version,
                'min_units': self.min_units,
                'units': self.units
                }
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
