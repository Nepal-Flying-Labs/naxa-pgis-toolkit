from django.conf import settings
from django.contrib.gis.db import models
from django.contrib import admin
from django.utils.translation import ugettext_lazy as _

from .utils.managers import ActiveManager

GEOMETRY_TYPE_CHOICES=(
                        ("Point",_("Point")),
                        ("MultiPoint",_('MultiPoint')),
                        ('LineString',_('LineString')),
                        ("MultiLineString",_("MultiLineString")),
                        ("Polygon",_('Polygon')),
                        ('MultiPolygon',_('MultiPolygon'))
                    )

DATA_TYPE_CHOICES=(
                    ("int",_("Integer")),
                    ("float",_('Decimal')),
                    ('str',_('Text')),
                    ('date',_('Date'))
                )

UNIT_CHOICES=(
                ("m",_("Meter")),
                ("sqm",_('Square Meter')),
                ('km',_('Kilometer'))
            )
# class Organization(models.Model):
#     admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)


# class Project(models.Model):
#     project_managers = models.ManyToManyField(settings.AUTH_USER_MODEL)
#     bounds = models.PolygonField()


# class Contribution(models.Model):
#     project_manager = models.ForeignKey(
#         settings.AUTH_USER_MODEL, on_delete=models.CASCADE
#     )
#     contributor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
#     parent = models.ForeignKey("self")

class IsDeleted(models.Model):
    is_deleted = models.BooleanField(default=False)
    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        abstract = True

class DateTimeStamp(models.Model):
    uploaded_date = models.DateTimeField(
        auto_now_add=True, blank=True, null=True)
    last_updated = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        abstract = True

class OrganizationCategory(IsDeleted,DateTimeStamp):
    name=models.CharField(max_length=254)

    def __str__(self):
        return f'{self.name}'

class Organization(IsDeleted,DateTimeStamp):
    category=models.ForeignKey(OrganizationCategory,on_delete=models.SET_NULL,blank=True,null=True)
    name=models.CharField(max_length=254)
    email=models.EmailField(blank=True,null=True)
    address=models.CharField(max_length=254,blank=True,null=True)
    contact=models.CharField(max_length=20,blank=True,null=True)
    link=models.URLField(blank=True,null=True)

    def __str__(self):
        return f'{self.name}'

class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'category', 'name', 'link')
    search_fields = ('id', 'name', 'email', 'link')
    list_filter = ('category',)

class Project(IsDeleted,DateTimeStamp):
    organization=models.ForeignKey(Organization,on_delete=models.CASCADE,null=True)
    name=models.CharField(max_length=254)
    description=models.TextField(blank=True,null=True)
    start_date=models.DateField(blank=True,null=True)
    end_date=models.DateField(blank=True,null=True)

    def __str__(self):
        return f'{self.name}'

class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_deleted', 'organization', 'name')
    search_fields = ('id', 'name')
    list_filter = ('organization', 'start_date', 'end_date')

class DefaultTheme(IsDeleted,DateTimeStamp):
    name=models.CharField(max_length=254)
    order=models.PositiveIntegerField(blank=True,null=True)

    def __str__(self):
        return f'{self.name}'

class LayerTemplate(IsDeleted,DateTimeStamp):
    name=models.CharField(max_length=254)
    geometry_type=models.CharField(max_length=50,choices=GEOMETRY_TYPE_CHOICES)

    def __str__(self):
        return f'{self.name}'

class LayerTemplateAttribute(models.Model):
    layer_template=models.ForeignKey(LayerTemplate,on_delete=models.CASCADE)
    name=models.CharField(max_length=254)
    alias=models.CharField(max_length=254,blank=True,null=True)
    data_type=models.CharField(max_length=20,choices=DATA_TYPE_CHOICES,default='str')
    length=models.IntegerField(blank=True,null=True)
    precision=models.IntegerField(blank=True,null=True)
    unit=models.CharField(max_length=20,choices=UNIT_CHOICES,blank=True,null=True)
    # choices=ArrayField(models.CharField(max_length=100, blank=True),size=20,blank=True, null=True)

class LayerTemplateAttributeAdmin(admin.ModelAdmin):
    list_display = ('id', 'layer_template', 'name', 'alias', 'unit')
    search_fields = ('id', 'name', 'alias')
    list_filter = ('layer_template', 'data_type')