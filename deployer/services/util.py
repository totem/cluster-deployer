from conf.appconfig import CLUSTER_NAME, BASE_URL

__author__ = 'sukrit'


def massage_config(config):
    """
    massages config for notification/indexing.
    1. Removes encrypted parameters from indexing.
    2. Extracts raw parameter for value types.

    :param config: dictionary that needs to be massaged
    :type config: dict
    :return: massaged config
    :rtype: dict
    """

    if hasattr(config, 'items'):
        if 'value' in config:

            if config.get('encrypted', False):
                return ''
            else:
                return str(config.get('value'))
        else:
            return {
                k: massage_config(v) for k, v in config.items()
            }
    elif isinstance(config, (list, set, tuple)):
        return [massage_config(v) for v in config]
    else:
        return config


def create_notify_ctx(deployment, operation=None):
    """
    Creates context to be used for notification (hipchat/github)

    :param meta_info
    :return: Dictionary representing notification context.
    """
    return {
        'deployment': massage_config(deployment),
        'cluster': CLUSTER_NAME,
        'operation': operation,
        'deployer': {
            'url': BASE_URL
        }
    }
