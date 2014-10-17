from celery.result import ResultBase, AsyncResult, GroupResult

__author__ = 'sukrit'


def find_error_task(task):
    if not task or not isinstance(task, ResultBase):
        return None

    if isinstance(task, AsyncResult) and \
            task.status in ['ERROR', 'FAILURE']:
        return task
    else:
        for next_task in task.children or []:
            ret_task = find_error_task(next_task)
            if ret_task:
                return ret_task
    return None


def simple_group_results(results, check_error=True):
    if check_error:
        for result in results:
            error_task = find_error_task(result)
            if error_task:
                raise error_task.result
    return [simple_result(result) for result in results]


def simple_result(task, check_error=True):
    if check_error:
        error_task = find_error_task(task)
        if error_task:
            raise error_task.result
    output = task
    while isinstance(output, ResultBase):
        if output.ready():
            if isinstance(output, AsyncResult):
                output = output.result
            elif isinstance(output, GroupResult):
                output = [simple_result(result) for result in output.results]
        else:
            raise TaskNotReadyException

    if isinstance(output, ResultBase):
        raise NotASimpleResultException

    return output


class TaskNotReadyException(Exception):
    pass


class NotASimpleResultException(Exception):
    pass
