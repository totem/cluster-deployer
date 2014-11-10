from datetime import datetime
import traceback
from flask import request
import flask
from deployer.tasks.exceptions import TaskExecutionException


def as_flask_error(error=None, message=None, details=None, traceback=None,
                   status=500, code='INTERNAL', timestamp=None):
    return flask.jsonify({
        'path': request.path,
        'url': request.url,
        'method': request.method,
        'message': message or str(error),
        'details': details,
        'traceback': traceback,
        'status': status,
        'code': code,
        'timestamp': timestamp or datetime.utcnow()
    }), status


def register(app, **kwargs):

    @app.errorhandler(404)
    def page_not_found(error):
        return as_flask_error(error, **{
            'message': 'The given resource:%s is not found on server'
                       % request.path,
            'code': 'NOT_FOUND',
            'status': 404
        })

    @app.errorhandler(TaskExecutionException)
    def task_error(error):
        return as_flask_error(error, **{
            'code': error.code,
            'message': error.message,
            'details': error.details,
            'traceback': error.traceback,
            'status': 500,
        })

    @app.errorhandler(Exception)
    @app.errorhandler(500)
    def internal(error):
        trace = traceback.format_exc()
        try:
            details = error.to_dict()
        except AttributeError:
            details = None
        return as_flask_error(error, **{
            'code': 'INTERNAL',
            'details': details,
            'traceback': trace,
            'status': 500,
        })

    @app.errorhandler(406)
    def not_acceptable(error):
        return as_flask_error(error, **{
            'code': 'NOT_ACCEPTABLE',
            'status': 406
        })

    @app.errorhandler(415)
    def invalid_media_type(error):
        return as_flask_error(error, **{
            'code': 'INVALID_MEDIA_TYPE',
            'status': 415
        })
