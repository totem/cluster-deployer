import copy
import datetime
import pytz
from deployer.util import dict_merge

__author__ = 'sukrit'

"""
Module containing methods for storing deployment/other information in persist
storage like mongo
"""


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

    def _add_raw_event(self, event):
        """
        Adds raw event to store.
        :param event: Event Details
        :type event: dict
        :return: None
        """
        self.not_supported()

    def setup(self):
        # No Setup needed by default
        pass

    def health(self):
        self.not_supported()
