import os

# Logging configuration
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s %(message)s'
LOG_DATE = '%Y-%m-%d %I:%M:%S %p'
LOG_ROOT_LEVEL = os.getenv('LOG_ROOT_LEVEL', 'INFO').upper()


DEFAULT_DEPLOYMENT_TYPE = 'github-quay'
QUAY_PATH_PREFIX = 'quay.io/%s/totem-' % \
                   (os.getenv('QUAY_ORGANIZATION', 'totem'))

DEPLOYMENT_TYPE_GITHUB_QUAY = 'github-quay'
DEPLOYMENT_TYPE_DEFAULT = 'default'

DEPLOYMENT_DEFAULTS = {
    DEPLOYMENT_TYPE_GITHUB_QUAY: {
        'deployment': {
            'name': '{GIT_OWNER}-{GIT_REPO}-{GIT_BRANCH}',
            'type': 'github-quay',
        },
        'templates': {
            'default-app': {
                'args': {
                    'image': QUAY_PATH_PREFIX +
                    '{GIT_OWNER}/{GIT_REPO}:{GIT_COMMIT}',
                    'environment': {},
                    'docker-args': ''
                },
                'enabled': True,
                'priority': 1,
            },
            'yoda-register': {
                'enabled': True,
                'priority': 2,
            },
            'default-logger': {
                'enabled': True,
                'priority': 2,
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
            'version': None
        },
        'templates': {
        }
    }
}

TEMPLATE_DEFAULTS = {
    'priority': 1,
    'enabled': True,
    'args': {}
}
