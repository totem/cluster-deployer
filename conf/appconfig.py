import os

# Logging configuration
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s %(message)s'
LOG_DATE = '%Y-%m-%d %I:%M:%S %p'
LOG_ROOT_LEVEL = os.getenv('LOG_ROOT_LEVEL', 'INFO').upper()
LOG_IDENTIFIER = os.getenv('LOG_IDENTIFIER', 'cluster-deployer')


DEFAULT_DEPLOYMENT_TYPE = 'git-quay'
QUAY_PATH_PREFIX = 'quay.io/%s' % os.getenv('QUAY_ORGANIZATION', 'totem')

DEPLOYMENT_TYPE_GIT_QUAY = 'git-quay'
DEPLOYMENT_TYPE_DEFAULT = 'default'

DEPLOYMENT_MODE_BLUEGREEN = 'blue-green'
DEPLOYMENT_MODE_REDGREEN = 'red-green'
DEPLOYMENT_MODE_AB = 'a/b'
DEPLOYMENT_MODE_CUSTOM = 'custom'

DEPLOYMENT_STATE_NEW = 'NEW'
DEPLOYMENT_STATE_STARTED = 'STARTED'
DEPLOYMENT_STATE_PROMOTED = 'PROMOTED'
DEPLOYMENT_STATE_FAILED = 'FAILED'
DEPLOYMENT_STATE_DECOMMISSIONED = 'DECOMMISSIONED'

RUNNING_DEPLOYMENT_STATES = [DEPLOYMENT_STATE_NEW, DEPLOYMENT_STATE_STARTED,
                             DEPLOYMENT_STATE_PROMOTED]

BOOLEAN_TRUE_VALUES = {"true", "yes", "y", "1", "on"}

API_PORT = int(os.getenv('API_PORT', '9000'))


LEVEL_FAILED = 1
LEVEL_FAILED_WARN = 2
LEVEL_SUCCESS = 3
LEVEL_STARTED = 4
LEVEL_PENDING = 5

DEFAULT_HIPCHAT_TOKEN = os.getenv('HIPCHAT_TOKEN', '')
DEFAULT_GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
BASE_URL = os.getenv('BASE_URL', 'http://localhost:{0}'.format(API_PORT))

TOTEM_ENV = os.getenv('TOTEM_ENV', 'local')
CLUSTER_NAME = os.getenv('CLUSTER_NAME', TOTEM_ENV)

NOTIFICATIONS_DEFAULTS = {
    'hipchat': {
        'enabled': os.getenv('HIPCHAT_ENABLED', 'false').strip()
        .lower() in BOOLEAN_TRUE_VALUES,
        'room': os.getenv('HIPCHAT_ROOM', 'not-set'),
        'token': '',
        'level': LEVEL_FAILED,
        'colors': {
            str(LEVEL_FAILED): 'red',
            str(LEVEL_FAILED_WARN): 'red',
            str(LEVEL_SUCCESS): 'green',
            str(LEVEL_STARTED): 'yellow',
            str(LEVEL_PENDING): 'yellow',
        },
        'url': 'https://api.hipchat.com'
    },
    'github': {
        'enabled': os.getenv(
            'GITHUB_NOTIFICATION_ENABLED', 'false')
        .strip().lower() in BOOLEAN_TRUE_VALUES,
        'token': '',
        'level': LEVEL_PENDING
    }
}

