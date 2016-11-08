"""
Tasks for notification
"""
import json

import time
from future.builtins import (  # noqa
    bytes, dict, int, list, object, range, str,
    ascii, chr, hex, input, next, oct, open,
    pow, round, filter, map, zip)

import requests

from conf.appconfig import LEVEL_FAILED, \
    LEVEL_FAILED_WARN, LEVEL_STARTED, LEVEL_SUCCESS, LEVEL_PENDING, \
    NOTIFICATIONS_DEFAULTS, DEFAULT_HIPCHAT_TOKEN, DEFAULT_GITHUB_TOKEN
from deployer import templatefactory
from deployer.celery import app
from deployer.services.security import decrypt_config
from deployer.tasks import util


@app.task
def notify(obj, ctx=None, level=LEVEL_FAILED,
           notifications=None, security_profile='default'):
    """
    Handles notification or job failure.

    :return: None
    """
    notifications = notifications or NOTIFICATIONS_DEFAULTS

    enabled_notifications = {
        name: notification for name, notification in notifications.items()
        if notification.get('enabled') and level <=
        notification.get('level', LEVEL_FAILED) and
        globals().get('notify_%s' % name)
    }
    for name, notification in enabled_notifications.items():
        globals().get('notify_%s' % name).si(
            obj, ctx, level, notification, security_profile).delay()


@app.task
def notify_hipchat(obj, ctx, level, config, security_profile):
    config = decrypt_config(config, profile=security_profile)
    api_url = config.get('url') or 'https://api.hipchat.com'
    room_url = '{0}/v2/room/{1}/notification'.format(
        api_url, config.get('room'))
    msg = templatefactory.render_template(
        'hipchat.html', notification=util.as_dict(obj), ctx=ctx, level=level)
    headers = {
        'content-type': 'application/json',
        'Authorization': 'Bearer {0}'.format(
            config.get('token', '') or DEFAULT_HIPCHAT_TOKEN)
    }
    data = {
        'message_format': 'html',
        'message': msg[:5000],
        'color': config.get('colors', {}).get(str(level), 'gray'),
        'notify': level <= LEVEL_FAILED_WARN
    }
    requests.post(room_url, data=json.dumps(data),
                  headers=headers).raise_for_status()


@app.task
def notify_slack(obj, ctx, level, config, security_profile):
    config = decrypt_config(config, profile=security_profile)
    url = config.get('url')
    notification = util.as_dict(obj)
    notification['channel'] = config.get('channel')
    notification['date'] = int(time.time())
    msg = templatefactory.render_template(
        'slack.json.jinja', notification=notification, ctx=ctx,
        level=level)
    headers = {
        'content-type': 'application/json',
    }
    if url:
        requests.post(url, data=msg, headers=headers) \
            .raise_for_status()


@app.task
def notify_github(obj, ctx, level, config, security_profile):
    config = decrypt_config(config, profile=security_profile)
    api_url = config.get('url') or 'https://api.github.com'
    git = ctx.get('deployment', {}).get('meta-info', {}).get('git', {})
    owner, repo, commit = git.get('owner'), git.get('repo'), git.get('commit')
    git_type = git.get('type', 'github')
    token = config.get('token') or DEFAULT_GITHUB_TOKEN
    if owner and repo and commit and token and git_type == 'github':
        desc = util.as_dict(obj).get('message', str(obj))
        # Max 140 characters allowed for description
        use_desc = desc[:137] + '...' if len(desc) > 140 else desc

        status_url = '{0}/repos/{1}/{2}/statuses/{3}'.format(
            api_url, owner, repo, commit)
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': 'token {0}'.format(token)
        }
        data = {
            'state': {
                LEVEL_FAILED: 'failure',
                LEVEL_FAILED_WARN: 'failure',
                LEVEL_SUCCESS: 'success',
                LEVEL_STARTED: 'pending',
                LEVEL_PENDING: 'pending'
            }.get(level, 'pending'),
            'description': use_desc,
            'context': ctx.get('cluster', 'local') + '::Deployer'
        }
        requests.post(status_url, data=json.dumps(data),
                      headers=headers).raise_for_status()
    else:
        # Github notification not sent
        pass
