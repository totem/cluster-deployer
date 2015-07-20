import datetime
from freezegun import freeze_time
from mock import MagicMock
from nose.tools import raises
import pytz
from deployer.services.storage.base import AbstractStore
from tests.helper import dict_compare


NOW = datetime.datetime(2022, 01, 01, tzinfo=pytz.UTC)


class TestAbstractStore:

    def setup(self):
        self.store = AbstractStore()

    @raises(NotImplementedError)
    def test_get(self):
        self.store.create_deployment(MagicMock())

    @raises(NotImplementedError)
    def test_get_deployment(self):
        self.store.get_deployment('fake_id')

    @raises(NotImplementedError)
    def test_update_state(self):
        self.store.update_state('fake_id', 'PROMOTED')

    @raises(NotImplementedError)
    def test_get_health(self):
        self.store.health()

    def test_setup(self):
        self.store.setup()
        # NOOP

    @freeze_time(NOW)
    def test_apply_modified_ts(self):

        # When: I apply modified timestamp for given deployemnt
        deployement = self.store.apply_modified_ts({
            'deployement': {
                'id': 'test'
            }
        })

        # Then: Modified timestamp is applied as expected
        dict_compare(deployement, {
            'deployement': {
                'id': 'test'
            },
            'modified': NOW
        })
