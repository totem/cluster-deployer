#!/bin/bash -lex

envsubst  < /etc/supervisor/conf.d/supervisord.conf.template  > /etc/supervisor/conf.d/supervisord.conf
/usr/local/bin/supervisord -c /etc/supervisor/supervisord.conf
