"""
General utility methods
"""
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
import errno
from functools import wraps
import os
import re
from future.builtins import (  # noqa
    bytes, dict, int, list, object, range, str,
    ascii, chr, hex, input, next, oct, open,
    pow, round, super,
    filter, map, zip)

import copy
import signal
import time
import math

INTERVAL_FORMAT = '^\\s*(\d+)(ms|h|m|s|d|w)\\s*$'


def dict_merge(*dictionaries):
    """
    Performs nested merge of multiple dictionaries. The values from
    dictionaries appearing first takes precendence

    :param dictionaries: List of dictionaries that needs to be merged.
    :return: merged dictionary
    :rtype
    """

    merged_dict = {}

    def merge(source, defaults):
        source = copy.deepcopy(source)
        # Nested merge requires both source and defaults to be dictionary
        if isinstance(source, dict) and isinstance(defaults, dict):
            for key, value in defaults.items():
                if key not in source:
                    # Key not found in source : Use the defaults
                    source[key] = value
                else:
                    # Key found in source : Recursive merge
                    source[key] = merge(source[key], value)
        return source

    for merge_with in dictionaries:
        merged_dict = merge(merged_dict, copy.deepcopy(merge_with or {}))

    return merged_dict


class TimeoutError(Exception):
    """
    Error corresponding to timeout of a function use with @timeout annotation.
    """
    pass


def timeout(seconds=10, error_message=os.strerror(errno.ETIME)):
    """
    Decorator that applies timeout for a dunction

    :param seconds: Timeout in seconds. Defaults to 10s.
    :param error_message: Error message corresponding to timeout.
    :return: decorated function
    """
    def decorator(func):
        def _handle_timeout(signum, frame):
            raise TimeoutError(error_message)

        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                signal.signal(signal.SIGALRM, _handle_timeout)
                signal_disabled = False
            except ValueError:
                # Possibly running in debug mode. Timeouts will be ignored
                signal_disabled = True
                pass

            if not signal_disabled:
                signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                if not signal_disabled:
                    signal.alarm(0)
            return result

        return wrapper
    return decorator


def function_retry(tries, delay, backoff, except_on, fn, *args, **kwargs):
    mtries, mdelay = tries, delay  # make mutable

    while True:
        try:
            return fn(*args, **kwargs)
        except except_on:
            pass

        mtries -= 1         # consume an attempt
        if mtries > 0:
            time.sleep(mdelay)  # wait...
            mdelay *= backoff   # make future wait longer

    # Re-raise last exception
    raise


# Retry decorator with backoff
def retry(tries, delay=3, backoff=2, except_on=(Exception, )):
    """Retries a function or method until it returns True.
    delay sets the initial delay in seconds, and backoff sets the factor by
    which the delay should lengthen after each failure.
    tries must be at least 0, and delay greater than 0."""

    tries = math.floor(tries)

    def decorator(f):
        def f_retry(*args, **kwargs):
            return function_retry(
                tries, delay, backoff, except_on, f, *args, **kwargs)
        return f_retry  # true decorator -> decorated function
    return decorator    # @retry(arg[, ...]) -> true decorator


def to_milliseconds(interval):
    """
    Converts string interval to milliseoncds

    :param interval: Time interval represented in string format. (.e.g: 5s)
    :type interval: str
    :return: Interval in milliseconds
    :rtype: long
    """

    match = re.search(INTERVAL_FORMAT, interval)
    if match and len(match.groups()) == 2:
        # Suffix can be 'h' , 'm', 's' or 'ms'
        suffix = match.group(2)
        prefix = int(match.group(1))
        converter = {
            's': lambda use_prefix: use_prefix * 1000,
            'm': lambda use_prefix: use_prefix * 60 * 1000,
            'h': lambda use_prefix: use_prefix * 60 * 60 * 1000,
            'd': lambda use_prefix: use_prefix * 24 * 60 * 60 * 1000,
            'w': lambda use_prefix: use_prefix * 07 * 24 * 60 * 60 * 1000,
        }.get(suffix, lambda use_prefix: use_prefix)
        return converter(prefix)
    else:
        # Invalid interval. Raise exception.
        raise InvalidInterval(interval)


class InvalidInterval(Exception):
    """
    Exception corresponding to invalid time interval.
    """

    def __init__(self, interval):
        """
        :param interval: Invalid interval
        :type interval: str
        """
        self.message = 'Invalid interval specified:{0}. Interval should ' \
                       'match format: {1}'.format(interval, INTERVAL_FORMAT)
        self.interval = interval
        super(InvalidInterval, self).__init__(interval)

    def to_dict(self):
        return {
            'code': 'INVALID_INTERVAL',
            'message': self.message,
            'details': {
                'interval': self.interval
            }
        }

    def __str__(self):
        return self.message
