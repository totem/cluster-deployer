import sys
from deployer.celery import app

if __name__ == '__main__':
    argv = list(sys.argv) if len(sys.argv) > 1 \
        else ['celery', '--loglevel=info']
    argv += ['beat']
    app.start(argv=argv)
