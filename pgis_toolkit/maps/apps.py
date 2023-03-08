import sys

from django.apps import AppConfig
from django.db.models.signals import post_save

# from maps.signals import post_save_layer

class MapsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pgis_toolkit.maps'

    def ready(self):
        import pgis_toolkit.maps.signals

        # '''execute code only once at startup'''
        # print(sys.argv, "is system arguments******************************************************")
        # if 'runserver_plus' not in sys.argv:
        #     return True
        # from pgis_toolkit.maps.models import Layer
        # print(Layer.active.all().count(), "is layer's count**************************************")
        # post_save.connect(post_save_layer, sender='maps.Layer')
