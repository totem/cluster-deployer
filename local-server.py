import os

import deployer.celery
from deployer.tasks.deployment import create
from deployer.server import app


if __name__ == '__main__':
    dep_task = create.s({
        'meta-info': {
            'github': {
                'owner': 'totem',
                'repo': 'spec-python',
                'commit': '9b3597b9da3957df7a91207ef4332d1efb400d7d',
                'branch': 'master'
            }

        },
        'deployment': {
            'name': 'spec-python',
            'type': 'github-quay',
            'version': 'v2'
        }
    })

    result = deployer.celery.app.AsyncResult(
        '4c72cd5b-f472-47ec-8e92-5b069d4cd620')
    # result = dep_task.delay()
    # result.get(propagate=True).get(propagate=True)
    # print result.ready()
    # print result
    #
    # def ready(result):
    #     output = result.get(propagate=False)
    #     while isinstance(output, ResultBase):
    #         if result.ready():
    #             output = output.get(propagate=False)
    #     return output
    # print(ready(result))

    # result = _fleet_check_running.delay('test', 'v1', 1, 'app')
    # result.get(propagate=False)
    # # print result.ready()
    # ready(result)

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

    # result = sumall.delay(1, 2, 3, 4)

    # print(result.id)
    # print(result.get().get()) # Works

    # print(deployer.celery.app.AsyncResult(
    # 'bfe715cf-0b65-452c-b6f2-98e02a4cb1f2').get().get())  #Hangs

    app.run(debug=True,
            port=int(os.getenv('API_PORT', '9000')))
