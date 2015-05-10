from nose.tools import eq_, raises
from deployer import util

from deployer.util import dict_merge
from tests.helper import dict_compare


__author__ = 'sukrit'

"""
Test for :mod: `deployer.util`
"""


def test_dict_merge():
    """
    should merge the two dictionaries
    """

    # Given: Dict obj that needs to be merged
    dict1 = {
        'key1': 'value1',
        'key2': {
            'key2.1': 'value2.1a'
        }
    }

    dict2 = {
        'key3': 'value3',
        'key2': {
            'key2.1': 'value2.1b',
            'key2.2': 'value2.2a'
        }
    }

    # When: I merge the two dictionaries
    merged_dict = dict_merge(dict1, dict2)

    # Then: Merged dictionary is returned
    eq_(merged_dict, {
        'key1': 'value1',
        'key2': {
            'key2.1': 'value2.1a',
            'key2.2': 'value2.2a'
        },
        'key3': 'value3',
    })


def test_to_milliseconds_for_valid_formats():
    """
    Should convert given set of intervals to milliseconds
    """

    # Given: Intervals that needs to be converted
    intervals = ['5s', '2h', '2m', '3ms', '2d', '3w']

    # When: I convert given intervals to milliseconds
    converted = [util.to_milliseconds(interval) for interval in intervals]

    # Then: Expected millisends for each interval is returned
    eq_(converted, [5000, 7200000, 120000, 3, 172800000, 1814400000])


@raises(util.InvalidInterval)
def test_to_milliseconds_for_invalid_format():
    """
    Should raise exception when interval format is invalid
    """

    # When: I convert invalid interval to ms
    util.to_milliseconds('5invalid')

    # Then: InvalidInterval exception is thrown


def test_dict_representation_for_invalid_interval():
    """
    Should return dict representation
    """

    # When: I get dict representation for InvalidInterval exception
    output = util.InvalidInterval('invalid').to_dict()

    # Then: Expected representation is returned
    dict_compare(output, {
        'code': 'INVALID_INTERVAL',
        'message': 'Invalid interval specified:invalid. Interval should '
                   'match format: ^\\s*(\d+)(ms|h|m|s|d|w)\\s*$',
        'details': {
            'interval': 'invalid'
        }
    })


def test_str_representation_for_invalid_interval():
    """
    Should return str representation for InvalidInterval exception
    """

    # When: I get str representation for InvalidInterval exception
    output = str(util.InvalidInterval('invalid'))

    # Then: Expected representation is returned
    eq_(output, 'Invalid interval specified:invalid. Interval should '
                'match format: ^\\s*(\d+)(ms|h|m|s|d|w)\\s*$')
