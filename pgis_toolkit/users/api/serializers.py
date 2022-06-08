from django.contrib.auth import get_user_model
from rest_framework import serializers
from pgis_toolkit.users.models import PreliminaryUser
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
        fields = ("username", "name")

class PreliminaryUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreliminaryUser
        fields = '__all__'