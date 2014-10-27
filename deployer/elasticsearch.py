from __future__ import absolute_import
from elasticsearch import Elasticsearch
from conf.appconfig import SEARCH_SETTINGS


def get_search_client():
    """
    Creates the elasticsearch client instance use SEARCH_SETTINGS

    :return: Instance of Elasticsearch
    :rtype: elasticsearch.Elasticsearch
    """
    return Elasticsearch(hosts=SEARCH_SETTINGS['host'],
                         port=SEARCH_SETTINGS['port'])
