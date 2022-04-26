from django.contrib import admin

from .models import *

# Register your models here.
admin.site.register(OrganizationCategory)
admin.site.register(Organization)
admin.site.register(Project)
admin.site.register(DefaultTheme)
admin.site.register(LayerTemplate)
admin.site.register(LayerTemplateAttribute)
