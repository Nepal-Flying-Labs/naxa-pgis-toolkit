from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework import status
from rest_framework.response import Response

from pgis_toolkit.projects.models import DefaultTheme, Document
from pgis_toolkit.maps.models import Theme, Project
from pgis_toolkit.utils.make_thumbnail import make_thumbnail


@receiver(post_save, sender=Project)
def post_save_project(sender, created, instance,**kwargs):
    '''
    This signal is to create an instance of Theme based on DefaultTheme objects for a project.
    '''
    errors = []
    try:
        if created:
            default_themes = DefaultTheme.objects.all()
            for theme in default_themes:
                Theme.objects.create(project=instance, name=theme.name, order=theme.order)
            return Response(status=status.HTTP_200_OK, data={"Message": "Theme Successfully created"})
    except Exception as e:
        errors.append({'errorName': str(e), 'details': str(e)})
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'error': errors})

@receiver(post_save, sender=Document)
def post_save_document(sender, created, instance,**kwargs):
    '''
    This signal is to create a cover image thumbnail based on Cover Image objects for a Document.
    '''
    errors = []
    try:
        if created:
            make_thumbnail(instance.cover_image, instance.cover_image_thumbnail)
            return Response(status=status.HTTP_200_OK, data={"Message": "Cover Image Thumbnail Successfully created"})
    except Exception as e:
        errors.append({'errorName': str(e), 'details': str(e)})
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'error': errors})
