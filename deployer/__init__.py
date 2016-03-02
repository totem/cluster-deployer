from __future__ import absolute_import
import deployer.logger
from celery.signals import setup_logging


__version__ = '0.4.5'
__author__ = 'sukrit'

deployer.logger.init_logging()
setup_logging.connect(deployer.logger.init_celery_logging)
