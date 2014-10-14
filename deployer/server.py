from __future__ import absolute_import
from flask import Flask
from deployer.views import root, application, task

app = Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True

for module in [root, application, task]:
    module.register(app)
