from celery import Celery

app = Celery('wq2dss',
             broker='amqp://user:password@rabbitmq',
             backend='rpc://',
             include=['wq2dss.tasks'])
