import socket
from celery.exceptions import ChordError
from celery.result import ResultBase, AsyncResult, GroupResult
import deployer
from deployer.tasks.exceptions import TaskExecutionException
from deployer.util import retry

__author__ = 'sukrit'


def check_or_raise_task_exception(result):
    if isinstance(result, GroupResult):
        for result in result.results:
            check_or_raise_task_exception(result)
    elif isinstance(result, AsyncResult) and result.failed():
        if isinstance(result.result, TaskExecutionException):
            raise result.result
        elif isinstance(result.result, ChordError):
            check_or_raise_task_exception(result.parent)
        else:
            raise TaskExecutionException(result.result, result.traceback)


def _check_error(result):
    if not result or not isinstance(result, AsyncResult):
        return
    check_or_raise_task_exception(result)
    _check_error(result.parent)


@retry(10, delay=5, backoff=1, except_on=(IOError, socket.error))
def simple_result(result):
    # DO not remove line below
    # Explanation: https://github.com/celery/celery/issues/2315
    deployer.celery.app.set_current()

    if isinstance(result, GroupResult):
        return simple_result(result.results)
    elif hasattr(result, '__iter__') and not isinstance(result, dict):
        return [simple_result(each_result) for each_result in result]
    elif isinstance(result, ResultBase):
        _check_error(result)
        if result.ready():
            check_or_raise_task_exception(result)
            return simple_result(result.result)
        else:
            raise TaskNotReadyException()
    return result


class TaskNotReadyException(Exception):
    pass
