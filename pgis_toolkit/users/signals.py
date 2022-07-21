from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from rest_framework import status
from rest_framework.response import Response

from config.settings import base as settings
from pgis_toolkit.maps.models import Project, Theme

User = get_user_model()

@receiver(post_save, sender=User)
def post_save_user(sender, created, instance,**kwargs):
    '''
    This signal is to hash the password of a user once created.'''
    errors = []
    try:
        if created and instance.is_superuser != True:
            instance.password = make_password(instance.password)
            instance.save()
            return Response(status=status.HTTP_200_OK, data={"Message": "Password hashing successful!"})
    except Exception as e:
        errors.append({'errorName': str(e), 'details': str(e)})
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'error': errors})
