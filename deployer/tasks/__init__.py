from deployer.celery import app
import deployer.tasks.deployment  # noqa


@app.task
def backend_cleanup():
    app.tasks['celery.backend_cleanup']()
