import logging
from celery.result import AsyncResult
import flask
from flask.views import MethodView
import deployer

logger = logging.getLogger(__name__)


class TaskApi(MethodView):
    """
    Api for task
    """

    @staticmethod
    def _ready(id):

        def next_output():
            ret_status = 'READY'
            ret_output = deployer.celery.app.AsyncResult(id)
            ret_traceback = None
            while isinstance(ret_output, AsyncResult) \
                    and ret_status is 'READY':
                ret_output = deployer.celery.app.AsyncResult(ret_output.id)
                if ret_output.ready():
                    if ret_output.failed():
                        ret_status = 'ERROR'
                        ret_traceback = ret_output.traceback
                        try:
                            ret_output = ret_output.result.to_dict() \
                                if ret_output.result else None
                        except AttributeError:
                            ret_output = repr(ret_output.result)
                    else:
                        ret_output = ret_output.result
                else:
                    ret_status = 'PENDING'
                    ret_output = None
                yield ret_output, ret_status, ret_traceback

        for output, status, traceback in next_output():
            pass

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
