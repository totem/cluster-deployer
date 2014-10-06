from collections import defaultdict
import copy
import os

DEFAULT_DEPLOYMENT_TYPE = 'github-quay'

QUAY_PATH_PREFIX = 'quay.io/%s/totem-' % \
                   (os.getenv('QUAY_ORGANIZATION', 'totem'))

DEPLOYMENT_DEFAULTS = defaultdict(dict, {
    'github-quay': {
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
    }
})