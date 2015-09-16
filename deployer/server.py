from __future__ import absolute_import
from flask import Flask
from flask.ext.cors import CORS
from conf.appconfig import CORS_SETTINGS, CORS_ENABLED
import deployer
from deployer.views import root, application, task, health, error, hypermedia

app = Flask(__name__)

# app.config['PROPAGATE_EXCEPTIONS'] = True
hypermedia.register_schema_api(app).register_error_handlers(app)

if CORS_ENABLED:
    CORS(app, resources={'/*': CORS_SETTINGS})

for module in [root, application, task, health, error]:
    module.register(app)


@app.before_request
def set_current_app():
    # DO not remove line below
    # Explanation: https://github.com/celery/celery/issues/2315
    deployer.celery.app.set_current()
