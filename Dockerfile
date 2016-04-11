FROM python:2.7-slim
ENV DEBIAN_FRONTEND noninteractive
ENV ETCDCTL_VERSION v2.3.1
ENV CONFD_VERSION 0.12.0-alpha3

# Native packages, python global deps, gettext, supervisor, dumb-init, etcd
RUN apt-get update --fix-missing \
  && apt-get install -y \
     gettext \
     wget \
     curl \
     openssl \

  # Upgrade pip
  && pip install --upgrade pip \

  # Confd
  && curl -L https://github.com/kelseyhightower/confd/releases/download/v$CONFD_VERSION/confd-${CONFD_VERSION}-linux-amd64 -o /usr/local/bin/confd \
  && chmod 555 /usr/local/bin/confd \

  # Etcd
  && curl -L https://github.com/coreos/etcd/releases/download/$ETCDCTL_VERSION/etcd-$ETCDCTL_VERSION-linux-amd64.tar.gz -o /tmp/etcd-$ETCDCTL_VERSION-linux-amd64.tar.gz \
  && cd /tmp && gzip -dc etcd-$ETCDCTL_VERSION-linux-amd64.tar.gz | tar -xof -  \
  && cp -f /tmp/etcd-$ETCDCTL_VERSION-linux-amd64/etcdctl /usr/local/bin \

  # Python Global Deps
  && pip install supervisor==3.2.3 supervisor-stdout \

  # Supervisor Directories
  && mkdir -p /var/log/supervisor  \
  && mkdir -p /etc/supervisor/conf.d  \
  && ln -sf /etc/supervisor/supervisord.conf /etc/supervisord.conf \

  # Dumb Init
  && wget -O /usr/bin/dumb-init https://github.com/Yelp/dumb-init/releases/download/v1.0.0/dumb-init_1.0.0_amd64 \
  && chmod +x /usr/bin/dumb-init \

  # SSH Key for fleet
  && mkdir /root/.ssh  \
  && chmod  500 /root/.ssh  \
  && chown -R root:root /root/.ssh \

  # Cleanup
  && apt-get clean \
  && rm -rf /var/cache/apt/archives/* /var/lib/apt/lists/* /tmp/* /root/.cache/*

# App dependencies
ADD requirements.txt /opt/cluster-deployer/requirements.txt
RUN apt-get update --fix-missing \
  # Install dev packages for build (Remove them in the end)
  && apt-get install -y gcc libffi-dev libssl-dev \
  && pip install -r /opt/cluster-deployer/requirements.txt \
  # Cleanup
  && apt-get -y remove gcc libffi-dev libssl-dev \
  && apt-get clean \
  && rm -rf /var/cache/apt/archives/* /var/lib/apt/lists/* /tmp/* /root/.cache/*


# Supervisor Scripts
ADD bin/supervisord-wrapper.sh /usr/sbin/supervisord-wrapper.sh
RUN chmod +x /usr/sbin/supervisord-wrapper.sh

# Confd Defaults
ADD bin/confd-wrapper.sh /usr/sbin/confd-wrapper.sh
RUN chmod +x /usr/sbin/confd-wrapper.sh

# SSH Keys
ADD bin/decrypt-ssh-keys.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/decrypt-ssh-keys.sh

# Etc Config
ADD etc /etc

ADD . /opt/cluster-deployer

EXPOSE 9000

WORKDIR /opt/cluster-deployer

CMD ["/usr/bin/dumb-init", "/usr/sbin/supervisord-wrapper.sh"]