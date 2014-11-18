import socket
import sys
from conf.celeryconfig import CLUSTER_NAME
from deployer.celery import app

if __name__ == '__main__':
    argv = list(sys.argv) if len(sys.argv) > 1 \
        else [__file__, '--loglevel=info']
    argv.append('-n cluster-deployer-%s@%s' %
                (CLUSTER_NAME, socket.gethostname()))
    app.worker_main(argv=argv)
