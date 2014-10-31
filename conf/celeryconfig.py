from datetime import timedelta
import os
import re
from ast import literal_eval

from celery.schedules import crontab
from kombu import Queue


MONGO_URL = os.getenv('MONGO_URL',
                      'mongodb://localhost:27017/cluster-deployer')
CLUSTER_NAME = os.getenv('CLUSTER_NAME', 'local')
MONGO_RESULTS_DB = os.getenv('MONGO_RESULTS_DB') or os.path.basename(MONGO_URL)

# Broker and Queue Settings
BROKER_URL = os.getenv('BROKER_URL', 'amqp://guest:guest@localhost:5672/')
CELERY_DEFAULT_QUEUE = 'cluster-deployer-%s-default' % CLUSTER_NAME
CELERY_PREFORK_QUEUE = 'cluster-deployer-%s-prefork' % CLUSTER_NAME
CELERY_QUEUES = (
    Queue(CELERY_DEFAULT_QUEUE, routing_key='default'),
    Queue(CELERY_PREFORK_QUEUE, routing_key='prefork'),
)
CELERY_DEFAULT_EXCHANGE_TYPE = 'direct'
CELERY_DEFAULT_ROUTING_KEY = 'default'
CELERY_ROUTES = {
    'deployer.tasks.deployment._fleet_deploy': {
        'routing_key': 'prefork',
    },
    'deployer.tasks.deployment._fleet_undeploy': {
        'routing_key': 'prefork',
    },
    'deployer.tasks.deployment._wait_for_undeploy': {
        'routing_key': 'prefork',
    },
    'deployer.tasks.deployment._wait_for_undeploy': {
        'routing_key': 'prefork',
    },
    'deployer.tasks.deployment._fleet_check_running': {
        'routing_key': 'prefork',
    }
}

# Results / Backend
CELERY_RESULT_BACKEND = MONGO_URL
CELERY_IMPORTS = ('deployer.tasks', 'deployer.tasks.deployment',
                  'deployer.tasks.common', 'deployer.tasks.proxy',
                  'celery.task')
CELERY_MONGODB_BACKEND_SETTINGS = {
    'database': MONGO_RESULTS_DB,
    'taskmeta_collection': os.getenv('MONGO_RESULTS_COLLECTION') or
    'celery_taskmeta_%s' % re.sub('[^A-Za-z_0-9]', '_', CLUSTER_NAME)
}
CELERY_ACCEPT_CONTENT = ['json', 'pickle']
CELERY_TASK_SERIALIZER = 'pickle'
CELERY_RESULT_SERIALIZER = 'pickle'
CELERY_ALWAYS_EAGER = literal_eval(os.getenv('CELERY_ALWAYS_EAGER', 'False'))
CELERY_CHORD_PROPAGATES = True

CELERY_STORE_ERRORS_EVEN_IF_IGNORED = True
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
CELERY_IGNORE_RESULT = False
CELERYD_TASK_SOFT_TIME_LIMIT = 300
CELERYD_TASK_TIME_LIMIT = 330
CELERY_SEND_TASK_SENT_EVENT = True
CELERY_TASK_RESULT_EXPIRES = timedelta(days=7)

# Remote Management
CELERYD_POOL_RESTARTS = True

# Messages older than 1 hour will be discarded
CELERY_EVENT_QUEUE_TTL = 3600

# Queue Settings
CELERY_QUEUE_HA_POLICY = 'all'

# GLobal Settings
CELERY_TIMEZONE = 'UTC'

# Task releated settings
CELERY_ACKS_LATE = True

# Celery Beat settings
CELERYBEAT_SCHEDULE = {
    'celery.task.backend_cleanup': {
        'task': 'deployer.tasks.backend_cleanup',
        'schedule': crontab(hour="*/6", minute="0"),
        'args': (),
    }
}
