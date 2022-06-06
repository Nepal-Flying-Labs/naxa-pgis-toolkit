from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from config.settings import base as settings

from rest_framework import status
from rest_framework.response import Response

from pgis_toolkit.projects.models import DefaultTheme, Document, RequestDemo, RequestDemoAlert
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

@receiver(post_save, sender=RequestDemo)
def post_save_requestdemo(sender, created, instance, **kwargs):
    '''
    This signal is to send email to the user requesting demo of pgis tool.
    '''
    errors=[]
    try:
        if created:
            '''sending response to the user requesting demo'''
            data = {
                'paragraph_1': 'Thank you for taking interest in USAFIRI mapping tool. We will look on our availability and inform you the timings of the demo.',
            }
            template = 'email/email_request_demo.html'
            html_message = render_to_string(template, data)
            message = strip_tags(html_message)
            subject = 'Succesful Request for Demo, USAFIRI'
            from_email = settings.EMAIL_HOST_USER
            recipient_list = [instance.email]
            send_mail(subject, message, from_email, recipient_list,
                    html_message=html_message, fail_silently=False)
            '''informing the concerned team members of USAFIRI that a demo is requested.'''
            data = {
                'paragraph_1': f'This is to inform you that Mr./Mrs. {instance.full_name} has requested for a demo of USAFIRI mapping tool. Credentials of the requesting user is as follows: \
                \nName: {instance.full_name} \
                \nEmail: {instance.email} \
                \nPhone: {instance.phone} \
                \nOrganization: {instance.organization_name} \
                \nMarketing Communications: {instance.marketing_communications}',
            }
            template = 'email/email_request_demo.html'
            html_message = render_to_string(template, data)
            message = strip_tags(html_message)
            subject = 'Request for Demo'
            from_email = settings.EMAIL_HOST_USER
            recipient_list = RequestDemoAlert.objects.values_list('email', flat=True)
            send_mail(subject, message, from_email, recipient_list,
                    html_message=html_message, fail_silently=False)
    except Exception as e:
        instance.delete()
        errors.append({'errorName': str(e), 'details': str(e)})
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'message': 'Error Occured', 'error': errors})