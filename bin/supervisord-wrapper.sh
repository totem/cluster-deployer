#!/bin/bash -lex

cat <<END>> /etc/environment
ETCD_HOST=$ETCD_HOST
ETCD_PORT=$ETCD_PORT
ETCD_TOTEM_BASE=$ETCD_TOTEM_BASE
ETCD_YODA_BASE=$ETCD_YODA_BASE
MONGO_URL=$MONGO_URL
TASK_EXECUTORS=$TASK_EXECUTORS
API_EXECUTORS=$API_EXECUTORS
C_FORCE_ROOT=$C_FORCE_ROOT
SSH_HOST_KEY=$SSH_HOST_KEY
BROKER_URL=$BROKER_URL
SSH_PASSPHRASE=$SSH_PASSPHRASE
GITHUB_TOKEN=$GITHUB_TOKEN
ELASTICSEARCH_HOST=$ELASTICSEARCH_HOST
ELASTICSEARCH_PORT=$ELASTICSEARCH_PORT
FLEET_HOST=$FLEET_HOST
END

envsubst  < /etc/supervisor/conf.d/supervisord.conf.template  > /etc/supervisor/conf.d/supervisord.conf
/usr/local/bin/supervisord -c /etc/supervisor/supervisord.conf
