from datetime import date

from django.utils.translation import ugettext_lazy as _

LAYER_TYPE_CHOICES=(("Raster",_("Raster")),("Vector",_('Vector')),('WMS',_('WMS')))
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

LOCATION_TYPE_CHOICES = (
    ('Custom Draw', _('Custom Draw')),
    ('File Upload', _('File Upload'))
)

FILE_TYPE_CHOICES = (
    ('Shapefile', _('Shapefile')),
    ('GeoJSON', _('GeoJSON')),
)

PUBLISHED_MONTH_CHOICES = (
    ('Jan', _('January')),
    ('Feb', _('February')),
    ('Mar', _('March')),
    ('Apr', _('APril')),
    ('May', _('May')),
    ('Jun', _('June')),
    ('Jul', _('July')),
    ('Aug', _('August')),
    ('Sep', _('September')),
    ('Oct', _('October')),
    ('Nov', _('November')),
    ('Dec', _('December')),
)

CURRENT_YEAR = int(date.today().year)

STATUS_CHOICES = (
    ('Pending', _('Pending')),
    ('Expired', _('Expired'))
)

THEMATIC_AREA_CHOICES = (
    ('Climate change and Energy', _('Climate change and Energy')),
)
