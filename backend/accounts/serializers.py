from django.contrib.auth.models import User
from rest_framework import serializers
from .models import District, Town, CarbonEmission, UserProfile

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email')

class DistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = District
        fields = '__all__'

class TownSerializer(serializers.ModelSerializer):
    district_name = serializers.CharField(source='district.name', read_only=True)
    class Meta:
        model = Town
        fields = ('id', 'name', 'district', 'district_name')

class CarbonEmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarbonEmission
        fields = '__all__'

class UserProfileSerializer(serializers.ModelSerializer):
    preferred_district_name = serializers.SerializerMethodField()
    preferred_town_name = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ('id', 'preferred_district', 'preferred_town', 'preferred_district_name', 'preferred_town_name')

    def get_preferred_district_name(self, obj):
        return obj.preferred_district.name if obj.preferred_district else None

    def get_preferred_town_name(self, obj):
        return obj.preferred_town.name if obj.preferred_town else None

class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password']
        )
        UserProfile.objects.get_or_create(user=user)
        return user
