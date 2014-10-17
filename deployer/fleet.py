from __future__ import absolute_import
from fleet.client.fleet_fabric import Provider
from fleet.deploy.deployer import default_jinja_environment
from conf.appconfig import FLEET_SETTINGS, FLEET_TEMPLATE_SETTINGS

jinja_env = default_jinja_environment(
    token=FLEET_TEMPLATE_SETTINGS['github']['token']
)


def get_fleet_provider():
    return Provider(hosts=FLEET_SETTINGS['host'])
