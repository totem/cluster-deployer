import os

# Logging configuration
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s %(message)s'
LOG_DATE = '%Y-%m-%d %I:%M:%S %p'
LOG_ROOT_LEVEL = os.getenv('LOG_ROOT_LEVEL', 'INFO').upper()


DEFAULT_DEPLOYMENT_TYPE = 'github-quay'
QUAY_PATH_PREFIX = 'quay.io/%s/%s' % (os.getenv('QUAY_ORGANIZATION', 'totem'),
                                      os.getenv('QUAY_PREFIX', 'totem-'))

DEPLOYMENT_TYPE_GITHUB_QUAY = 'github-quay'
DEPLOYMENT_TYPE_DEFAULT = 'default'

DEPLOYMENT_MODE_BLUEGREEN = 'blue-green'
DEPLOYMENT_MODE_REDGREEN = 'red-green'
DEPLOYMENT_MODE_AB = 'a/b'
DEPLOYMENT_MODE_CUSTOM = 'custom'

DEPLOYMENT_STATE_STARTED = 'STARTED'
DEPLOYMENT_STATE_PROMOTED = 'PROMOTED'
DEPLOYMENT_STATE_FAILED = 'FAILED'
DEPLOYMENT_STATE_DECOMMISSIONED = 'DECOMMISSIONED'

BOOLEAN_TRUE_VALUES = {"true", "yes", "y", "1", "on"}


DEPLOYMENT_DEFAULTS = {
    DEPLOYMENT_TYPE_GITHUB_QUAY: {
        'deployment': {
            'name': '{GIT_OWNER}-{GIT_REPO}-{GIT_BRANCH}',
            'type': 'github-quay'
        },
        'templates': {
            'app': {
                'args': {
                    'image': QUAY_PATH_PREFIX + '{GIT_REPO}:{GIT_COMMIT}',
                    'environment': {},
                    'docker-args': ''
                },
                'name': 'default-app',
            },
            'yoda-register': {
                'name': 'yoda-ec2-register'
            },
            'logger': {
                'name': 'default-logger'
            }
        }
    },
    DEPLOYMENT_TYPE_DEFAULT: {
        'meta-info': {
            'job-id': 'not_set',
            'github': {
                'owner': 'not_set',
                'repo': 'not_set',
                'branch': 'master',
                'commit': 'not_set'
            }
        },
        'deployment': {
            'type': 'default',
            'version': None,
            'mode': DEPLOYMENT_MODE_BLUEGREEN,
            'nodes': 2
        },
        'templates': {
        },
        'proxy': {
            'hosts': [],
            'listeners': []
        }
    }
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

TASK_SETTINGS = {
    'DEFAULT_GET_TIMEOUT': 600,
    'DEFAULT_RETRIES': 5,
    'DEFAULT_RETRY_DELAY': 10,
    'CHECK_RUNNING_RETRIES': 60,
    'CHECK_RUNNING_RETRY_DELAY': 10,
    'LOCK_RETRIES': 10,
    'LOCK_RETRY_DELAY': 60,
    'DEPLOYMENT_WAIT_RETRIES': 30,
    'DEPLOYMENT_WAIT_RETRY_DELAY': 20

}

TOTEM_ETCD_SETTINGS = {
    'base': os.getenv('ETCD_TOTEM_BASE', '/totem'),
    'host': os.getenv('ETCD_HOST', '172.17.42.1'),
    'port': int(os.getenv('ETCD_PORT', '4001')),
    'yoda_base': os.getenv('ETCD_YODA_BASE', '/yoda'),
}

SEARCH_SETTINGS = {
    'enabled': os.getenv('SEARCH_ENABLED', 'true').strip().lower() in
    BOOLEAN_TRUE_VALUES,
    'host': os.getenv('ELASTICSEARCH_HOST', '172.17.42.1'),
    'port': os.getenv('ELASTICSEARCH_PORT', '9200'),
    'default-index': 'cluster-deployer-%s' % os.getenv('CLUSTER_NAME', 'local')
}
