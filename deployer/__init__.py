import logging
from conf.appconfig import LOG_FORMAT, LOG_DATE, LOG_ROOT_LEVEL

__author__ = 'sukrit'

logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE, level=LOG_ROOT_LEVEL)
