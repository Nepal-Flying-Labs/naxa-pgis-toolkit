from django.core.management.base import BaseCommand

from pgis_toolkit.maps.models import FeatureCollection, Layer

'''
python manage.py delete-uploading-layers
this is to run once at system startup only
'''
class Command(BaseCommand):
    help = 'delete layers whose uploading status is uploading.'

    def handle(self, *args, **kwargs):
        try:
            Layer.objects.filter(upload_status='uploading').delete()
            print("Layers with upload_status as uploading successfully deleted.")
        except Exception as e:
            print("delete-uploading-layers management command run failed. Details:", str(e))
