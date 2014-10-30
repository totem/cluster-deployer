from nose.tools import eq_
from deployer.server import app


class TestHyperSchema:
    """
    Tests hperschema
    """

    def setup(self):
        self.client = app.test_client()

    def test_root_hyperschema(self):
        """
        Should set the Link header for root endpoint.
        """

        # When I invoke the root endpoint
        resp = self.client.get('/')

        # The Link header is set for the root endpoint
        eq_(resp.headers['Link'], '</schemas/root-v1#>; rel="describedBy"')
