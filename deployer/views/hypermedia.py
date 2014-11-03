"""
Module that provides decorators for hypermedia handling and Schema validation
using Json HyperSchema and Json Schema.
"""

import functools
import glob
import json
import os
from flask import make_response, request
import flask
from jsonschema import validate, ValidationError, SchemaError
from repoze.lru import lru_cache

DEFAULT_SCHEMA_BASE_URI = '/schemas'
SCHEMA_PATH = './schemas'
SCHEMA_CACHE_MAX_SIZE = 50


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


class ValidateSchema:
    """
    Wrapper to validate Schema for request
    """

    def __init__(self, schema_name, data_field='data'):
        self.schema_name = schema_name
        self.data_field = data_field

    @staticmethod
    def get_error_details(error):
        return {
            'schema': error.schema,
            'schema-path': '/'.join(error.schema_path)
        }

    def __call__(self, func):
        """
        :param func: Function to be wrapped
        :return: Wrapped function
        """

        @functools.wraps(func)
        def inner(*args, **kwargs):
            schema = load_schema(request.url_root[:-1], self.schema_name)
            data = json.loads(request.data)
            try:
                validate(data, schema)
            except ValidationError as error:
                return flask.jsonify({
                    'code': 'VALIDATION',
                    'message': error.message,
                    'details': ValidateSchema.get_error_details(error)
                }), 400
            except SchemaError as error:
                return flask.jsonify({
                    'code': 'SCHEMA_ERROR',
                    'message': error.message,
                    'details': ValidateSchema.get_error_details(error)
                }), 500
            kwargs.setdefault(self.data_field, data)
            resp = make_response(func(*args, **kwargs))
            return resp
        return inner


@lru_cache(SCHEMA_CACHE_MAX_SIZE)
def load_schema(base_url, schema_name):
    """
    Helper function that loads given schema

    :param schema_name:
    :return:
    """
    fname = '%s/%s.json' % (SCHEMA_PATH, schema_name)
    if not os.path.isfile(fname):
        return None
    with open('%s/%s.json' % (SCHEMA_PATH, schema_name)) as file:
        data = file.read().replace('${base_url}', base_url)
        return json.loads(data)


@lru_cache(1)
def get_all_schemas():
    return [os.path.splitext(os.path.basename(filepath))[0] for filepath in
            glob.glob('%s/*.json' % SCHEMA_PATH)]
