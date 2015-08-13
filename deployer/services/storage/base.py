import copy
import datetime
import pytz
from deployer.util import dict_merge

__author__ = 'sukrit'

"""
Module containing methods for storing deployment/other information in persist
storage like mongo
"""

EVENT_NEW_DEPLOYMENT = 'NEW_DEPLOYMENT'
EVENT_ACQUIRED_LOCK = 'ACQUIRED_LOCK'
EVENT_DEPLOYMENTS_STOPPED = 'DEPLOYMENTS_STOPPED'
EVENT_DEPLOYMENTS_UNDEPLOYED = 'DEPLOYMENTS_UNDEPLOYED'
EVENT_UNITS_ADDED = 'UNITS_ADDED'
EVENT_UNITS_STARTED = 'UNITS_STARTED'
EVENT_UNITS_DEPLOYED = 'UNITS_DEPLOYED'
EVENT_NODES_DISCOVERED = 'NODES_DISCOVERED'
EVENT_DEPLOYMENT_CHECK_PASSED = 'DEPLOYMENT_CHECK_PASSED'
EVENT_WIRED = 'WIRED'
EVENT_UPSTREAMS_REGISTERED = 'UPSTREAMS_REGISTERED'
EVENT_PROMOTED = 'PROMOTED'
EVENT_DEPLOYMENT_FAILED = 'DEPLOYMENT_FAILED'


class AbstractStore:

    @staticmethod
    def apply_modified_ts(deployment):
        return dict_merge(
            {
                'modified': datetime.datetime.now(tz=pytz.UTC)
            }, deployment)

    def not_supported(self):
        """
        Raises NotImplementedError with a message
        :return:
        """
        raise NotImplementedError(
            'Store: {} does not support this operation'.format(self.__class__))

    def create_deployment(self, deployment):
        """
        Creates/ updates deployment information
        :param deployment: Dictionary containing deployment information
        :type deployment: dict
        :return: None
        """
        self.not_supported()

    def get_deployment(self, deployment_id):
        """
        Gets deployment by given id
        :param deployment_id: Deployment id
        :type deployment_id: str
        :return: Deployment dictionary
        :rtype: dict
        """
        self.not_supported()

    def update_state(self, deployment_id, state):
        """
        Update the state of given deployment
        :param deployment_id: Deployment id
        :type deployment_id: str
        :param state: State of the deployment (e.g. PROMOTED, NEW, etc)
        :type state: str
        :return: None
        """
        self.not_supported()

    def add_event(self, event_type, details=None, search_params=None):
        """
        Adds event to event store
        :param event_type: Type of event
        :type event_type: str
        :keyword details: Details associated with event
        :type details: dict
        :keyword search_params: Additional meta-info associated with event
        :type search_params: dict
        :return: None
        """
        event_upd = copy.deepcopy(search_params or {})
        event_upd.update({
            'type': event_type,
            'details': details,
            'date': datetime.datetime.utcnow(),
            'component': 'deployer'
        })
        self._add_raw_event(event_upd)

    def update_state_bulk(self, name, new_state, existing_state=None,
                          version=None):
        """
        Bulk update the state for deployments matching name , optional version
        and optional state to new state
        :param name: Name of the deployment
        :type name: str
        :param new_state: New state for the deployment
        :type new_state: str
        :keyword existing_state: Existing state of deployment. If None,
            deployments matching all state are updated
        :type existing_state: str
        :keyword version: Optional version of the deployment. If None,
            deployments matching all versions are updated
        :type version: str
        :return: None
        """
        self.not_supported()

    def update_runtime_upstreams(self, deployment_id, upstreams):
        """
        Updates the runtime upstreams information in the store

        :param deployment_id: Id of the deployment
        :type deployment_id: str
        :param upstreams: Dictionary representing runtime upstreams info
        :type upstreams: dict
        :return: None
        """
        self.not_supported()

    def update_runtime_units(self, deployment_id, units):
        """
        Updates the runtime units information in the store for given deployment

        :param deployment_id: Id of the deployment
        :type deployment_id: str
        :param units: Dictionary representing units for given deployment
        :type units: array
        :return: None
        """
        self.not_supported()

    def find_apps(self):
        """
        Looks up all applications names
        :return: List of application names (str)
        :rtype: list
        """
        self.not_supported()

    def filter_deployments(self, name=None, version=None, only_running=True,
                           only_ids=False, state=None):
        """
        Filter deployments
        :keyword name: Optional Application name
        :type name: str
        :keyword version: Application version
        :type version: str
        :keyword only_running: If True, gets the list of running deployments
            else gets all deployments
        :type only_running: bool
        :keyword only_ids:  If True , only ids are included and rest of the
            fields are excluded. (The structure of document however does not
            change)
        :type only_ids: bool
        :keyword state: Filter based on deployment state
        :type state: str
        :return: List of deployments
        :rtype list
        """
        self.not_supported()

    def _add_raw_event(self, event):
        """
        Adds raw event to store.
        :param event: Event Details
        :type event: dict
        :return: None
        """
        self.not_supported()

    def setup(self):
        """
        Setup the store prior to use.
        :return: None
        """
        # No Setup needed by default
        pass

    def health(self):
        self.not_supported()
