from django.contrib import admin

from .models import *

# Register your models here.

# Register your models here.
admin.site.register(Theme, ThemeAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Layer, LayerAdmin)