DEPLOYMENT_DEFAULTS = {
    DEPLOYMENT_TYPE_GIT_QUAY: {
        'deployment': {
            'name': '{GIT_OWNER}-{GIT_REPO}-{GIT_REF}',
            'type': 'git-quay'
        },
        'templates': {
            'app': {
                'args': {
                    'image': QUAY_PATH_PREFIX +
                    '/{GIT_OWNER}-{GIT_REPO}:{GIT_COMMIT}',
                    'environment': {},
                    'docker-args': ''
                },
                'name': 'default-app',
            },
            'yoda-register': {
                'name': 'yoda-register'
            }
        }
    },
    DEPLOYMENT_TYPE_DEFAULT: {
        'meta-info': {
            'job-id': 'not_set',
            'git': {
                'owner': 'not_set',
                'repo': 'not_set',
                'ref': 'master',
                'commit': 'not_set',
                'type': 'github'
            }
        },
        'deployment': {
            'type': 'default',
            'version': None,
            'mode': DEPLOYMENT_MODE_BLUEGREEN,
            'nodes': 1,
            'check': {
                'min-nodes': 1,
                'port': None,
                'attempts': 10,
                'timeout': '10s'
            }
        },
        'templates': {
            'app': {
                'args': {
                    'environment': {},
                }
            }
        },
        'proxy': {
            'hosts': {},
            'listeners': {},
            'upstreams': {}
        },
        'security': {
            'profile': 'default'
        },
        'notifications': NOTIFICATIONS_DEFAULTS
    }
}

UPSTREAM_DEFAULTS = {
    'mode': 'http',
    'health': {
        'timeout': '5s'
    },
    'ttl': '1w'
}

TEMPLATE_DEFAULTS = {
    'enabled': True,
    'args': {}
}

FLEET_SETTINGS = {
    'hosts': os.getenv('FLEET_HOST', '172.17.42.1'),
    'fab_settings': {
        'key_filename': os.getenv('SSH_HOST_KEY',
                                  os.getenv('HOME')+'/.ssh/id_rsa')
    }
}

FLEET_TEMPLATE_SETTINGS = {
    'github': {
        'token': os.getenv('GITHUB_TOKEN')
    }
}

DEFAULT_LOCK_TTL = 3600

LOCK_JOB_TTL = 120
LOCK_JOB_BASE = '/cluster-deployer/locks/jobs'
LOCK_JOB_SYNC_PROMOTED_UPSTREAMS = 'sync-promoted-upstreams'
LOCK_JOB_SYNC_PROMOTED_UNITS = 'sync-promoted-units'

TASK_SETTINGS = {
    'DEFAULT_GET_TIMEOUT': 600,
    'DEFAULT_RETRIES': 5,
    'DEFAULT_RETRY_DELAY': 10,
    'SSH_RETRY_DELAY': 10,
    'SSH_RETRIES': 10,
    'CHECK_RUNNING_RETRIES': 30,
    'CHECK_RUNNING_RETRY_DELAY': 30,
    'CHECK_DISCOVERY_RETRIES': 20,
    'CHECK_DISCOVERY_RETRY_DELAY': 30,
    'LOCK_RETRIES': 64,
    'LOCK_RETRY_DELAY': 60,
    'DEPLOYMENT_WAIT_RETRIES': 60,
    'DEPLOYMENT_WAIT_RETRY_DELAY': 60,
    'CHECK_NODE_RETRY_DELAY': 10,
}

TOTEM_ETCD_SETTINGS = {
    'base': os.getenv('ETCD_TOTEM_BASE', '/totem'),
    'host': os.getenv('ETCD_HOST', '127.0.0.1'),
    'port': int(os.getenv('ETCD_PORT', '4001')),
    'yoda_base': os.getenv('ETCD_YODA_BASE', '/yoda'),
}

CORS_SETTINGS = {
    'enabled': os.getenv('CORS_ENABLED', 'true').strip().lower() in
    BOOLEAN_TRUE_VALUES,
    'origins': os.getenv('CORS_ORIGINS', '*')
}

ENCRYPTION = {
    'store': os.getenv('ENCRYPTION_STORE', None),
    's3': {
        'bucket': os.getenv('ENCRYPTION_S3_BUCKET', 'not-set'),
        'base': os.getenv('ENCRYPTION_S3_BASE', 'totem/keys'),
    },
    'passphrase': os.getenv('ENCRYPTION_PASSPHRASE', None),
}

