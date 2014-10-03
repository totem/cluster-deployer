__author__ = 'sukrit'

from nose.tools import eq_

from deployer.tasks.deployment import create


def test_create():
    """Should create a new deployment."""
    response = create.delay('Hello').get(propogate=True)
    eq_(response, 'Hello')
    pass
