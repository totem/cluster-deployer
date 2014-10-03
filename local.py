import deployer.celery
from deployer.tasks.deployment import create

from deployer.server import app

if __name__ == '__main__':
    deployer.celery.app.conf.CELERY_ALWAYS_EAGER = True
    result = create.delay({
        'meta-info': {
            'job-id': 'test',
            'github': {
                'owner': 'totem',
                'repo': 'cluster-deployer',
                'branch': 'develop',
                'commit': '12313345'
            }
        },
        'deployment': {
            'name': 'totem-cluster-deployer-develop',
            'version': 'v1'
        },
        'type': 'github-quay',
        'templates': {
            'default-app': {
                'name': 'default-app',
                'args': {
                    'image': 'quay.io/totem/totem-cluster-deployer:12313345',
                    'environment': {},
                    'docker-args': ''
                },
                'enabled': True,
                'priority': 1,
            },
            'yoda-register': {
                'enabled': False,
                'priority': 2,
            },
            'default-logger': {
                'enabled': True,
                'priority': 2,
            }
        }
    })
    print result.get(propagate=True, timeout=60)
    app.run(debug=True)
