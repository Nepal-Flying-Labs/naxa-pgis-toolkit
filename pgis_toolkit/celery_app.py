from __future__ import absolute_import, unicode_literals

import os

from celery import Celery, shared_task

from config.settings.base import env

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'config.settings.{env("BUILD_ENV")}')


app = Celery('pgis_toolkit')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))


'''Detect whether Celery is available and running'''
def get_celery_worker_status():
    try:
        insp = app.control.inspect()
        nodes = insp.stats()
        if not nodes:
            return "error: celery is not running"
            # raise Exception("celery is not running.")
        return "working"
        # logger.error("celery workers are: {}".format(nodes))
        # return nodes
    except Exception as e:
        return "error: celery is not running"
