"""
Test for `deployer.services.distributed_lock`
"""

from mock import Mock, patch
from nose.tools import raises, eq_
from deployer.services.distributed_lock import LockService, \
    ResourceLockedException
from tests.helper import dict_compare

__author__ = 'sukrit'

MOCK_APP = 'spec-python-develop'
MOCK_LOCK = 'mock-lock'
MOCK_KEY = '/totem/cluster-deployer/locks/apps/spec-python-develop'


class TestLockService():
    """
    Test for LockService
    """

    def setup(self):
        self.etcd_cl = Mock(spec='etcd.Client')()
        self.service = LockService(etcd_cl=self.etcd_cl)

    @patch('uuid.uuid4')
    def test_apply_lock(self, mock_uuid4):
        """
        Should apply lock when no lock exists
        """

        # Given: Non existing lock
        self.etcd_cl.write.return_value = None

        # And: Mock lock value
        mock_uuid4.return_value = MOCK_LOCK

        # When: I try to apply lock
        lock = self.service.apply_lock(MOCK_APP)

        # Then: Lock is applied successfully
        dict_compare(lock, {
            'key': MOCK_KEY,
            'name': MOCK_APP,
            'value': MOCK_LOCK
        })
        self.etcd_cl.write.assert_called_once_with(
            MOCK_KEY, MOCK_LOCK, prevExists=False, ttl=self.service.lock_ttl)

    @raises(ResourceLockedException)
    @patch('uuid.uuid4')
    def test_apply_lock_when_lock_exists(self, mock_uuid4):
        """
        Should apply lock when no lock exists
        """

        # Given: Existing lock
        self.etcd_cl.write.side_effect = KeyError

        # And: Mock lock value
        mock_uuid4.return_value = MOCK_LOCK

        # When: I try to apply lock
        self.service.apply_lock(MOCK_APP)

        # Then: ResourceLockedException is raised

    def test_release_lock(self):
        """
        Should release existing lock
        """

        # Given: Existing lock
        lock = {
            'key': MOCK_KEY,
            'name': MOCK_APP,
            'value': MOCK_LOCK
        }
        self.etcd_cl.delete.return_value = None

        # When: I try to release lock
        release_successful = self.service.release(lock)

        # Then: Lock is released successfully
        eq_(release_successful, True)
        self.etcd_cl.delete.assert_called_once_with(MOCK_KEY,
                                                    prevValue=MOCK_LOCK)

    def test_release_non_existing_lock(self):
        """
        Should release existing lock
        """

        # Given: Non Existing lock
        lock = {
            'key': MOCK_KEY,
            'name': MOCK_APP,
            'value': MOCK_LOCK
        }
        self.etcd_cl.delete.side_effect = KeyError

        # When: I try to release lock
        release_successful = self.service.release(lock)

        # Then: Lock is released successfully
        eq_(release_successful, False)
