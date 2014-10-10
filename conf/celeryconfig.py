from datetime import timedelta
import os
from ast import literal_eval

from celery.schedules import crontab


MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017/cluster-deployer')

BROKER_URL = MONGO_URL

CELERY_RESULT_BACKEND = MONGO_URL
CELERY_IMPORTS = ('deployer.tasks', 'celery.task')
CELERY_MONGODB_BACKEND_SETTINGS = {
    'database': os.getenv('MONGO_RESULTS_DB') or os.path.basename(MONGO_URL),
}
CELERY_ACCEPT_CONTENT = ['json', 'pickle']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'pickle'
CELERY_ALWAYS_EAGER = literal_eval(os.getenv('CELERY_ALWAYS_EAGER', 'False'))
CELERYD_CONCURRENCY = 50

CELERY_STORE_ERRORS_EVEN_IF_IGNORED = True
CELERYD_TASK_SOFT_TIME_LIMIT = 300
CELERYD_TASK_TIME_LIMIT = 330
CELERY_SEND_TASK_SENT_EVENT = True
CELERY_TASK_RESULT_EXPIRES = timedelta(days=7)

CELERY_TIMEZONE = 'UTC'

CELERYBEAT_SCHEDULE = {
    'celery.task.backend_cleanup': {
        'task': 'deployer.tasks.backend_cleanup',
        'schedule': crontab(hour="*/6", minute="0"),
        'args': (),
    }
}

CELERY_CHORD_PROPAGATES = True
