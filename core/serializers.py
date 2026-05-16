from rest_framework import serializers
from django.contrib.auth.models import User

class RegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    phone = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)


class ParentProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=True, allow_blank=False)
    last_name = serializers.CharField(required=True, allow_blank=False)
    phone = serializers.CharField(required=True, allow_blank=False)
    address = serializers.CharField(required=True, allow_blank=False)

    def validate_phone(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Phone number is too short.")
        return value

class TherapistProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=True, allow_blank=False)
    last_name = serializers.CharField(required=True, allow_blank=False)
    specialization = serializers.CharField(required=True, allow_blank=False)