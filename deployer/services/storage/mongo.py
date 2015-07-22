import datetime
from pymongo import MongoClient
import pymongo
import pytz
from conf.appconfig import MONGODB_URL, MONGODB_DEPLOYMENT_COLLECTION, \
    MONGODB_DB, DEPLOYMENT_EXPIRY_SECONDS, MONGODB_EVENT_COLLECTION, \
    DEPLOYMENT_STATE_PROMOTED, RUNNING_DEPLOYMENT_STATES
from deployer.services.storage.base import AbstractStore

__author__ = 'sukrit'


def create(url=MONGODB_URL, dbname=MONGODB_DB,
           deployment_coll=MONGODB_DEPLOYMENT_COLLECTION,
           event_coll=MONGODB_EVENT_COLLECTION
           ):
    """
    Creates Instance of MongoStore
    :keyword url: MongoDB Connection String
    :type url: str
    :keyword dbname: MongoDB database name
    :type dbname: str
    :keyword deployment_coll: MongoDB Deployment Collection name
    :type deployment_coll: str
    :return: Instance of MongoStore
    :rtype: MongoStore
    """
    return MongoStore(url, dbname, deployment_coll, event_coll)


class MongoStore(AbstractStore):
    """
    Mongo based implementation of store.
    """

    def __init__(self, url, dbname, deployment_coll, event_coll):
        self.client = MongoClient(url)
        self.dbname = dbname
        self.deployment_coll = deployment_coll
        self.event_coll = event_coll

    def setup(self):
        """
        Setup indexes for mongo store
        :return:
        """
        idxs = self._deployments.index_information()
        if 'created_idx' not in idxs:
            self._deployments.create_index(
                [('date', pymongo.DESCENDING)], name='created_idx')

        if 'identity_idx' not in idxs:
            self._deployments.create_index(
                'deployment.id', name='identity_idx', unique=True)

        if 'modified_idx' not in idxs:
            self._deployments.create_index(
                [('modified', pymongo.DESCENDING)], name='modified_idx')

        if 'expiry_idx' not in idxs:
            self._deployments.create_index(
                [('_expiry', pymongo.DESCENDING)], name='expiry_idx',
                background=True, expireAfterSeconds=DEPLOYMENT_EXPIRY_SECONDS)

    @property
    def _db(self):
        return self.client[self.dbname]

    @property
    def _deployments(self):
        """
        Gets the deployments collection reference
        :return: Deployment collection reference
        :rtype: pymongo.collection.Collection
        """
        return self._db[self.deployment_coll]

    @property
    def _events(self):
        """
        Gets the events collection reference
        :return: Event collection reference
        :rtype: pymongo.collection.Collection
        """
        return self._db[self.event_coll]

    def create_deployment(self, deployment):
        deployment_upd = self.apply_modified_ts(deployment)
        deployment_upd['_expiry'] = datetime.datetime.now(tz=pytz.UTC)
        self._deployments.replace_one(
            {
                'deployment.id': deployment_upd['deployment']['id']
            },
            self.apply_modified_ts(deployment_upd),
            upsert=True
        )

    @staticmethod
    def _generate_expiry(state):
        if state == DEPLOYMENT_STATE_PROMOTED:
            return datetime.datetime.max
        return datetime.datetime.now(tz=pytz.UTC)

    def update_state(self, deployment_id, state):
        self._deployments.update_one(
            {
                'deployment.id': deployment_id,
            },
            {
                '$set': {
                    'state': state,
                    'modified': datetime.datetime.now(tz=pytz.UTC),
                    '_expiry': self._generate_expiry(state)
                }
            }
        )

    def get_deployment(self, deployment_id):
        return self._deployments.find_one(
            {
                'deployment.id': deployment_id,
            },
            projection={
                '_id': False,
                '_expiry': False
            }
        )

    def health(self):
        return {
            'nodes': list(self.client.nodes),
            'primary': self.client.primary,
            'secondaries': list(self.client.secondaries),
            'collections': self._db.collection_names(
                include_system_collections=False)
        }

    def _add_raw_event(self, event):
        """
        Adds event to event store
        :param event:
        :return:
        """
        self._events.insert_one(event)

    def update_state_bulk(self, name, new_state, existing_state=None,
                          version=None):
        u_filter = {
            'deployment.name': name
        }
        if existing_state:
            u_filter['state'] = existing_state

        if version:
            u_filter['deployment.version'] = version

        self._deployments.update_many(u_filter, {
            '$set': {
                'state': new_state,
                'modified': datetime.datetime.now(tz=pytz.UTC),
                '_expiry': self._generate_expiry(new_state)
            }
        })

    def find_apps(self):
        return [
            app['_id'] for app in
            self._deployments.aggregate([
                {'$group': {'_id': '$deployment.name'}},
                {'$sort':  {'_id':  1}}
            ]) or []
        ]

    def filter_deployments(self, name, version=None, only_running=True):
        u_filter = {
            'deployment.name': name
        }
        if version:
            u_filter['deployment.version'] = version
        if only_running:
            u_filter['state'] = {
                '$in': RUNNING_DEPLOYMENT_STATES
            }
        return [
            deployment for deployment in
            self._deployments.find(u_filter, projection={
                '_id': False
            }).sort('deployment.version')
        ]
