"""
Module that provides decorators for hypermedia handling and Schema validation
using Json HyperSchema and Json Schema.
"""

import functools
from flask import make_response

DEFAULT_SCHEMA_BASE_URI = '/schemas'


class HyperSchema:
    """
    Wrapper to generate Link header using schema_name
    """

    def __init__(self, schema_name, schema_base=DEFAULT_SCHEMA_BASE_URI):
        self.schema_name = schema_name
        self.schema_base = schema_base

    def __call__(self, func):
        """
        :param func: Function to be wrapped
        :return: Wrapped function
        """

        @functools.wraps(func)
        def inner(*args, **kwargs):
            resp = make_response(func(*args, **kwargs))
            resp.headers['Link'] = '<%s/%s#>; rel="describedBy"' % \
                                   (self.schema_base, self.schema_name)
            return resp
        return inner
