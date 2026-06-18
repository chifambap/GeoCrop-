import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Extended user with role and organisation."""

    class Role(models.TextChoices):
        ADMIN      = 'admin',      'Admin'
        COLLECTOR  = 'collector',  'Collector'
        VALIDATOR  = 'validator',  'Validator'
        VIEWER     = 'viewer',     'Viewer'

    role         = models.CharField(max_length=20, choices=Role.choices, default=Role.COLLECTOR)
    organisation = models.CharField(max_length=200, blank=True)
    phone        = models.CharField(max_length=30, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['username']

    def __str__(self):
        return f'{self.username} ({self.role})'

    @property
    def is_admin_or_validator(self):
        return self.role in (self.Role.ADMIN, self.Role.VALIDATOR)

    def save(self, *args, **kwargs):
        # Auto-grant Django admin access to admin-role users
        if self.role == self.Role.ADMIN:
            self.is_staff = True
            self.is_superuser = True
        else:
            self.is_staff = False
            self.is_superuser = False
        super().save(*args, **kwargs)


class RegistrationRequest(models.Model):
    """Pending registration awaiting admin approval."""

    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='registration_request')
    token      = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} — pending'
