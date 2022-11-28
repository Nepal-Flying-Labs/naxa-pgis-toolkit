from django.conf import settings
# from django.contrib import admin
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.utils.translation import ugettext_lazy as _

from pgis_toolkit.utils.constants import (
    CURRENT_YEAR,
    DATA_TYPE_CHOICES,
    FILE_TYPE_CHOICES,
    GEOMETRY_TYPE_CHOICES,
    LAYER_TYPE_CHOICES,
    LOCATION_TYPE_CHOICES,
    PUBLISHED_MONTH_CHOICES,
    THEMATIC_AREA_CHOICES,
    UNIT_CHOICES,
)
from pgis_toolkit.utils.make_thumbnail import make_thumbnail

from .utils.managers import ActiveManager

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
    thematic_areas=models.CharField(max_length=50, choices=THEMATIC_AREA_CHOICES, blank=True, null=True)
    description = models.CharField(max_length=254, blank=True, null=True)
    size = models.CharField(max_length=10,blank=True, null=True)

    class Meta:
        app_label = 'projects'

    def __str__(self):
        return f'{self.id} {self.name}'

    def clean(self):
        """
        Make sure Organization name are unique
        """
        if Organization.active.exclude(id=self.id).filter(name=self.name).exists():
            raise ValidationError(f'Organization with name {self.name} already exists.')

class Country(models.Model):
    name = models.CharField(max_length=100, blank=True, null=True)
    code = models.CharField(max_length=3, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    def __str__(self):
        return f'{self.name}, {self.code}'

    class Meta:
        app_label = 'projects'

class State(models.Model):
    name = models.CharField(max_length=100, blank=True, null=True)
    code = models.CharField(max_length=10, blank=True, null=True)
    country = models.ForeignKey(Country,on_delete=models.SET_NULL, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    def __str__(self):
        return f'{self.name}, {self.code}, {self.country}'

    class Meta:
        app_label = 'projects'

class DefaultTheme(models.Model):
    name=models.CharField(max_length=254)
    order=models.PositiveIntegerField(blank=True,null=True)
    description=models.TextField(blank=True, null=True)

    def __str__(self):
        return str(self.name)
    class Meta:
        app_label = 'projects'

class Project(IsDeleted,DateTimeStamp):

    organization=models.ForeignKey(Organization, related_name='ProjectOrganization', on_delete=models.CASCADE,null=True)
    name=models.CharField(max_length=254)
    description=models.TextField(blank=True,null=True)
    start_date=models.DateField(blank=True,null=True)
    end_date=models.DateField(blank=True,null=True)
    country = models.ManyToManyField(Country, blank=True)
    state = models.ManyToManyField(State, blank=True)
    location_type = models.CharField(max_length=50, choices=LOCATION_TYPE_CHOICES, blank=True, null=True)
    file = models.FileField(upload_to='site/',blank=True, null=True)
    geometry_type = models.CharField(max_length=50, blank=True, null=True)
    file_type = models.CharField(max_length=50, choices=FILE_TYPE_CHOICES, blank=True, null=True)
    bbox = models.JSONField(blank=True, null=True)

    class Meta:
        app_label = 'projects'

    def __str__(self):
        return f'{self.id} {self.name}'

    def clean(self):
        """
        Make sure Project name are unique
        """
        if Project.active.exclude(id=self.id).filter(name=self.name).exists():
            raise ValidationError(f'Project with name {self.name} already exists.')

class ProjectLocationFeatureCollection(DateTimeStamp, IsDeleted):
    project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, related_name='ProjectLocation')
    attributes = models.JSONField(blank=True, null=True)
    geometry = models.GeometryField(srid=4326, blank=True, null=True)

    def __str__(self):
        return str(self.id)

    class Meta:
        app_label = 'projects'

class Template(models.Model):
    name=models.CharField(max_length=254)
    geometry_type=models.CharField(max_length=50,choices=GEOMETRY_TYPE_CHOICES)

    def __str__(self):
        return f'{self.name}'

    class Meta:
        # app_label = 'projects'
        abstract=True

    def clean(self):
        """
        Make sure template name are unique
        """
        if LayerTemplate.active.exclude(id=self.id).filter(name=self.name).exists():
            raise ValidationError(
                f'Layer template with name {self.name} already exists')


class TemplateAttribute(models.Model):
    # layer_template=models.ForeignKey(LayerTemplate,on_delete=models.CASCADE)
    name=models.CharField(max_length=254)
    alias=models.CharField(max_length=254,blank=True,null=True)
    data_type=models.CharField(max_length=20,choices=DATA_TYPE_CHOICES,default='str')
    length=models.IntegerField(blank=True,null=True)
    precision=models.IntegerField(blank=True,null=True)
    unit=models.CharField(max_length=20,choices=UNIT_CHOICES,blank=True,null=True)
    # choices=ArrayField(models.CharField(max_length=100, blank=True),size=20,blank=True, null=True)
    class Meta:
        # app_label = 'projects'
        abstract=True
        # unique_together = (("layer_template", "name"),)

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


class LayerTemplate(Template,IsDeleted,DateTimeStamp):

    class Meta:
        app_label = 'projects'

class LayerTemplateAttribute(DateTimeStamp,TemplateAttribute):
    layer_template=models.ForeignKey(LayerTemplate,on_delete=models.CASCADE)

    class Meta:
        app_label = 'projects'
        unique_together = (("layer_template", "name"),)

class Document(DateTimeStamp):
    name=models.CharField(max_length=254)
    project=models.ForeignKey(Project, on_delete=models.CASCADE)
    cover_image=models.ImageField(upload_to='documents/cover_images/', blank=True, null=True)
    cover_image_thumbnail=models.ImageField(upload_to='thumbnails/', editable=False, blank=True, null=True)
    published_year = models.IntegerField(validators=[MaxValueValidator(CURRENT_YEAR), MinValueValidator(1980)])
    published_month = models.CharField(max_length=3, choices=PUBLISHED_MONTH_CHOICES, blank=True, null=True)
    published_day = models.IntegerField(validators=[MaxValueValidator(31), MinValueValidator(1)], blank=True, null=True)
    file = models.FileField(upload_to='documents/files/', blank=True, null=True)
    url = models.URLField(blank=True, null=True)

    class Meta:
        app_label = 'projects'
        unique_together = (("project", "name"),)
        permissions = (
            ('download_document', 'Can download the document'),
        )

class RequestDemo(DateTimeStamp):
    full_name = models.CharField(max_length=254)
    email = models.EmailField(max_length=254)
    #validators=[RegexValidator(r'^\d{1,10}$')]
    phone = models.CharField(max_length=10, blank=True, null=True) #no validators since pgis_toolkit users are foreign.
    organization_name = models.CharField(max_length=254, blank=True, null=True)
    marketing_communications = models.BooleanField(default=False)

    class Meta:
        app_label = 'projects'

class RequestDemoAlert(models.Model):
    name = models.CharField(max_length=254, blank=True, null=True)
    email = models.EmailField(max_length=254)

    class Meta:
        app_label = 'projects'
