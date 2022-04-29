from django.conf import settings
# from django.contrib import admin
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
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
        app_label = 'projects'
        abstract = True

class DateTimeStamp(models.Model):
    uploaded_date = models.DateTimeField(
        auto_now_add=True, blank=True, null=True)
    last_updated = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        app_label = 'projects'
        abstract = True

class OrganizationCategory(IsDeleted,DateTimeStamp):
    name=models.CharField(max_length=254)

    class Meta:
        app_label = 'projects'

    def __str__(self):
        return f'{self.name}'

    def clean(self):
        """
        Make sure Organization Category name are unique
        """
        if OrganizationCategory.active.exclude(id=self.id).filter(name=self.name).exists():
            raise ValidationError(f'Category with name {self.name} already exists.')

class Organization(IsDeleted,DateTimeStamp):
    category=models.ForeignKey(OrganizationCategory,on_delete=models.SET_NULL,blank=True,null=True)
    name=models.CharField(max_length=254)
    email=models.EmailField(blank=True,null=True)
    address=models.CharField(max_length=254,blank=True,null=True)
    contact=models.CharField(max_length=20,blank=True,null=True)
    link=models.URLField(blank=True,null=True)

    class Meta:
        app_label = 'projects'

    def __str__(self):
        return f'{self.name}'

    def clean(self):
        """
        Make sure Organization name are unique
        """
        if Organization.active.exclude(id=self.id).filter(name=self.name).exists():
            raise ValidationError(f'Organization with name {self.name} already exists.')

class Project(IsDeleted,DateTimeStamp):
    organization=models.ForeignKey(Organization,on_delete=models.CASCADE,null=True)
    name=models.CharField(max_length=254)
    description=models.TextField(blank=True,null=True)
    start_date=models.DateField(blank=True,null=True)
    end_date=models.DateField(blank=True,null=True)

    class Meta:
        app_label = 'projects'

    def __str__(self):
        return f'{self.name}'

    def clean(self):
        """
        Make sure Project name are unique
        """
        if Project.active.exclude(id=self.id).filter(name=self.name).exists():
            raise ValidationError(f'Project with name {self.name} already exists.')

class DefaultTheme(IsDeleted,DateTimeStamp):
    name=models.CharField(max_length=254)
    order=models.PositiveIntegerField(blank=True,null=True)

    def __str__(self):
        return f'{self.name}'

    class Meta:
        app_label = 'projects'

class LayerTemplate(IsDeleted,DateTimeStamp):
    name=models.CharField(max_length=254)
    geometry_type=models.CharField(max_length=50,choices=GEOMETRY_TYPE_CHOICES)

    def __str__(self):
        return f'{self.name}'

    class Meta:
        app_label = 'projects'

    def clean(self):
        """
        Make sure template name are unique
        """
        if LayerTemplate.active.exclude(id=self.id).filter(name=self.name).exists():
            raise ValidationError(
                f'Layer template with name {self.name} already exists')


class LayerTemplateAttribute(DateTimeStamp):
    layer_template=models.ForeignKey(LayerTemplate,on_delete=models.CASCADE)
    name=models.CharField(max_length=254)
    alias=models.CharField(max_length=254,blank=True,null=True)
    data_type=models.CharField(max_length=20,choices=DATA_TYPE_CHOICES,default='str')
    length=models.IntegerField(blank=True,null=True)
    precision=models.IntegerField(blank=True,null=True)
    unit=models.CharField(max_length=20,choices=UNIT_CHOICES,blank=True,null=True)
    # choices=ArrayField(models.CharField(max_length=100, blank=True),size=20,blank=True, null=True)
    class Meta:
        app_label = 'projects'
        unique_together = (("layer_template", "name"),)

    def clean(self):
        """
        Make sure proper fields are added
        """
        if (self.data_type=="str" or self.data_type=="int") and not self.length:
            # Raise a Validation error if length is empty when data_type equal to text or integer.
            raise ValidationError('length is missing')
        elif self.data_type=="float" and not (self.length or self.precision):
            # Raise a Validation error if length or precision is empty when data_type equal is decimal/float.
            raise ValidationError('length and precision should not be null')
