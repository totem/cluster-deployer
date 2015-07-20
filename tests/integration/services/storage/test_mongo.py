import copy
import datetime
from freezegun import freeze_time
import pytz
from deployer.services.storage.mongo import create
from nose.tools import ok_
from deployer.util import dict_merge
from tests.helper import dict_compare

__author__ = 'sukrit'

"""
Integration test for mongo storage. These requires mongo instance running
"""


EXISTING_DEPLOYMENT1 = {
    'deployment': {
        'id': 'test-deployment-1'
    },
    'state': 'NEW',
    '_expiry': datetime.datetime.now(tz=pytz.UTC)
}

NOW = datetime.datetime(2022, 01, 01)


class TestMongoStore():

    @classmethod
    def setup(cls):
        cls.store = create(deployment_coll='deployments-integration-store')
        cls.store._deployments.drop()
        cls.store.setup()
        cls.store._deployments.insert_one(copy.deepcopy(EXISTING_DEPLOYMENT1))

    def _get_raw_document_without_internal_id(self, deployment_id):
        deployment = self.store._deployments.find_one(
            {'deployment.id': deployment_id})
        if deployment:
            del(deployment['_id'])
        return deployment

    def test_store_setup(self):

        # When I get the index informatiom
        # Note: Setup was already called
        indexes = self.store._deployments.index_information()

        # Indexes are created as expected
        for idx in ('created_idx', 'identity_idx', 'modified_idx',
                    'expiry_idx'):
            ok_(idx in indexes, '{} was not created'.format(idx))

    def test_get_deployment(self):

        # When I get existing deployment
        deployment = self.store.get_deployment('test-deployment-1')

        # Expected Deployment is returned
        expected_deployment = copy.deepcopy(EXISTING_DEPLOYMENT1)
        del(expected_deployment['_expiry'])
        dict_compare(deployment, expected_deployment)

    @freeze_time(NOW)
    def test_create_deployment(self):

        # Given: Deployment to be created
        deployment = {
            'deployment': {
                'id': 'test-deployment-create'
            },
            'state': 'NEW',
        }

        # When: I create new deployment
        self.store.create_deployment(deployment)

        # Then: Deployment gets created as expected
        created_deployment = self._get_raw_document_without_internal_id(
            'test-deployment-create')

        expected_deployment = dict_merge(deployment, {
            '_expiry': NOW,
            'modified': NOW,
        })

        dict_compare(created_deployment, expected_deployment)

    @freeze_time(NOW)
    def test_update_state(self):

        # When: I promote state for existing deployment
        self.store.update_state('test-deployment-1', 'PROMOTED')

        # Then: Deployment state is changed to promoted and set to never expire
        deployment = self._get_raw_document_without_internal_id(
            'test-deployment-1')
        expected_deployment = dict_merge(deployment, {
            '_expiry': datetime.datetime.max,
            'modified': NOW,
        })
        dict_compare(deployment, expected_deployment)

    def test_health(self):

        # When: I fetch the health state of the store
        health = self.store.health()

        # Then: Expected health instance is returned
        for key in ('nodes', 'primary', 'secondaries', 'collections'):
            ok_(key in health)