MIME_JSON = 'application/json'
MIME_HTML = 'text/html'
MIME_ROOT_V1 = 'application/vnd.deployer.root.v1+json'
MIME_TASK_V1 = 'application/vnd.deployer.task.v1+json'
MIME_APP_LIST_V1 = 'application/vnd.deployer.app-list.v1+json'
MIME_APP_VERSION_LIST_V1 = 'application/vnd.deployer.app.version-list.v1+json'
MIME_APP_VERSION_V1 = 'application/vnd.deployer.app.version.v1+json'
MIME_APP_VERSION_UNIT_LIST_V1 = \
    'application/vnd.deployer.app.version.unit-list.v1+json'
MIME_APP_VERSION_CREATE_V1 = \
    'application/vnd.deployer.app.version.create.v1+json'
MIME_APP_VERSION_DELETE_V1 = \
    'application/vnd.deployer.app.version.delete.v1+json'
MIME_APP_DELETE_V1 = 'application/vnd.deployer.app.delete.v1+json'
MIME_HEALTH_V1 = 'application/vnd.deployer.health.v1+json'
MIME_RECOVERY_V1 = 'application/vnd.deployer.recovery.v1+json'

SCHEMA_TASK_V1 = 'task-v1'
SCHEMA_ROOT_V1 = 'root-v1'
SCHEMA_APP_LIST_V1 = 'app-list-v1'
SCHEMA_APP_VERSION_CREATE_V1 = 'app-version-create-v1'
SCHEMA_APP_VERSION_V1 = 'app-version-v1'
SCHEMA_APP_VERSION_LIST_V1 = 'app-version-list-v1'
SCHEMA_APP_VERSION_UNIT_LIST_V1 = 'app-version-unit-list-v1'
SCHEMA_HEALTH_V1 = 'health-v1'
SCHEMA_RECOVERY_V1 = 'recovery-v1'

API_MAX_PAGE_SIZE = 1000
API_DEFAULT_PAGE_SIZE = 10

HEALTH_OK = 'ok'
HEALTH_FAILED = 'failed'

# Storage
DEFAULT_STORE_NAME = 'mongo'
# Mongo Settings
MONGODB_USERNAME = os.getenv('MONGODB_USERNAME', '')
MONGODB_PASSWORD = os.getenv('MONGODB_PASSWORD', '')
MONGODB_HOST = os.getenv('MONGODB_HOST', '127.0.0.1')
MONGODB_PORT = int(os.getenv('MONGODB_PORT', '27017'))
MONGODB_DB = os.getenv('MONGODB_DB') or 'totem-{}'.format(TOTEM_ENV)
MONGODB_AUTH_DB = os.getenv('MONGODB_AUTH_DB') or 'admin'
MONGODB_AUTH = '{0}:{1}@'.format(MONGODB_USERNAME, MONGODB_PASSWORD) \
    if MONGODB_USERNAME else ''
MONGODB_DEFAULT_URL = 'mongodb://{0}{1}:{2}/{3}'.format(
    MONGODB_AUTH, MONGODB_HOST, MONGODB_PORT, MONGODB_AUTH_DB)
MONGODB_URL = os.getenv('MONGODB_URL') or MONGODB_DEFAULT_URL
MONGODB_DEPLOYMENT_COLLECTION = os.getenv('MONGODB_DEPLOYMENT_COLLECTION') or \
    'deployments'
MONGODB_EVENT_COLLECTION = os.getenv('MONGODB_EVENT_COLLECTION') or \
    'events'

# Number of seconds after a non running deployment will expire
DEFAULT_DEPLOYMENT_EXPIRY_SECONDS = 4 * 7 * 24 * 3600  # 4 weeks
DEPLOYMENT_EXPIRY_SECONDS = int(
    os.getenv('DEPLOYMENT_EXPIRY_SECONDS', DEFAULT_DEPLOYMENT_EXPIRY_SECONDS))
