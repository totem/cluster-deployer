from deployer import hypermedia
import deployer
from deployer.services.task_client import TaskClient

__author__ = 'sukrit'

hypermedia = hypermedia.HyperMedia()
task_client = TaskClient(deployer.celery.app)
