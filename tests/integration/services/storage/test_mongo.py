import copy
import datetime
from freezegun import freeze_time
import pymongo
from conf.appconfig import DEPLOYMENT_STATE_DECOMMISSIONED, \
    DEPLOYMENT_STATE_NEW, DEPLOYMENT_STATE_PROMOTED, CLUSTER_NAME, \
    DEPLOYMENT_STATE_STARTED
from deployer.services.storage.mongo import create
from nose.tools import ok_, eq_
from deployer.util import dict_merge
from tests.helper import dict_compare

__author__ = 'sukrit'


"""
Integration test for mongo storage. These requires mongo instance running
"""

NOW = datetime.datetime(2022, 01, 01)


EXISTING_DEPLOYMENTS = {
    'test-deployment1-v0': {
        'id': 'test-deployment1-v0',
        'deployment': {
            'name': 'test-deployment1',
            'version': 'v0'
        },
        'state': DEPLOYMENT_STATE_DECOMMISSIONED,
        '_expiry': NOW,
        'cluster': CLUSTER_NAME
    },
    'test-deployment1-v1': {
        'id': 'test-deployment1-v1',
        'deployment': {
            'name': 'test-deployment1',
            'version': 'v1'
        },
        'state': DEPLOYMENT_STATE_PROMOTED,
        '_expiry': NOW,
        'cluster': CLUSTER_NAME
    },
    'test-deployment1-v2': {
        'id': 'test-deployment1-v2',
        'deployment': {
            'name': 'test-deployment1',
            'version': 'v2'
        },
        'state': DEPLOYMENT_STATE_NEW,
        '_expiry': NOW,
        'cluster': CLUSTER_NAME
    },
    'test-deployment2-v1': {
        'id': 'test-deployment2-v1',
        'deployment': {
            'name': 'test-deployment2',
            'version': 'v1'
        },
        'state': DEPLOYMENT_STATE_DECOMMISSIONED,
        '_expiry': NOW,
        'cluster': CLUSTER_NAME
    },
    'test-deployment2-v2': {
        'id': 'test-deployment2-v2',
        'deployment': {
            'name': 'test-deployment2',
            'version': 'v2'
        },
        'state': DEPLOYMENT_STATE_STARTED,
        '_expiry': NOW,
        'cluster': CLUSTER_NAME
    },
    'test-deployment3-v1': {
        'id': 'test-deployment3-v1',
        'deployment': {
            'name': 'test-deployment2',
            'version': 'v1'
        },
        'state': DEPLOYMENT_STATE_STARTED,
        '_expiry': NOW,
        'cluster': 'DIFFERENT-CLUSTER'
    }
}


