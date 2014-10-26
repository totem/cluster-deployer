from datetime import timedelta
import os
from ast import literal_eval

from celery.schedules import crontab


MONGO_URL = os.getenv('MONGO_URL',
                      'mongodb://localhost:27017/cluster-deployer')
CLUSTER_NAME = os.getenv('CLUSTER_NAME', 'local')
MONGO_RESULTS_DB = os.getenv('MONGO_RESULTS_DB') or os.path.basename(MONGO_URL)


BROKER_URL = os.getenv('BROKER_URL', 'amqp://guest:guest@localhost:5672/')
CELERY_RESULT_BACKEND = MONGO_URL
CELERY_IMPORTS = ('deployer.tasks', 'deployer.tasks.deployment',
                  'deployer.tasks.common', 'deployer.tasks.proxy',
                  'celery.task')
CELERY_MONGODB_BACKEND_SETTINGS = {
    'database': MONGO_RESULTS_DB,
    'taskmeta_collection': os.getenv('MONGO_RESULTS_COLLECTION') or
    'celery_taskmeta_%s' % CLUSTER_NAME
}
CELERY_ACCEPT_CONTENT = ['json', 'pickle']
CELERY_TASK_SERIALIZER = 'pickle'
CELERY_RESULT_SERIALIZER = 'pickle'
CELERY_ALWAYS_EAGER = literal_eval(os.getenv('CELERY_ALWAYS_EAGER', 'False'))
CELERYD_CONCURRENCY = int(os.getenv('CELERYD_CONCURRENCY', '50'))
CELERY_CHORD_PROPAGATES = True

CELERY_STORE_ERRORS_EVEN_IF_IGNORED = True
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
CELERY_IGNORE_RESULT = False
CELERYD_TASK_SOFT_TIME_LIMIT = 300
CELERYD_TASK_TIME_LIMIT = 330
CELERY_SEND_TASK_SENT_EVENT = True
CELERY_TASK_RESULT_EXPIRES = timedelta(days=7)

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
