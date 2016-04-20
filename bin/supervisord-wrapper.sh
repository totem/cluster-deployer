#!/bin/sh -e

. /usr/sbin/deployer-env.sh

until $ETCDCTL cluster-health; do
  >&2 echo "Etcdctl cluster not healthy - sleeping"
  sleep 5
done

# Cleanup for local testing
if ls celerybeat* 2>/dev/null; then
  rm celerybeat*
fi

if [ "$DISCOVER_RABBITMQ" == "true" ]; then
  export AMQP_HOST="$($ETCDCTL ls $ETCD_TOTEM_BASE/rabbitmq/nodes | xargs -n 1  $ETCDCTL get | xargs echo -n | tr ' ' ',')"
  until [ ! -z "$AMQP_HOST" ]; do
    >&2 echo "Rabbitmq could not be discovered - sleeping"
    sleep 10
    export AMQP_HOST="$($ETCDCTL ls $ETCD_TOTEM_BASE/rabbitmq/nodes | xargs -n 1  $ETCDCTL get | xargs echo -n | tr ' ' ',')"
  done
fi

if [ "$DISCOVER_MONGO" == "true" ]; then
  export MONGODB_SERVERS="$($ETCDCTL ls $ETCD_TOTEM_BASE/mongo/nodes | xargs -n 1  $ETCDCTL get | xargs echo -n | tr ' ' ',')"
  until [ ! -z "$MONGODB_SERVERS" ]; do
    >&2 echo "Mongo servers could not be discovered - sleeping"
    sleep 10
    export MONGODB_SERVERS="$($ETCDCTL ls $ETCD_TOTEM_BASE/mongo/nodes | xargs -n 1  $ETCDCTL get | xargs echo -n | tr ' ' ',')"
  done
fi

envsubst  < /etc/supervisor/conf.d/supervisord.conf.template  > /etc/supervisor/conf.d/supervisord.conf
/usr/local/bin/supervisord -c /etc/supervisor/supervisord.conf

