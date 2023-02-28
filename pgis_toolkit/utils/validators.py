import os

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


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

class CustomURLValidator(URLValidator):
    def __call__(self, value):
        print(value, "is value")
        if '://' not in value:
            # Validate as if it were http://
            value = 'http://' + value
            print(value, "after value")
        super(CustomURLValidator, self).__call__(value)

# def CustomURLValidator(value):
#     print(value, "is value")
#     if '://' not in value:
#         value = 'http://' + value
#     print(value, "is value after")
#     return value

def validate_url(value):
    validator = URLValidator()
    try:
        validator(value)
    except ValidationError:
        raise ValidationError('Invalid URL')
