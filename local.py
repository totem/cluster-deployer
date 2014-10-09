from ast import literal_eval
from celery.result import ResultBase
import deployer.celery
import os
from deployer.tasks.deployment import create, _fleet_check_running

from deployer.server import app

if __name__ == '__main__':
    deployer.celery.app.conf.CELERY_ALWAYS_EAGER = \
        literal_eval(os.getenv('CELERY_ALWAYS_EAGER', 'True'))
    dep_task = create.s({
        'meta-info': {
            'github': {
                'owner': 'totem',
                'repo': 'cluster-deployer',
                'commit': '',
                'branch': 'master'
            }

        },
        'deployment': {
            'name': 'totem-cluster-deployer-develop',
            'type': 'github-quay',
        },

        'templates': {
            'default-app': {
                'enabled': True,
                'priority': 1,
                'args': {
                    'image': ''
                }
            },
            'yoda-ec2-register': {
                'enabled': False
            },
            'default-logger': {
                'enabled': True
            }
        }
    })

    # result = deployer.celery.app.AsyncResult(
    #    '88e812ec-6afc-45a8-90fb-9c513ba8cfa6')
    result = dep_task.delay()
    result.get(propagate=False)
    # print result.ready()
    print result

    def ready(result):
        if result.ready():
            output = result.get(propagate=False)
            while isinstance(output, ResultBase):
                output = output.get(propagate=False)
            print(output)
    ready(result)

    result = _fleet_check_running.delay('test', 'v1', 1, 'app')
    result.get(propagate=False)
    # print result.ready()
    ready(result)

    # print deployer.celery.app.AsyncResult(
    # u'0fe50924-80b3-41ff-8bc3-717000c83ba5').result

    # if result.failed():
    #     print(result._traceback)
    # elif output.failed():
    #     print(output._traceback)
    # else:
    #     print(output)

    # result = add.delay(1,2)
    # output = result.get(propagate=False)
    # print(output)
    # if result.failed():
    #     print(result._traceback)
    # elif output.failed():
    #     print(output._traceback)
    # else:
    #     print(output.get())

    app.run(debug=True,
            port=int(os.getenv('API_PORT', '9000')))
