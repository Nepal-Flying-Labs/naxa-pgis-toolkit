import os

from django.core.exceptions import ValidationError


def validate_std_icon_extension(value):
    ext = os.path.splitext(value.name)[1]  # [0] returns path+filename
    valid_extensions = ['.svg', '.png', '.jpg']
    if not ext.lower() in valid_extensions:
        raise ValidationError('Unsupported file extension.')

def validate_icon_extension(value):
    ext = os.path.splitext(value.name)[1]  # [0] returns path+filename
    valid_extensions = ['.svg', '.png', '.jpg']
    if not ext.lower() in valid_extensions:
        raise ValidationError('Unsupported file extension.')
