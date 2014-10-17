from deployer.celery import app


@app.task
def backend_cleanup():
    app.tasks['celery.backend_cleanup']()
