FROM totem/python-base:2.7-trusty

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update
RUN apt-get install -y openssh-server openssh-client libffi-dev gettext nano

##SSH Server (To troubleshoot issues with discover)
RUN mkdir /var/run/sshd
ADD .root/.ssh /root/.ssh
RUN chmod -R 400 /root/.ssh/* && chmod  500 /root/.ssh & chown -R root:root /root/.ssh

#Syslog
RUN echo '$PreserveFQDN on' | cat - /etc/rsyslog.conf > /tmp/rsyslog.conf && sudo mv /tmp/rsyslog.conf /etc/rsyslog.conf
RUN sed -i 's~^#\$ModLoad immark\(.*\)$~$ModLoad immark \1~' /etc/rsyslog.conf

#Confd
ENV CONFD_VERSION 0.6.2
RUN curl -L https://github.com/kelseyhightower/confd/releases/download/v$CONFD_VERSION/confd-${CONFD_VERSION}-linux-amd64 -o /usr/local/bin/confd
RUN chmod 555 /usr/local/bin/confd

#Etcdctl
RUN echo "Etcd force...."
ENV ETCDCTL_VERSION v0.4.6
RUN curl -L https://github.com/coreos/etcd/releases/download/$ETCDCTL_VERSION/etcd-$ETCDCTL_VERSION-linux-amd64.tar.gz -o /tmp/etcd-$ETCDCTL_VERSION-linux-amd64.tar.gz
RUN cd /tmp && gzip -dc etcd-$ETCDCTL_VERSION-linux-amd64.tar.gz | tar -xof -
RUN cp -f /tmp/etcd-$ETCDCTL_VERSION-linux-amd64/etcdctl /usr/local/bin
RUN rm -rf /tmp/etcd-$ETCDCTL_VERSION-linux-amd64.tar.gz

ADD requirements.txt /opt/requirements.txt
RUN pip install -r /opt/requirements.txt

#Supervisor Config
RUN mkdir -p /var/log/supervisor
ADD bin/supervisord-wrapper.sh /usr/sbin/supervisord-wrapper.sh
RUN chmod 550 /usr/sbin/supervisord-wrapper.sh

#Confd Defaults
ADD bin/confd-wrapper.sh /usr/sbin/confd-wrapper.sh
RUN chmod 550 /usr/sbin/confd-wrapper.sh

#Etc Config
ADD etc /etc

ADD . /opt/cluster-deployer
RUN pip install -r /opt/cluster-deployer/requirements.txt

ENV ETCD_URL 172.17.42.1:4001
ENV ETCD_PROXY_BASE /totem
ENV MONGO_URL mongodb://172.17.42.1:27017/totem_deployer
ENV TASK_EXECUTORS 2
ENV API_EXECUTORS 2
ENV C_FORCE_ROOT true

EXPOSE 9000 5555 22

WORKDIR /opt/cluster-deployer

ENTRYPOINT ["/usr/sbin/supervisord-wrapper.sh"]