from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from conf.appconfig import CLUSTER_NAME, BASE_URL

from deployer.services.util import massage_config, create_notify_ctx
from tests.helper import dict_compare


def test_massage_config():
    """
    Should massage configuration as required by search.
    """

    # Given: Configuration that needs to be massaged.
    config = {
        'key1': 'value1',
        'key2': {
            'value': 'value2',
            'encrypted': True
        },
        'key3': [
            {
                'key3.1': {
                    'value': 'value3.1'
                }
            }
        ]
    }

    # When: I massage the config
    result = massage_config(config)

    # Then: Config gets massaged as expected
    dict_compare(result, {
        'key1': 'value1',
        'key2': '',
        'key3': [
            {
                'key3.1': 'value3.1'
            }
        ]
    })


def test_create_notify_ctx():
    """
    Should return notification context for a given deployment
    """

    # Given: Existing deployment
    deployment = {
        "key": "value"
    }

    # When: I create notification context for given deployment
    ctx = create_notify_ctx(deployment, operation='mockop')

    # Then: Expected context is returned
    dict_compare(ctx, {
        'deployment': deployment,
        'cluster': CLUSTER_NAME,
        'operation': 'mockop',
        'deployer': {
            'url': BASE_URL
        }
    })
