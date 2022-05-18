from django.apps import AppConfig

# from django.db.models.signals import post_save
# from maps.signals import post_save_layer

class MapsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'maps'

    def ready(self):
        import maps.signals

        # post_save.connect(post_save_layer, sender='maps.Layer')
