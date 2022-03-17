from django.conf import settings
from django.contrib.gis.db import models


class Organization(models.Model):
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)


class Project(models.Model):
    project_managers = models.ManyToManyField(settings.AUTH_USER_MODEL)
    bounds = models.PolygonField()


class Contribution(models.Model):
    project_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    contributor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    parent = models.ForeignKey("self")
