#!/bin/bash -le

cat <<END>> /etc/profile.d/cluster-deployer-env.sh
export ETCD_HOST='${ETCD_HOST:-172.17.42.1}'
export ETCD_PORT='${ETCD_PORT:-4001}'
export ETCD_TOTEM_BASE='${ETCD_TOTEM_BASE:-/totem}'
export ETCD_YODA_BASE='${ETCD_YODA_BASE:-/yoda}'
export CELERY_GEVENT_EXECUTORS='${CELERY_GEVENT_EXECUTORS:-1}'
export CELERY_GEVENT_CONCURRENCY='${CELERY_GEVENT_CONCURRENCY:-50}'
export CELERY_PREFORK_CONCURRENCY='${CELERY_PREFORK_CONCURRENCY:-2}'
export API_EXECUTORS='${API_EXECUTORS:-2}'
export C_FORCE_ROOT='${C_FORCE_ROOT:-true}'
export SSH_HOST_KEY='${SSH_HOST_KEY:-/root/.ssh/id_rsa}'
export AMQP_HOST='${AMQP_HOST:-172.17.42.1}'
export AMQP_PORT='${AMQP_PORT:-5672}'
export AMQP_USERNAME='${AMQP_USERNAME:-guest}'
export AMQP_PASSWORD='${AMQP_PASSWORD:-guest}'
export MONGODB_USERNAME='${MONGODB_USERNAME:-}'
export MONGODB_PASSWORD='${MONGODB_PASSWORD:-}'
export MONGODB_HOST='${MONGODB_HOST:-172.17.42.1}'
export MONGODB_PORT='${MONGODB_PORT:-27017}'
export MONGODB_DB='${MONGODB_DB:-totem}'
export BROKER_URL='${BROKER_URL}'
export SSH_PASSPHRASE='${SSH_PASSPHRASE}'
export GITHUB_TOKEN='${GITHUB_TOKEN}'
export FLEET_HOST='${FLEET_HOST:-172.17.42.1}'
export CLUSTER_NAME='${CLUSTER_NAME:-local}'
export TOTEM_ENV='${TOTEM_ENV:-local}'
export QUAY_ORGANIZATION='${QUAY_ORGANIZATION:-totem}'
export QUAY_PREFIX='${QUAY_PREFIX:-totem-}'
export C_FORCE_ROOT=true
export ENCRYPTION_PASSPHRASE='${ENCRYPTION_PASSPHRASE:-changeit}'
export ENCRYPTION_S3_BUCKET='${ENCRYPTION_S3_BUCKET:-not-set}'
export ENCRYPTION_STORE='${ENCRYPTION_PROVIDER:-s3}'
export HIPCHAT_TOKEN='${HIPCHAT_TOKEN}'
export HIPCHAT_ENABLED='${HIPCHAT_ENABLED:-false}'
export HIPCHAT_TOKEN='${HIPCHAT_TOKEN}'
export HIPCHAT_ROOM='${HIPCHAT_ROOM:-not-set}'
export GITHUB_NOTIFICATION_ENABLED='${GITHUB_NOTIFICATION_ENABLED:-false}'
export BASE_URL='${BASE_URL:-http://172.17.42.1:9000}'
export LOG_IDENTIFIER='${LOG_IDENTIFIER:-cluster-deployer}'
END


/bin/bash -le -c " envsubst  < /etc/supervisor/conf.d/supervisord.conf.template  > /etc/supervisor/conf.d/supervisord.conf; \
                    /usr/local/bin/supervisord -c /etc/supervisor/supervisord.conf"


