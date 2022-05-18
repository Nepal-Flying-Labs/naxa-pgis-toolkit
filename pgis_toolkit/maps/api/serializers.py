from rest_framework import serializers

from pgis_toolkit.maps.models import *


class LayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Layer
        fields = '__all__'
