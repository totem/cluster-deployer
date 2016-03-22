from hyperschema.hypermedia import HyperMedia
import deployer
from conf.appconfig import API_PORT
from deployer.services.task_client import TaskClient

__author__ = 'sukrit'

hypermedia = HyperMedia(base_url='http://localhost:{}'.format(API_PORT))
task_client = TaskClient(deployer.celery.app)
