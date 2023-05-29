from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pgis_toolkit.projects"

    def ready(self):
        import pgis_toolkit.projects.signals
