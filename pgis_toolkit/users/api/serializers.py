from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
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
        representation['organization'] = instance.organization.name if instance.organization else None
        representation['project'] = instance.project.name if instance.project else None
        representation['group'] = instance.group.name if instance.group else None
        return representation

class PreliminaryUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreliminaryUser
        fields = '__all__'

class PreliminaryUserListSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()
    group = serializers.SerializerMethodField()
    class Meta:
        model = PreliminaryUser
        fields = ('id', 'email', 'organization', 'project', 'group', 'status', 'last_updated')

    def get_organization(self, instance):
        return instance.organization.name if instance.organization else None

    def get_project(self, instance):
        return instance.project.name if instance.project else None

    def get_group(self, instance):
        return instance.group.name if instance.group else None

class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = '__all__'

class UserGroupPermissionsSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ['permissions']

    def get_permissions(self, obj):
        if obj.permissions:
            data = []
            qs = obj.permissions.all().values('name')
            for q in qs:
                data.append(q['name'])
            return data
        return data


class UserGroupListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ('id', 'name')
