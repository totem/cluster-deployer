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
        :param state: State of the deployment (e.g. PROMOTED, NEW, etc)
        :return:
        """
        self.not_supported()

    def setup(self):
        # No Setup needed by default
        pass

    def health(self):
        self.not_supported()
