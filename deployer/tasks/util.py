from celery.result import ResultBase, AsyncResult, GroupResult

__author__ = 'sukrit'


def check_parent_error(result):
    if not result or not isinstance(result, AsyncResult):
        return
    result.maybe_reraise()
    check_parent_error(result.parent)


def simple_result(result):
    if isinstance(result, GroupResult):
        return simple_result(result.results)
    elif hasattr(result, '__iter__') and not isinstance(result, dict):
        return [simple_result(each_result) for each_result in result]
    elif isinstance(result, ResultBase):
        check_parent_error(result)
        result = AsyncResult(result.id)
        if result.ready():
            if result.failed():
                raise result.result
            else:
                return simple_result(result.result)
        else:
            raise TaskNotReadyException()
    return result


class TaskNotReadyException(Exception):
    pass
