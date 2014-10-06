"""
General utility methods
"""
import copy


def dict_merge(dict1, dict2):
    """
    Performs nested merge of 2 dictionaries. It takes only those values from
    second dictionary , whose keys do not exist in dictionary 1.

    :param dict1: Base dictionary
    :type dict1: dict
    :param dict2: Dictionary containing defaults
    :type dict2: dict
    :return: merged dictionary
    """
    dict1_copy = copy.deepcopy(dict1)
    dict2_copy = copy.deepcopy(dict2)

    def merge(source, defaults):
        # Nested merge requires both source and defaults to be dictionary
        if isinstance(source, dict) and isinstance(defaults, dict):
            for key, value in defaults.iteritems():
                if key not in source:
                    # Key not found in source : Use the defaults
                    source[key] = value
                else:
                    # Key found in source : Recursive merge
                    source[key] = merge(source[key], value)
        return source

    return merge(dict1_copy, dict2_copy)