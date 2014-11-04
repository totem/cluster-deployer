"""
Module that provides decorators for hypermedia handling and Schema validation
using Json HyperSchema and Json Schema.
"""

import functools
import glob
import json
import os
import traceback
from flask import make_response, request, url_for
import flask
from flask.views import MethodView
from jsonschema import validate, ValidationError, SchemaError
from ordered_set import OrderedSet
from repoze.lru import lru_cache
from werkzeug.exceptions import UnsupportedMediaType, NotAcceptable

SCHEMA_PATH = os.getenv('SCHEMA_PATH', './schemas')
SCHEMA_CACHE_MAX_SIZE = int(os.getenv('SCHEMA_CACHE_MAX_SIZE', '50'))
MIME_JSON = 'application/json'


class HyperMedia:

    def __init__(self, schema_cache_size=SCHEMA_CACHE_MAX_SIZE,
                 schema_path=SCHEMA_PATH):
        self.schema_cache_size = schema_cache_size
        self.register_load_schema = self._load_schema()
        self.get_all_schemas = self._get_all_schemas()

    def _load_schema(self):
        @lru_cache(self.schema_cache_size)
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
        return load_schema

    def _get_all_schemas(self):
        @lru_cache(1)
        def get_all_schemas():
            return [os.path.splitext(os.path.basename(filepath))[0]
                    for filepath in glob.glob('%s/*.json' % self.schema_path)]
        return get_all_schemas

    def consumes(self, type_mappings):
        """
        Wrapper that finds matches the content with one of supported type and
        performs a json schema validation for the type.

        :param type_mappings: Dictionary of (content type, schema name)
        :return: decorated function
        """
        def decorated(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                if request.mimetype not in type_mappings:
                    raise UnsupportedMediaType()
                data = json.loads(request.data)
                schema_name = type_mappings.get(request.mimetype)
                if schema_name:
                    schema = self.load_schema(request.url_root[:-1],
                                              schema_name)
                    validate(data, schema)
                kwargs.setdefault('request_mimetype', request.mimetype)
                kwargs.setdefault('request_data', data)
                return fn(*args, **kwargs)
            return wrapper
        return decorated

    @staticmethod
    def produces(type_mappings, default=MIME_JSON):
        """
        Wrapper that does content negotiation based on accept headers and
        applies hyperschema to the response.
        It passes the negotiated header to the wrapped method. Currently it
        does a very basic negotitation. In future it can be modified to do full
        content negotiation.

        :param type_mappings: Dictionary of (content type, hyperschema name)
        :return: decorated function
        """
        def decorated(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                requested = OrderedSet(request.accept_mimetypes.values())
                defined = type_mappings.keys()
                supported = requested & defined
                if len(requested) == 0 or next(iter(requested)) == '*/*':
                    mimetype = default
                elif len(supported) == 0:
                    raise NotAcceptable()
                else:
                    mimetype = next(iter(supported))
                kwargs.setdefault('accept_mimetype', mimetype)
                resp = make_response(fn(*args, **kwargs))
                hyperschema = type_mappings[mimetype]
                if hyperschema:
                    resp.headers['Link'] = \
                        '<%s#>; rel="describedBy"' % url_for(
                            '.schemas', schema_id=hyperschema, _external=True)
                return resp
            return wrapper
        return decorated

    def register_schema_api(self, flask_app, schema_uri='/schemas'):
        SchemaApi.hypermedia = self
        flask_app.add_url_rule(
            '%s/<string:schema_id>' % schema_uri,
            view_func=SchemaApi.as_view('schemas'),
            methods=['GET'])
        return self

    def register_error_handlers(self, flask_app):
        @flask_app.errorhandler(ValidationError)
        def validation_error(error):
            return _as_flask_error(error, **{
                'code': 'VALIDATION',
                'message': error.message,
                'details': self._get_error_details(error),
                'status': 400,
                })

        @flask_app.errorhandler(SchemaError)
        def schema_error(error):
            return _as_flask_error(error, **{
                'code': 'SCHEMA_ERROR',
                'message': error.message,
                'details': self._get_error_details(error),
                'status': 500,
                'traceback': traceback.format_exc()
            })
        return self

    @staticmethod
    def _as_flask_error(error, message=None, details=None, traceback=None,
                        status=500, code='INTERNAL'):
        return flask.jsonify({
            'path': request.path,
            'url': request.url,
            'method': request.method,
            'message': message or str(error),
            'details': details,
            'traceback': traceback,
            'status': status,
            'code': code
        }), status


    @staticmethod
    def _get_error_details(error):
        return {
            'schema': error.schema,
            'schema-path': '/'.join(error.schema_path)
        }


class SchemaApi(MethodView):
    """
    Root API
    """

    hypermedia = None

    def get(self, schema_id):
        """
        Gets the version for the Deployer API.

        :return: Flask Json Response containing version.
        """
        schema = self.hypermedia.load_schema(request.url_root[:-1], schema_id)
        if not schema:
            return flask.abort(404)
        return flask.jsonify(schema)


def _as_flask_error(error, message=None, details=None, traceback=None,
                   status=500, code='INTERNAL'):
    return flask.jsonify({
        'path': request.path,
        'url': request.url,
        'method': request.method,
        'message': message or str(error),
        'details': details,
        'traceback': traceback,
        'status': status,
        'code': code
    }), status