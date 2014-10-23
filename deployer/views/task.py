import logging
from celery.result import AsyncResult, ResultBase
import flask
from flask.views import MethodView
import deployer
from deployer.tasks.exceptions import TaskExecutionException

logger = logging.getLogger(__name__)


class TaskApi(MethodView):
    """
    Api for task
    """

    @staticmethod
    def _find_error_task(task):
        if not task or not isinstance(task, ResultBase):
            return

        if isinstance(task, AsyncResult):
            if task.status in ['FAILURE']:
                return task
            else:
                return TaskApi._find_error_task(task.result)
        else:
            return

    @staticmethod
    def _ready(id):
        status = 'READY'
        # DO not remove line below
        # Explanation: https://github.com/celery/celery/issues/2315
        deployer.celery.app.set_current()

        output = deployer.celery.app.AsyncResult(id)
        # print('%r', output.result.backend.database)
        error_task = TaskApi._find_error_task(output)

        if error_task:
            output, status =  \
                error_task.result, error_task.status
            if not isinstance(output, TaskExecutionException):
                output = TaskExecutionException(output, error_task.traceback)
        else:
            while isinstance(output, AsyncResult) and status is 'READY':
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
            flask.abort(404)
        else:
            response = TaskApi._ready(id)
            return flask.jsonify(response)


def register(app):
    app.add_url_rule('/tasks/<string:id>', view_func=TaskApi.as_view('tasks'),
                     methods=['GET'])
