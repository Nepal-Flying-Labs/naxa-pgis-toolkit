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
    # role = serializers.SerializerMethodField()
    # project = serializers. SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'image_thumbnail', 'full_name',  'contact', 'email', 'organization')

    # def get_role(self, instance):
    #     user_role = UserRole.active.filter(user__id=instance.id).values_list('user__id', )

class PreliminaryUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreliminaryUser
        fields = '__all__'

class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = '__all__'