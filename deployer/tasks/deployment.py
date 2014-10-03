from deployer.celery import app

__author__ = 'sukrit'


@app.task(name='deployment.create')
def create(deployment):
    print(str(deployment))
    return deployment


@app.task(name='deployment.wire')
def wire(proxy):
    print(str(proxy))


@app.task(name='deployment.unwire')
def unwire(proxy):
    print(str(proxy))


@app.task(name='deployment.unwire')
def delete(deployment):
    print(str(deployment))
