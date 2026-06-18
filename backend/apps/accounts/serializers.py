from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'role', 'organisation', 'phone', 'created_at']
        read_only_fields = ['id', 'created_at']


class RegisterSerializer(serializers.ModelSerializer):
    email     = serializers.EmailField(required=True)
    password  = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model  = User
        fields = ['username', 'email', 'password', 'password2',
                  'first_name', 'last_name', 'organisation', 'phone']

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password2': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = User(**validated_data, is_active=False)
        user.set_password(password)
        user.save()
        return user


class CustomTokenSerializer(TokenObtainPairSerializer):
    """Add user info to JWT response."""
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['role']     = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data
