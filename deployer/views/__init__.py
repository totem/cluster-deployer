from hyperschema.hypermedia import HyperMedia
import deployer
from deployer.services.task_client import TaskClient

__author__ = 'sukrit'

hypermedia = HyperMedia()
task_client = TaskClient(deployer.celery.app)
