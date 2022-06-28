from django.contrib.auth.models import AbstractUser, Group, UserManager
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from config.settings.base import URL
from pgis_toolkit.projects.models import DateTimeStamp, IsDeleted, Organization, Project
from pgis_toolkit.utils.constants import STATUS_CHOICES
from pgis_toolkit.utils.make_thumbnail import make_thumbnail

# class User(AbstractUser):
#     """
#     Default custom user model for PGIS toolkit.
#     If adding fields that need to be filled at user signup,
#     check forms.SignupForm and forms.SocialSignupForms accordingly.
#     """

#     #: First and last name do not cover name patterns around the globe
#     name = CharField(_("Name of User"), blank=True, max_length=255)
#     first_name = None  # type: ignore
#     last_name = None  # type: ignore

#     def get_absolute_url(self):
#         """Get url for user's detail view.

#         Returns:
#             str: URL for user detail.

#         """
#         return reverse("users:detail", kwargs={"username": self.username})

class User(IsDeleted, AbstractUser):
    """
    Default custom user model for PGIS toolkit.
    """
    full_name = models.CharField(max_length=254)
    '''removing unnecessary fields'''
    first_name = None
    last_name = None
    groups = None
    user_permissions = None
    #overriding email field by making it unique field
    email = models.EmailField(unique=True)
    address = models.CharField(max_length=254)
    image = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    image_thumbnail = models.ImageField(upload_to='thumbnails/', editable=False, blank=True, null=True)
    contact = models.CharField(max_length=13, blank=True, null=True)
    email_verification_token = models.UUIDField(blank=True, null=True)
    objects = UserManager()

    class Meta:
        app_label = 'users'

    def save(self, *args, **kwargs):
        if self.image:
            if not make_thumbnail(self.image, self.image_thumbnail):
                raise Exception(
                    'Could not create thumbnail- is the file type is valid')
        # if self.password:
        #     self.password=make_password(self.password)
        super(User, self).save(*args, **kwargs)

    # @property
    # def get_image_thumbnail(self):
    #     return f'{URL}{self.image_thumbnail.url}' if self.image_thumbnail else None


class UserRole(IsDeleted):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True)
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        app_label = 'users'
        unique_together = (("user", "project"),)

    def __str__(self):
        return f'{self.user}, {self.organization}, {self.group}'

'''Model to store required information to verify and identify user for registration using the email invite approach'''
class PreliminaryUser(IsDeleted, DateTimeStamp):
    email = models.EmailField(max_length=254, unique=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, blank=True, null=True)
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True)
    email_verification_token = models.UUIDField()
    status = models.CharField(max_length=254, choices=STATUS_CHOICES, default='Pending')

    class Meta:
        app_label = 'users'
