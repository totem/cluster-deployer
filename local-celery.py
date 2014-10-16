import sys
from deployer.celery import app

if __name__ == '__main__':
    argv = sys.argv if len(sys.argv) > 1 else [__file__, '--loglevel=info']
    app.conf.CELERYD_CONCURRENCY = 2
    app.worker_main(argv=argv)