class TestMongoStore():

    @classmethod
    def setup(cls):
        cls.store = create(
            deployment_coll='deployments-integration-store',
            event_coll='events-integration-store'
        )
        cls.store._deployments.drop()
        cls.store._events.drop()
        cls.store.setup()
        requests = [pymongo.InsertOne(copy.deepcopy(deployment)) for deployment
                    in EXISTING_DEPLOYMENTS.values()]
        cls.store._deployments.bulk_write(requests)

    def _get_raw_document_without_internal_id(self, deployment_id):
        deployment = self.store._deployments.find_one(
            {'id': deployment_id},
            projection={'_id': False}
        )
        return deployment

    def _find_matching_deployments_with_name(self, name):
        deployments = self.store._deployments.find({
            'deployment.name': name
        }, projection={'_id': False}).sort('id',
                                           pymongo.ASCENDING)
        deployments = [deployment for deployment in deployments]
        return deployments

    def test_store_setup(self):

        # When I get the index informatiom
        # Note: Setup was already called
        indexes = self.store._deployments.index_information()

        # Indexes are created as expected
        for idx in ('created_idx', 'identity_idx', 'app_idx',
                    'expiry_idx'):
            ok_(idx in indexes, '{} was not created'.format(idx))

    def test_get_deployment(self):

        # When I get existing deployment
        deployment = self.store.get_deployment('test-deployment1-v1')

        # Expected Deployment is returned
        expected_deployment = copy.deepcopy(
            EXISTING_DEPLOYMENTS['test-deployment1-v1'])
        del(expected_deployment['_expiry'])
        dict_compare(deployment, expected_deployment)

    @freeze_time(NOW)
    def test_create_deployment(self):

        # Given: Deployment to be created
        deployment = {
            'id': 'test-deployment-create',
            'deployment': {},
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
        self.store.update_state('test-deployment1-v1', 'PROMOTED')

        # Then: Deployment state is changed to promoted and set to never expire
        deployment = self._get_raw_document_without_internal_id(
            'test-deployment1-v1')
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

    @freeze_time(NOW)
    def test_add_event(self):

        # When: I add event to mongo store
        self.store.add_event(
            'MOCK_EVENT',
            details={'mock': 'details'},
            search_params={
                'meta-info': {
                    'mock': 'search'
                }
            })

        # Then: Event gets added as expected
        event = self.store._events.find_one({'type': 'MOCK_EVENT'})
        del(event['_id'])
        dict_compare(event, {
            'component': 'deployer',
            'type': 'MOCK_EVENT',
            'date': NOW,
            'meta-info': {
                'mock': 'search'
            },
            'details': {
                'mock': 'details'
            }
        })

    def test_update_state_bulk(self):
        # Given: Deployment that needs to be updated
        deployment_name = 'test-deployment1'
        # When: I bulk update state for existing deployments
        self.store.update_state_bulk(
            deployment_name, DEPLOYMENT_STATE_DECOMMISSIONED)

        # Then: All versions of given deployment are marked as decommissioned
        deployments = self._find_matching_deployments_with_name(
            deployment_name)
        ok_(deployments is not None,
            'Expecting to find deployments with name:{} '.format(
                deployment_name))
        eq_(len(deployments), 3)
        for deployment in deployments:
            eq_(deployment['state'], DEPLOYMENT_STATE_DECOMMISSIONED)

    def test_update_state_bulk_ith_given_state_and_version(self):
        # Given: Deployment that needs to be updated
        deployment_name = 'test-deployment1'
        version = 'v1'
        existing_state = DEPLOYMENT_STATE_PROMOTED

        # When: I bulk update state for existing deployments
        self.store.update_state_bulk(
            deployment_name, DEPLOYMENT_STATE_DECOMMISSIONED, version=version,
            existing_state=existing_state)

        # Then: Deployments with maching state and version gets updated
        deployments = self._find_matching_deployments_with_name(
            deployment_name)
        ok_(deployments is not None,
            'Expecting to find deployments with name:{} '.format(
                deployment_name))
        eq_(len(deployments), 3)
        eq_(deployments[0]['state'], DEPLOYMENT_STATE_DECOMMISSIONED)
        eq_(deployments[1]['state'], DEPLOYMENT_STATE_DECOMMISSIONED)
        eq_(deployments[2]['state'], DEPLOYMENT_STATE_NEW)

    def test_find_apps(self):
        # When: I find applications from the store
        apps = self.store.find_apps()

        # Then: Expected apps are returned
        eq_(apps, ['test-deployment1', 'test-deployment2'])

    def test_filter_deployments(self):
        # When: I filter deployments from the store
        deployments = self.store.filter_deployments()

        # Then:Running deployments are returned
        eq_(len(deployments), 3)
        dict_compare(deployments[0],
                     EXISTING_DEPLOYMENTS['test-deployment1-v1'])
        dict_compare(deployments[1],
                     EXISTING_DEPLOYMENTS['test-deployment1-v2'])
        dict_compare(deployments[2],
                     EXISTING_DEPLOYMENTS['test-deployment2-v2'])

    def test_filter_deployments_by_name(self):
        # When: I filter deployments from the store
        deployments = self.store.filter_deployments('test-deployment1')

        # Then: Expected deployments are returned
        eq_(len(deployments), 2)
        dict_compare(deployments[0],
                     EXISTING_DEPLOYMENTS['test-deployment1-v1'])
        dict_compare(deployments[1],
                     EXISTING_DEPLOYMENTS['test-deployment1-v2'])

    def test_filter_deployments_with_version(self):
        # When: I filter deployments from the store with given version
        deployments = self.store.filter_deployments(
            'test-deployment1', version='v1')

        # Then: Expected deployments are returned
        eq_(len(deployments), 1)
        dict_compare(deployments[0],
                     EXISTING_DEPLOYMENTS['test-deployment1-v1'])

    def test_filter_deployments_with_state(self):
        # When: I filter deployments from the store with given state
        deployments = self.store.filter_deployments(state=DEPLOYMENT_STATE_NEW)

        # Then: Expected deployments are returned
        eq_(len(deployments), 1)
        dict_compare(deployments[0],
                     EXISTING_DEPLOYMENTS['test-deployment1-v2'])

    def test_filter_deployments_with_excluded_names(self):
        # When: I filter deployments from the store with given state
        deployments = self.store.filter_deployments(
            exclude_names=('test-deployment1',))

        # Then: Expected deployments are returned
        eq_(len(deployments), 1)
        dict_compare(deployments[0],
                     EXISTING_DEPLOYMENTS['test-deployment2-v2'])

    def test_filter_deployment_ids(self):
        # When: I filter deployments from the store for ids only
        deployments = self.store.filter_deployments('test-deployment1',
                                                    only_ids=True)

        # Then: Expected deployment ids are returned
        eq_(len(deployments), 2)
        dict_compare(deployments[0], {'id': 'test-deployment1-v1'})
        dict_compare(deployments[1], {'id': 'test-deployment1-v2'})

    @freeze_time(NOW)
    def test_update_runtime_upstreams(self):

        # Given: Upstreams that needs to be updated
        upstreams = {
            '8080': {
                'upstream1': 'host1:40001',
                'upstream2': 'host2:40001'
            }
        }

        # When: I promote state for existing deployment
        self.store.update_runtime_upstreams('test-deployment1-v1', upstreams)

        # Then: Deployment state is changed to promoted and set to never expire
        deployment = self._get_raw_document_without_internal_id(
            'test-deployment1-v1')
        expected_deployment = dict_merge(deployment, {
            'runtime': {
                'upstreams': upstreams
            },
            'modified': NOW,
        })
        dict_compare(deployment, expected_deployment)

    @freeze_time(NOW)
    def test_update_runtime_units(self):

        # Given: Upstreams that needs to be updated
        units = [
            {
                'name': 'unit1',
                'machine':  'machine1',
                'active': 'active',
                'sub': 'dead'
            }
        ]

        # When: I promote state for existing deployment
        self.store.update_runtime_units('test-deployment1-v1', units)

        # Then: Deployment state is changed to promoted and set to never expire
        deployment = self._get_raw_document_without_internal_id(
            'test-deployment1-v1')
        expected_deployment = dict_merge(deployment, {
            'runtime': {
                'units': units
            },
            'modified': NOW,
        })
        dict_compare(deployment, expected_deployment)
