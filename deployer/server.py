from __future__ import absolute_import
from flask import Flask
from deployer.views import root

app = Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True

root.register(app)
