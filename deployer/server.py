from __future__ import absolute_import
import json
from flask import Flask
import celery
import deployer.celery
from deployer.tasks.deployment import create

app = Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True


@app.route('/')
def hello_world():
    return json.dumps(create.delay({'message': 'Hello World'})\
        .get(propagate=True, timeout=60))