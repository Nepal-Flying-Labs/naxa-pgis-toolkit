from celery.schedules import crontab
from geo.Geoserver import Geoserver

from .base import *  # noqa
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = True
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="4kB9ZhkXY3FNuQfd4kNEAX5AeF6sCzg9nFfWmwIu9oBAepjQrBEt3VpDBjJQh60k",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
# ALLOWED_HOSTS = ["localhost", "0.0.0.0", "127.0.0.1"]
ALLOWED_HOSTS = ["*"]
# CACHES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#caches
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "",
    }
}

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
# EMAIL_BACKEND = env(
#     "DJANGO_EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
# )

# django-debug-toolbar
# ------------------------------------------------------------------------------
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#prerequisites
INSTALLED_APPS += ["debug_toolbar"]  # noqa F405
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#middleware
MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]  # noqa F405
# https://django-debug-toolbar.readthedocs.io/en/latest/configuration.html#debug-toolbar-config
DEBUG_TOOLBAR_CONFIG = {
    # 'SHOW_TOOLBAR_CALLBACK': lambda r: False,  # disables it
    "DISABLE_PANELS": ["debug_toolbar.panels.profiling.ProfilingPanel", "debug_toolbar.panels.redirects.RedirectsPanel"],
    "SHOW_TEMPLATE_CONTEXT": True,
    # "SKIP_TEMPLATE_PREFIXES": ['django/forms/widgets/', 'admin/widgets/', 'admin/change_form.html']
}
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#internal-ips
INTERNAL_IPS = ["127.0.0.1", "10.0.2.2"]
if env("USE_DOCKER") == "yes":
    import socket

    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS += [".".join(ip.split(".")[:-1] + ["1"]) for ip in ips]

# django-extensions
# ------------------------------------------------------------------------------
# https://django-extensions.readthedocs.io/en/latest/installation_instructions.html#configuration
INSTALLED_APPS += ["django_extensions"]  # noqa F405

# Your stuff...
# ------------------------------------------------------------------------------

# geoserver
geoserver = Geoserver(env("GEOSERVER_ADDRESS", default='http://localhost:8080/geoserver'),
                      username=env("GEOSERVER_USERNAME", default='admin'),
                      password=env("GEOSERVER_PASSWORD", default='geoserver'))
CELERY_IMPORTS = ['pgis_toolkit.maps.tasks', 'pgis_toolkit.users.tasks']
CELERY_RESULT_BACKEND = 'django-db'
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TIMEZONE = 'CET'

CELERY_TASK_ROUTES = {
    # 'core.tasks.add': {'queue': 'pccims'},
    'pgis_toolkit.users.tasks.check_token_expiration': {'queue': 'default'},
}

CELERY_BEAT_SCHEDULE = {
    'check_token_expiration': {
        'task': 'pgis_toolkit.users.tasks.check_token_expiration',
        'schedule': crontab(minute=0, hour=0),  # Execute daily at midnight.
        'options': {'queue': 'default'}
    },
}
