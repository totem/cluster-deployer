#!/bin/sh -e

. /usr/sbin/deployer-env.sh

cp /root/.ssh/id_rsa.encrypted /root/.ssh/id_rsa.new
ssh-keygen -P "$SSH_PASSPHRASE" -N '' -p -f /root/.ssh/id_rsa.new
mv /root/.ssh/id_rsa.new /root/.ssh/id_rsa