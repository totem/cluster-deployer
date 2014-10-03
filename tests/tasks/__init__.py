__author__ = 'sukrit'

from deployer.celery import app


def setup_package():
    # Make celery synchronous for unit testing.
    app.conf['CELERY_ALWAYS_EAGER'] = True
    pass
