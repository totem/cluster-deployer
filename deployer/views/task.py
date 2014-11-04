import logging
from celery.result import AsyncResult, ResultBase
import flask
from flask.views import MethodView
from conf.appconfig import TASK_SETTINGS
import deployer
from deployer.tasks.exceptions import TaskExecutionException

logger = logging.getLogger(__name__)

from flask import request


class TaskApi(MethodView):
    """
    Api for task
    """

    @staticmethod
    def _find_error_task(task, wait=False,
                         timeout=TASK_SETTINGS['DEFAULT_GET_TIMEOUT']):
        if not task or not isinstance(task, ResultBase):
            return

        if isinstance(task, AsyncResult):
            if not task.ready() and wait:
                task.get(propagate=False, timeout=timeout)
            if task.failed():
                return task
            elif task.status in ['PENDING'] and task.parent:
                while task.parent:
                    if task.parent.failed():
                        return task.parent
                    else:
                        task = task.parent
            else:
                return TaskApi._find_error_task(task.result)
        else:
            return

    @staticmethod
    def _ready(id, wait=False, timeout=TASK_SETTINGS['DEFAULT_GET_TIMEOUT']):
        status = 'READY'
        # DO not remove line below
        # Explanation: https://github.com/celery/celery/issues/2315
        deployer.celery.app.set_current()

        output = deployer.celery.app.AsyncResult(id)
        # print('%r', output.result.backend.database)
        error_task = TaskApi._find_error_task(output, wait=wait,
                                              timeout=timeout)

        if error_task:
            output, status =  \
                error_task.result, error_task.status
            if not isinstance(output, TaskExecutionException):
                output = TaskExecutionException(output, error_task.traceback)
        else:
            while isinstance(output, AsyncResult) and status is 'READY':
                if wait:
                    output.get(timeout=timeout, propagate=False)
                if output.ready():
                    output = output.result
                else:
                    status = 'PENDING'
                    output = None
        if output:
            try:
                output = output.to_dict()
            except AttributeError:
                if not isinstance(output, dict)\
                        and not isinstance(output, list):
                    output = str(output)

        return {
            'status': status,
            'output': output
        }

    def get(self, id=None):
        if not id:
            return flask.abort(404)
        else:
            wait = request.args.get('wait', 'false').strip().lower()
            wait = True if wait in {'true', 'y', 'yes', '1'} else False
            timeout = int(request.args.get(
                'timeout', TASK_SETTINGS['DEFAULT_GET_TIMEOUT']))
            response = TaskApi._ready(id, wait=wait, timeout=timeout)
            return flask.jsonify(response)


def register(app, **kwargs):
    app.add_url_rule('/tasks/<string:id>', view_func=TaskApi.as_view('tasks'),
                     methods=['GET'])
