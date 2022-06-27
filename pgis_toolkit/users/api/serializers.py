from django.contrib.auth import get_user_model
from rest_framework import serializers

from pgis_toolkit.users.models import PreliminaryUser, UserRole

User = get_user_model()


# class UserSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = User
#         fields = ["username", "name", "url"]

#         extra_kwargs = {
#             "url": {"view_name": "api:user-detail", "lookup_field": "username"}
#         }

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'

class UserListSerializer(serializers.ModelSerializer):
    # image_thumbnail = serializers.SerializerMethodField()
    class Meta:
        model = UserRole
        fields = ('id',)
        # fields = ('id', 'image_thumbnail', 'user__full_name',  'contact', 'email', 'organization')
    # def get_image_thumbnail(self, instance):
    #     return User.active.get(id=instance.user.id).image_thumbnail
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['full_name'] = instance.user.full_name
        representation['image_thumbnail'] = self.context['request'].build_absolute_uri(instance.user.image_thumbnail.url) if instance.user.image_thumbnail else None
        # representation['image_thumbnail'] = instance.user.get_image_thumbnail
        representation['contact'] = instance.user.contact
        representation['email'] = instance.user.email
        representation['organization'] = instance.organization.name
        representation['project'] = instance.project.name
        representation['group'] = instance.group.name
        return representation

class PreliminaryUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreliminaryUser
        fields = '__all__'

class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = '__all__'
