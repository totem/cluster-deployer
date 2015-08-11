from deployer.celery import app

__author__ = 'sukrit'


def setup_package():
    # Make celery synchronous for unit testing.
    app.conf['CELERY_ALWAYS_EAGER'] = True
    pass
