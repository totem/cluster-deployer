from __future__ import absolute_import
from flask import Flask
import deployer
from deployer.views import root, application, task, health, schema, error

app = Flask(__name__)
# app.config['PROPAGATE_EXCEPTIONS'] = True

for module in [root, application, task, health, schema, error]:
    module.register(app)

@app.before_request
def set_current_app():
    deployer.celery.app.set_current()

