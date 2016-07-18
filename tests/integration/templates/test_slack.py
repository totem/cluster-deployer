import json

from nose.tools import eq_, ok_

from deployer import templatefactory

"""
Tests for Slack Jinja templates
"""


def test_slack_template():
    """
    should render json output for slack API.
    """

    output = templatefactory.render_template(
        'slack.json.jinja',
        ctx={
            "deployment": {
                "meta-info": {
                    "git": {
                        "owner": "test-owner",
                        "repo": "test-repo",
                        "ref": "test-ref",
                        "type": "github",
                    }
                }
            },
            "cluster": "local",
            "operation": "test",

        },
        notification={
            "message": "test message",
            "code": "DEPLOYMENT_FAILED"
        }, level=1)
    slack_dict = json.loads(output)

    eq_(slack_dict.get("username"), "Deployer (local-test)")
    eq_(slack_dict.get("channel"), "#totem")
    ok_(slack_dict.get("text"))
    ok_(slack_dict.get("attachments"))
