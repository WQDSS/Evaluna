from celery import Celery

app = Celery('wqdss',
             broker='amqp://user:password@rabbitmq',
             backend='rpc://',
             include=['wqdss.tasks'])

app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1
)
