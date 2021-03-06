from conf.appconfig import TASK_SETTINGS
from deployer.celery import app
from deployer.tasks.util import simple_result, TaskNotReadyException


@app.task(bind=True)
def async_wait(self, result,
               default_retry_delay=TASK_SETTINGS['DEFAULT_RETRY_DELAY'],
               max_retries=TASK_SETTINGS['DEFAULT_RETRIES'],
               ret_value=None):
    """
    Performs asynchronous wait for result. It uses retry approach for result
    to be available rather calling get() . This way the trask do not directly
    wait for wach other

    :param result: Result to be evaluated.
    :param default_retry_delay: Delay between retries.
    :param max_retries: Maximum no. of retries to wait for result
    :param ret_value: If None, evaluated result is returned else ret_value is
        returned
    :return: ret_value or evaluated result
    """
    try:
        result = simple_result(result)
    except TaskNotReadyException as exc:
        self.retry(exc=exc,
                   countdown=default_retry_delay,
                   max_retries=max_retries)
    return ret_value or result


@app.task
def ping():
    return 'pong'
