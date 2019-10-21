from celery import Celery

app = Celery('wq2dss',
             broker='amqp://user:password@rabbitmq',
             backend='rpc://',
             include=['wq2dss.tasks'])

app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1
)
