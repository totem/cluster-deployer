import logging
from celery.result import AsyncResult, ResultBase
import flask
from flask.views import MethodView
import deployer

logger = logging.getLogger(__name__)


class TaskApi(MethodView):
    """
    Api for task
    """

    @staticmethod
    def _find_error_task(task):
        if not task or not isinstance(task, ResultBase):
            return None

        if isinstance(task, AsyncResult) and \
                task.status in ['ERROR', 'FAILURE']:
            return task
        else:
            for next_task in task.children or []:
                ret_task = TaskApi._find_error_task(next_task)
                if ret_task:
                    return ret_task
        return None

    @staticmethod
    def _ready(id):

        status = 'READY'
        output = deployer.celery.app.AsyncResult(id)
        traceback = None
        error_task = TaskApi._find_error_task(output)

        if error_task:
            output, status, traceback =  \
                error_task.result, error_task.status, error_task.traceback

        else:
            while isinstance(output, AsyncResult) and status is 'READY':
                output = deployer.celery.app.AsyncResult(output.id)
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
            'output': output,
            'traceback': traceback
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
