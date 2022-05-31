import os.path
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image


def make_thumbnail(image_name, thumbnail_name):
    try:
        image = Image.open(image_name)
        image.thumbnail((600, 400), Image.ANTIALIAS)

        thumb_name, thumb_extension = os.path.splitext(image_name.name)
        thumb_extension = thumb_extension.lower()

        thumb_filename = thumb_name + '_thumb' + thumb_extension

        if thumb_extension in ['.jpg', '.jpeg']:
            FTYPE = 'JPEG'
        elif thumb_extension == '.gif':
            FTYPE = 'GIF'
        elif thumb_extension == '.png':
            FTYPE = 'PNG'
        else:
            return False  # Unrecognized file type

        # Save thumbnail to in-memory file as StringIO
        temp_thumb = BytesIO()
        image.save(temp_thumb, FTYPE)
        temp_thumb.seek(0)

        # set save=False, otherwise it will run in an infinite loop
        thumbnail_name.save(thumb_filename, ContentFile(
            temp_thumb.read()), save=False)
        temp_thumb.close()

        return True
    except:
        pass
