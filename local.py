from ast import literal_eval
import deployer.celery
import os
from deployer.tasks.deployment import create

from deployer.server import app

if __name__ == '__main__':
    deployer.celery.app.conf.CELERY_ALWAYS_EAGER = \
        literal_eval(os.getenv('CELERY_ALWAYS_EAGER', 'True'))
    result = create.delay({
        'meta-info': {
            'github': {
                'owner': 'totem',
                'repo': 'cluster-deployer'
            }

        },
        'deployment': {
            'name': 'totem-cluster-deployer-develop',
            'version': 'v1',
            'type': 'github-quay',
        },

        'templates': {
            'default-app': {
                'enabled': True,
                'priority': 1,
            },
            'yoda-register': {
                'enabled': False
            },
            'default-logger': {
                'enabled': True
            }
        }
    })
    print result.get(propagate=False, timeout=60)
    if result._traceback:
        print(result._traceback)
    app.run(debug=True,
            port=int(os.getenv('API_PORT', '9000')))
