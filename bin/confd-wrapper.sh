#!/bin/bash -le

export ETCD_URL="http://$ETCD_HOST:$ETCD_PORT"
export ETCDCTL="etcdctl --peers $ETCD_URL"


sed -i -e "s|http[:]//172.17.42.1[:]4001|$ETCD_URL|g" -e "s|/totem|$ETCD_TOTEM_BASE|g" /etc/confd/confd.toml

$ETCDCTL ls $ETCD_TOTEM_BASE/ssh  || $ETCDCTL mkdir $ETCD_TOTEM_BASE/ssh
confd